"""Metadata extraction and file categorization engine."""
import hashlib
import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict

from shabana_smart_sort.domain.enums import FileCategory
from shabana_smart_sort.domain.models import FileItem

# Standard extension mappings
EXTENSION_CATEGORIES: Dict[str, FileCategory] = {
    # Documents
    ".pdf": FileCategory.DOCUMENT,
    ".doc": FileCategory.DOCUMENT,
    ".docx": FileCategory.DOCUMENT,
    ".rtf": FileCategory.DOCUMENT,
    ".txt": FileCategory.DOCUMENT,
    ".odt": FileCategory.DOCUMENT,
    ".epub": FileCategory.DOCUMENT,

    # Spreadsheets
    ".xls": FileCategory.SPREADSHEET,
    ".xlsx": FileCategory.SPREADSHEET,
    ".csv": FileCategory.SPREADSHEET,
    ".tsv": FileCategory.SPREADSHEET,
    ".ods": FileCategory.SPREADSHEET,

    # Presentations
    ".ppt": FileCategory.PRESENTATION,
    ".pptx": FileCategory.PRESENTATION,
    ".odp": FileCategory.PRESENTATION,
    ".key": FileCategory.PRESENTATION,

    # Images
    ".jpg": FileCategory.IMAGE,
    ".jpeg": FileCategory.IMAGE,
    ".png": FileCategory.IMAGE,
    ".gif": FileCategory.IMAGE,
    ".bmp": FileCategory.IMAGE,
    ".webp": FileCategory.IMAGE,
    ".svg": FileCategory.IMAGE,
    ".tiff": FileCategory.IMAGE,
    ".ico": FileCategory.IMAGE,
    ".psd": FileCategory.IMAGE,
    ".raw": FileCategory.IMAGE,

    # Videos
    ".mp4": FileCategory.VIDEO,
    ".mkv": FileCategory.VIDEO,
    ".mov": FileCategory.VIDEO,
    ".avi": FileCategory.VIDEO,
    ".wmv": FileCategory.VIDEO,
    ".flv": FileCategory.VIDEO,
    ".webm": FileCategory.VIDEO,
    ".m4v": FileCategory.VIDEO,

    # Audio
    ".mp3": FileCategory.AUDIO,
    ".wav": FileCategory.AUDIO,
    ".flac": FileCategory.AUDIO,
    ".aac": FileCategory.AUDIO,
    ".ogg": FileCategory.AUDIO,
    ".m4a": FileCategory.AUDIO,
    ".wma": FileCategory.AUDIO,

    # Archives
    ".zip": FileCategory.ARCHIVE,
    ".rar": FileCategory.ARCHIVE,
    ".7z": FileCategory.ARCHIVE,
    ".tar": FileCategory.ARCHIVE,
    ".gz": FileCategory.ARCHIVE,
    ".bz2": FileCategory.ARCHIVE,
    ".xz": FileCategory.ARCHIVE,
    ".tgz": FileCategory.ARCHIVE,

    # Installers / Executables
    ".exe": FileCategory.INSTALLER,
    ".msi": FileCategory.INSTALLER,
    ".iso": FileCategory.INSTALLER,
    ".bat": FileCategory.INSTALLER,
    ".cmd": FileCategory.INSTALLER,
    ".apk": FileCategory.INSTALLER,
    ".dmg": FileCategory.INSTALLER,

    # Code / Developer
    ".py": FileCategory.CODE,
    ".js": FileCategory.CODE,
    ".ts": FileCategory.CODE,
    ".jsx": FileCategory.CODE,
    ".tsx": FileCategory.CODE,
    ".html": FileCategory.CODE,
    ".htm": FileCategory.CODE,
    ".css": FileCategory.CODE,
    ".json": FileCategory.CODE,
    ".xml": FileCategory.CODE,
    ".yaml": FileCategory.CODE,
    ".yml": FileCategory.CODE,
    ".c": FileCategory.CODE,
    ".cpp": FileCategory.CODE,
    ".h": FileCategory.CODE,
    ".java": FileCategory.CODE,
    ".cs": FileCategory.CODE,
    ".go": FileCategory.CODE,
    ".rs": FileCategory.CODE,
    ".php": FileCategory.CODE,
    ".rb": FileCategory.CODE,
    ".sql": FileCategory.CODE,
    ".sh": FileCategory.CODE,
    ".ps1": FileCategory.CODE,
}


class MetadataEngine:
    """Extracts system metadata, Windows file attributes, and calculates hashes."""

    @staticmethod
    def categorize_extension(ext: str) -> FileCategory:
        """Determines category from extension (e.g. '.pdf' -> DOCUMENT)."""
        return EXTENSION_CATEGORIES.get(ext.lower(), FileCategory.MISC)

    @classmethod
    def create_file_item(
        cls,
        path: Path,
        root_path: Optional[Path] = None,
        stat_result: Optional[os.stat_result] = None,
        compute_hash: bool = False,
    ) -> FileItem:
        """Constructs a FileItem with stat attributes and category."""
        if stat_result is None:
            stat_result = path.stat()

        ext = path.suffix.lower()
        category = cls.categorize_extension(ext)
        size_bytes = stat_result.st_size
        is_empty = (size_bytes == 0)

        # Dates (using UTC or local timezone-aware)
        created_at = datetime.fromtimestamp(stat_result.st_ctime)
        modified_at = datetime.fromtimestamp(stat_result.st_mtime)
        accessed_at = datetime.fromtimestamp(stat_result.st_atime)

        # Attributes
        name = path.name
        is_hidden = name.startswith(".")
        is_readonly = not (stat_result.st_mode & stat.S_IWRITE)

        # Windows hidden attribute check
        if hasattr(stat_result, "st_file_attributes"):
            # FILE_ATTRIBUTE_HIDDEN = 2
            if stat_result.st_file_attributes & 2:
                is_hidden = True
            # FILE_ATTRIBUTE_READONLY = 1
            if stat_result.st_file_attributes & 1:
                is_readonly = True

        relative_path = ""
        if root_path is not None:
            try:
                relative_path = str(path.relative_to(root_path))
            except ValueError:
                relative_path = path.name
        else:
            relative_path = path.name

        sha256 = None
        if compute_hash and not is_empty:
            sha256 = cls.compute_sha256(path)

        return FileItem(
            path=path,
            name=name,
            stem=path.stem,
            extension=ext,
            size_bytes=size_bytes,
            category=category,
            created_at=created_at,
            modified_at=modified_at,
            accessed_at=accessed_at,
            is_hidden=is_hidden,
            is_readonly=is_readonly,
            is_empty=is_empty,
            parent_dir=path.parent,
            relative_path=relative_path,
            sha256=sha256,
        )

    @staticmethod
    def compute_sha256(path: Path, max_bytes: Optional[int] = None) -> Optional[str]:
        """Calculates SHA256 hash safely with chunked streaming."""
        try:
            h = hashlib.sha256()
            bytes_read = 0
            with open(path, "rb") as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk:
                        break
                    h.update(chunk)
                    bytes_read += len(chunk)
                    if max_bytes and bytes_read >= max_bytes:
                        break
            return h.hexdigest()
        except Exception:
            return None
