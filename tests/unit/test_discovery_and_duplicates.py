"""Tests for discovery, metadata extraction, and duplicate detection."""
from pathlib import Path
from shabana_smart_sort.domain.enums import FileCategory
from shabana_smart_sort.engines.discovery_engine import DiscoveryEngine
from shabana_smart_sort.engines.duplicate_engine import DuplicateEngine
from shabana_smart_sort.engines.metadata_engine import MetadataEngine


def test_metadata_categorization():
    assert MetadataEngine.categorize_extension(".pdf") == FileCategory.DOCUMENT
    assert MetadataEngine.categorize_extension(".PNG") == FileCategory.IMAGE
    assert MetadataEngine.categorize_extension(".xlsx") == FileCategory.SPREADSHEET
    assert MetadataEngine.categorize_extension(".zip") == FileCategory.ARCHIVE
    assert MetadataEngine.categorize_extension(".exe") == FileCategory.INSTALLER
    assert MetadataEngine.categorize_extension(".py") == FileCategory.CODE
    assert MetadataEngine.categorize_extension(".unknown_xyz") == FileCategory.MISC


def test_discovery_engine_scan(temp_dir):
    # Setup test folder structure
    sub = temp_dir / "subfolder"
    sub.mkdir()
    (temp_dir / "file1.txt").write_text("Hello", encoding="utf-8")
    (temp_dir / "file2.pdf").write_text("World", encoding="utf-8")
    (sub / "subfile.jpg").write_text("Photo", encoding="utf-8")

    engine = DiscoveryEngine()

    # Non-recursive scan
    flat_items = engine.scan_directory(temp_dir, recursive=False)
    assert len(flat_items) == 2
    names = {i.name for i in flat_items}
    assert "file1.txt" in names
    assert "file2.pdf" in names

    # Recursive scan
    recursive_items = engine.scan_directory(temp_dir, recursive=True)
    assert len(recursive_items) == 3
    r_names = {i.name for i in recursive_items}
    assert "subfile.jpg" in r_names


def test_duplicate_engine_detection(temp_dir):
    # Create two identical files and one distinct file
    f1 = temp_dir / "original.pdf"
    f2 = temp_dir / "copy_of_original.pdf"
    f3 = temp_dir / "different.pdf"

    content = b"Identical binary bytes for duplicate test"
    f1.write_bytes(content)
    f2.write_bytes(content)
    f3.write_bytes(b"Different content with another size altogether")

    items = [
        MetadataEngine.create_file_item(f1, root_path=temp_dir),
        MetadataEngine.create_file_item(f2, root_path=temp_dir),
        MetadataEngine.create_file_item(f3, root_path=temp_dir),
    ]

    duplicates = DuplicateEngine.find_duplicates(items)
    # Should detect 1 hash group containing 2 files
    assert len(duplicates) == 1
    duplicate_group = list(duplicates.values())[0]
    assert len(duplicate_group) == 2
    dup_names = {item.name for item in duplicate_group}
    assert "original.pdf" in dup_names
    assert "copy_of_original.pdf" in dup_names
