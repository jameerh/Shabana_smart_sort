"""Content and OCR extraction engine for textual search and indexing."""
import os
import io
import csv
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple

from shabana_smart_sort.domain.models import FileItem
from shabana_smart_sort.infrastructure.database import DatabaseManager

logger = logging.getLogger("ShabanaSmartSort.ContentEngine")


class ContentEngine:
    """
    Extracts text from files (.txt, .csv, .pdf, .docx, .xlsx, .pptx) and images (OCR).
    Maintains an SQLite persistent cache to prevent re-extracting unchanged files.
    """

    SUPPORTED_TEXT_EXTS = {
        ".txt", ".csv", ".tsv", ".json", ".xml", ".html", ".htm",
        ".md", ".log", ".py", ".js", ".ts", ".css", ".sql", ".yaml", ".yml"
    }
    SUPPORTED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif"}

    def __init__(self, db_manager: DatabaseManager, max_read_bytes: int = 1_000_000):
        self.db = db_manager
        self.max_read_bytes = max_read_bytes

    def get_or_extract_content(self, file_path: Path, modified_at: datetime, size_bytes: int) -> Tuple[str, str]:
        """
        Returns (content_text, ocr_text).
        Checks cache first. If missing or file modified/resized, performs extraction and caches result.
        """
        cached = self._get_cached(file_path, modified_at, size_bytes)
        if cached is not None:
            return cached

        content_text = ""
        ocr_text = ""
        ext = file_path.suffix.lower()

        try:
            if ext in self.SUPPORTED_TEXT_EXTS:
                content_text = self._extract_plain_text(file_path)
            elif ext == ".pdf":
                content_text = self._extract_pdf(file_path)
            elif ext in {".docx", ".xlsx", ".pptx"}:
                content_text = self._extract_office(file_path, ext)
            elif ext in self.SUPPORTED_IMAGE_EXTS:
                ocr_text = self._extract_ocr(file_path)
        except Exception as e:
            logger.debug(f"Failed extracting text from {file_path.name}: {e}")

        # Store in cache
        self._store_cached(file_path, modified_at, size_bytes, content_text, ocr_text)
        return content_text, ocr_text

    def enrich_file_item(self, item: FileItem) -> FileItem:
        """Populates content_text and ocr_text on a FileItem."""
        content_text, ocr_text = self.get_or_extract_content(item.path, item.modified_at, item.size_bytes)
        item.content_text = content_text
        item.ocr_text = ocr_text
        return item

    def _get_cached(self, file_path: Path, modified_at: datetime, size_bytes: int) -> Optional[Tuple[str, str]]:
        conn = self.db.get_connection()
        cur = conn.cursor()
        mod_iso = modified_at.isoformat()
        cur.execute(
            "SELECT content_text, ocr_text FROM file_content_index WHERE path = ? AND modified_at = ? AND size_bytes = ?",
            (str(file_path), mod_iso, size_bytes)
        )
        row = cur.fetchone()
        if row:
            return row["content_text"] or "", row["ocr_text"] or ""
        return None

    def _store_cached(self, file_path: Path, modified_at: datetime, size_bytes: int, content_text: str, ocr_text: str) -> None:
        conn = self.db.get_connection()
        now_iso = datetime.now(timezone.utc).isoformat()
        with conn:
            conn.execute("""
                INSERT INTO file_content_index (path, modified_at, size_bytes, content_text, ocr_text, indexed_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                    modified_at = excluded.modified_at,
                    size_bytes = excluded.size_bytes,
                    content_text = excluded.content_text,
                    ocr_text = excluded.ocr_text,
                    indexed_at = excluded.indexed_at
            """, (str(file_path), modified_at.isoformat(), size_bytes, content_text, ocr_text, now_iso))

    def _extract_plain_text(self, file_path: Path) -> str:
        for enc in ("utf-8", "latin-1", "cp1252"):
            try:
                with open(file_path, "r", encoding=enc, errors="replace") as f:
                    return f.read(self.max_read_bytes)
            except Exception:
                continue
        return ""

    def _extract_pdf(self, file_path: Path) -> str:
        # Try pypdf / pypdf2 / pymupdf if installed
        try:
            import pypdf
            reader = pypdf.PdfReader(str(file_path))
            pages_text = []
            for i, page in enumerate(reader.pages):
                if i > 20:  # limit first 20 pages for responsiveness
                    break
                t = page.extract_text()
                if t:
                    pages_text.append(t)
            return "\n".join(pages_text)
        except Exception:
            pass

        # Native stream fallback for basic readable PDF text
        try:
            with open(file_path, "rb") as f:
                raw = f.read(self.max_read_bytes)
                import re
                strings = re.findall(rb"\(([^\(\)]*)\)\s*Tj", raw)
                if strings:
                    return " ".join(s.decode("latin-1", errors="ignore") for s in strings)
        except Exception:
            pass
        return ""

    def _extract_office(self, file_path: Path, ext: str) -> str:
        # docx, xlsx, and pptx are ZIP archives containing xml
        try:
            import zipfile
            import xml.etree.ElementTree as ET
            with zipfile.ZipFile(file_path, "r") as z:
                xml_files = []
                if ext == ".docx":
                    xml_files = ["word/document.xml"]
                elif ext == ".xlsx":
                    xml_files = ["xl/sharedStrings.xml"]
                elif ext == ".pptx":
                    xml_files = [f for f in z.namelist() if f.startswith("ppt/slides/slide")]

                extracted_tokens = []
                for xf in xml_files:
                    if xf in z.namelist():
                        data = z.read(xf)
                        root = ET.fromstring(data)
                        extracted_tokens.extend(root.itertext())
                return " ".join(extracted_tokens)
        except Exception:
            pass
        return ""

    def _extract_ocr(self, file_path: Path) -> str:
        """Attempts OCR extraction using pytesseract or Windows Media OCR if available."""
        try:
            import pytesseract
            from PIL import Image
            img = Image.open(file_path)
            # Limit resolution if huge
            if img.width > 2500 or img.height > 2500:
                img.thumbnail((2500, 2500))
            return pytesseract.image_to_string(img)
        except Exception:
            pass
        return ""
