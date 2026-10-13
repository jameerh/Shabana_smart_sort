"""Pytest fixtures for Shabana Smart Sort tests."""
import pytest
from pathlib import Path
from datetime import datetime, timezone
import tempfile
import shutil

from shabana_smart_sort.app.dependency_container import DependencyContainer
from shabana_smart_sort.domain.enums import FileCategory
from shabana_smart_sort.domain.models import FileItem
from shabana_smart_sort.engines.metadata_engine import MetadataEngine


@pytest.fixture
def temp_dir():
    """Provides an isolated temporary directory for testing."""
    td = tempfile.mkdtemp(prefix="smart_sort_test_")
    path = Path(td)
    yield path
    shutil.rmtree(td, ignore_errors=True)


@pytest.fixture
def container(temp_dir):
    """Provides a fully wired test DependencyContainer in a temp directory."""
    data_dir = temp_dir / "app_data"
    data_dir.mkdir(parents=True, exist_ok=True)
    cont = DependencyContainer(data_dir)
    return cont


@pytest.fixture
def sample_files(temp_dir):
    """Creates a realistic variety of mock files in a source directory."""
    src = temp_dir / "mock_downloads"
    src.mkdir(parents=True, exist_ok=True)

    # 1. PDF
    pdf_file = src / "contract_2026.pdf"
    pdf_file.write_text("Mock PDF content", encoding="utf-8")

    # 2. Uppercase JPG
    img_file = src / "VACATION_PHOTO.JPG"
    img_file.write_bytes(b"\xFF\xD8\xFF\xE0" + b"\x00" * 100)

    # 3. Zip archive
    zip_file = src / "backup_data.zip"
    zip_file.write_bytes(b"PK\x03\x04" + b"\x00" * 50)

    # 4. Installer
    exe_file = src / "installer_setup.exe"
    exe_file.write_bytes(b"MZ" + b"\x00" * 200)

    # 5. Office Doc
    doc_file = src / "quarterly_report.docx"
    doc_file.write_text("Mock Docx content", encoding="utf-8")

    # 6. Python script
    py_file = src / "automation_script.py"
    py_file.write_text("print('hello')", encoding="utf-8")

    # 7. Unmatched random file
    xyz_file = src / "mystery.xyz123"
    xyz_file.write_text("Unknown format", encoding="utf-8")

    # Return list of FileItems
    items = []
    for f in src.iterdir():
        items.append(MetadataEngine.create_file_item(f, root_path=src))

    return src, items
