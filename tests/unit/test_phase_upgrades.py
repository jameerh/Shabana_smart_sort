"""Unit tests for Phase 1, 2, and 3: Dynamic Presets, Compound Rules, and Content/OCR Indexing."""
import pytest
from datetime import datetime, timezone
from pathlib import Path

from shabana_smart_sort.domain.enums import (
    ConditionTarget,
    ConditionOperator,
    LogicalOperator,
    FileCategory,
)
from shabana_smart_sort.domain.models import FileItem
from shabana_smart_sort.domain.rule_schema import Rule, RuleCondition, ConditionGroup, RuleAction
from shabana_smart_sort.engines.rule_engine import RuleEngine
from shabana_smart_sort.engines.content_engine import ContentEngine
from shabana_smart_sort.infrastructure.database import DatabaseManager
from shabana_smart_sort.repositories.rule_repository import RuleRepository


def test_compound_and_or_condition_groups():
    """Verifies (A AND B) OR (C AND D) compound condition evaluation."""
    # Group 1: PDF AND size > 1000
    grp1 = ConditionGroup(
        logical_op=LogicalOperator.ALL,
        conditions=[
            RuleCondition(target=ConditionTarget.EXTENSION, operator=ConditionOperator.EQUALS, value=".pdf"),
            RuleCondition(target=ConditionTarget.SIZE_BYTES, operator=ConditionOperator.GREATER_THAN, value=1000),
        ]
    )

    # Group 2: Images (jpg/png) AND filename contains "satbara"
    grp2 = ConditionGroup(
        logical_op=LogicalOperator.ALL,
        conditions=[
            RuleCondition(target=ConditionTarget.EXTENSION, operator=ConditionOperator.IS_ONE_OF, value=[".jpg", ".png"]),
            RuleCondition(target=ConditionTarget.FILENAME, operator=ConditionOperator.CONTAINS, value="satbara"),
        ]
    )

    # Rule combines Group 1 OR Group 2
    rule = Rule(
        name="Compound Tax Documents",
        logical_op=LogicalOperator.ANY,
        condition_groups=[grp1, grp2],
        action=RuleAction(destination_template="Organized/Taxes/"),
    )

    engine = RuleEngine([rule])

    # Case 1: PDF > 1000 bytes -> Matches Group 1
    pdf_match = FileItem(
        path=Path("tax.pdf"), name="tax.pdf", stem="tax", extension=".pdf",
        size_bytes=5000, category=FileCategory.DOCUMENT,
        created_at=datetime.now(timezone.utc), modified_at=datetime.now(timezone.utc), accessed_at=datetime.now(timezone.utc)
    )
    res = engine.evaluate_file(pdf_match)
    assert res.is_matched is True

    # Case 2: PDF <= 1000 bytes (e.g. 500 bytes) -> Fails Group 1 and Group 2 -> Unmatched
    pdf_small = FileItem(
        path=Path("small.pdf"), name="small.pdf", stem="small", extension=".pdf",
        size_bytes=500, category=FileCategory.DOCUMENT,
        created_at=datetime.now(timezone.utc), modified_at=datetime.now(timezone.utc), accessed_at=datetime.now(timezone.utc)
    )
    res = engine.evaluate_file(pdf_small)
    assert res.is_matched is False

    # Case 3: JPG with 'satbara' in filename -> Matches Group 2
    img_match = FileItem(
        path=Path("satbara_7_12.jpg"), name="satbara_7_12.jpg", stem="satbara_7_12", extension=".jpg",
        size_bytes=300, category=FileCategory.IMAGE,
        created_at=datetime.now(timezone.utc), modified_at=datetime.now(timezone.utc), accessed_at=datetime.now(timezone.utc)
    )
    res = engine.evaluate_file(img_match)
    assert res.is_matched is True


def test_rule_repository_condition_group_sqlite_persistence(tmp_path):
    """Verifies that ConditionGroups and legacy conditions are stored and reloaded accurately from SQLite."""
    db_file = tmp_path / "test_groups.db"
    db_mgr = DatabaseManager(db_file)
    repo = RuleRepository(db_mgr)

    grp1 = ConditionGroup(
        logical_op=LogicalOperator.ALL,
        conditions=[
            RuleCondition(target=ConditionTarget.EXTENSION, operator=ConditionOperator.EQUALS, value=".pdf"),
            RuleCondition(target=ConditionTarget.FILENAME, operator=ConditionOperator.STARTS_WITH, value="Invoice"),
        ]
    )
    grp2 = ConditionGroup(
        logical_op=LogicalOperator.ANY,
        conditions=[
            RuleCondition(target=ConditionTarget.EXTENSION, operator=ConditionOperator.EQUALS, value=".docx"),
            RuleCondition(target=ConditionTarget.EXTENSION, operator=ConditionOperator.EQUALS, value=".xlsx"),
        ]
    )

    new_rule = Rule(
        name="Business Documents Grouped",
        logical_op=LogicalOperator.ANY,
        condition_groups=[grp1, grp2],
        action=RuleAction(destination_template="Organized/Business/"),
    )

    repo.save(new_rule)

    # Reload from DB
    reloaded = repo.get_by_id(new_rule.id)
    assert reloaded is not None
    assert reloaded.name == "Business Documents Grouped"
    assert len(reloaded.condition_groups) == 2
    assert reloaded.condition_groups[0].logical_op == LogicalOperator.ALL
    assert len(reloaded.condition_groups[0].conditions) == 2
    assert reloaded.condition_groups[1].logical_op == LogicalOperator.ANY
    assert len(reloaded.condition_groups[1].conditions) == 2


def test_content_engine_text_extraction_and_caching(tmp_path):
    """Verifies ContentEngine extracts text and correctly utilizes SQLite cache."""
    db_file = tmp_path / "test_content.db"
    db_mgr = DatabaseManager(db_file)
    content_engine = ContentEngine(db_mgr)

    # Create sample text file
    sample_file = tmp_path / "sample_contract.txt"
    sample_file.write_text("Confidential Agronomy Agreement 2026 for Shabana Farms.", encoding="utf-8")

    stat = sample_file.stat()
    mod_time = datetime.fromtimestamp(stat.st_mtime, timezone.utc)

    # First extraction - uncached
    text1, ocr1 = content_engine.get_or_extract_content(sample_file, mod_time, stat.st_size)
    assert "Shabana Farms" in text1

    # Second extraction - should hit SQLite cache
    text2, ocr2 = content_engine.get_or_extract_content(sample_file, mod_time, stat.st_size)
    assert text2 == text1


def test_file_content_rule_matching(tmp_path):
    """Verifies RuleEngine evaluating ConditionTarget.FILE_CONTENT."""
    db_file = tmp_path / "test_content_rule.db"
    db_mgr = DatabaseManager(db_file)
    content_engine = ContentEngine(db_mgr)

    rule = Rule(
        name="Identify Agronomy Contracts",
        logical_op=LogicalOperator.ALL,
        conditions=[
            RuleCondition(
                target=ConditionTarget.FILE_CONTENT,
                operator=ConditionOperator.CONTAINS,
                value="Agronomy Agreement"
            )
        ],
        action=RuleAction(destination_template="Organized/Contracts/")
    )
    engine = RuleEngine([rule])

    # Sample file with matching content
    contract_file = tmp_path / "doc_101.txt"
    contract_file.write_text("Official Agronomy Agreement between parties.", encoding="utf-8")
    stat = contract_file.stat()
    item = FileItem(
        path=contract_file, name=contract_file.name, stem=contract_file.stem, extension=".txt",
        size_bytes=stat.st_size, category=FileCategory.DOCUMENT,
        created_at=datetime.now(timezone.utc), modified_at=datetime.fromtimestamp(stat.st_mtime, timezone.utc),
        accessed_at=datetime.now(timezone.utc)
    )

    # Enrich item via content_engine
    content_engine.enrich_file_item(item)

    assert item.content_text is not None
    assert "Agronomy Agreement" in item.content_text

    match_res = engine.evaluate_file(item)
    assert match_res.is_matched is True
    assert match_res.rule.name == "Identify Agronomy Contracts"
