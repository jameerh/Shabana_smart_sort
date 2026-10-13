"""Unit tests for destination template resolution and directory traversal security."""
from pathlib import Path
from datetime import datetime

from shabana_smart_sort.domain.enums import FileCategory
from shabana_smart_sort.domain.models import FileItem
from shabana_smart_sort.domain.rule_schema import Rule, RuleAction
from shabana_smart_sort.engines.destination_engine import DestinationEngine


def test_destination_template_variables():
    base_root = Path("C:/Downloads/Organized")
    mod_date = datetime(2026, 10, 15)

    item = FileItem(
        path=Path("C:/Downloads/invoice.pdf"),
        name="invoice.pdf",
        stem="invoice",
        extension=".pdf",
        size_bytes=1000,
        category=FileCategory.DOCUMENT,
        created_at=mod_date,
        modified_at=mod_date,
        accessed_at=mod_date,
    )

    rule = Rule(
        name="Business Invoices",
        action=RuleAction(destination_template="PDFs/{year}/{month}/")
    )

    dest = DestinationEngine.resolve_destination(base_root, item, rule)
    assert "2026" in str(dest)
    assert "10" in str(dest)
    assert dest.name == "invoice.pdf"


def test_path_traversal_prevention():
    base_root = Path("C:/Downloads/Organized")
    mod_date = datetime.now()

    item = FileItem(
        path=Path("C:/Downloads/payload.exe"),
        name="payload.exe",
        stem="payload",
        extension=".exe",
        size_bytes=500,
        category=FileCategory.INSTALLER,
        created_at=mod_date,
        modified_at=mod_date,
        accessed_at=mod_date,
    )

    # Attack attempt: trying to escape to Windows directory using relative jumps
    rule = Rule(
        name="Attack Rule",
        action=RuleAction(destination_template="../../Windows/System32/")
    )

    dest = DestinationEngine.resolve_destination(base_root, item, rule)
    # Must NOT contain .. and must stay inside base_root
    dest_str = str(dest.resolve()).replace("\\", "/")
    base_str = str(base_root.resolve()).replace("\\", "/")
    assert dest_str.startswith(base_str)
