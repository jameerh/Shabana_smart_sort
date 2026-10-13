"""Unit tests for the rule evaluation engine."""
import pytest
from datetime import datetime, timedelta
from pathlib import Path

from shabana_smart_sort.domain.enums import (
    ConditionTarget,
    ConditionOperator,
    LogicalOperator,
    FileCategory,
)
from shabana_smart_sort.domain.models import FileItem
from shabana_smart_sort.domain.rule_schema import Rule, RuleCondition, RuleAction
from shabana_smart_sort.engines.rule_engine import RuleEngine


def create_dummy_item(
    name: str = "document.pdf",
    size: int = 1024,
    category: FileCategory = FileCategory.DOCUMENT,
    days_ago: int = 2,
) -> FileItem:
    p = Path(f"/test/{name}")
    mod_time = datetime.now() - timedelta(days=days_ago)
    return FileItem(
        path=p,
        name=name,
        stem=p.stem,
        extension=p.suffix.lower(),
        size_bytes=size,
        category=category,
        created_at=mod_time,
        modified_at=mod_time,
        accessed_at=mod_time,
    )


def test_extension_matching_case_insensitive():
    engine = RuleEngine()
    rule = Rule(
        name="PDF Rule",
        conditions=[
            RuleCondition(
                target=ConditionTarget.EXTENSION,
                operator=ConditionOperator.IS_ONE_OF,
                value=[".pdf"],
            )
        ]
    )

    item1 = create_dummy_item("contract.pdf")
    matched1, _ = engine.evaluate_rule(rule, item1)
    assert matched1 is True

    item2 = create_dummy_item("CONTRACT.PDF")
    matched2, _ = engine.evaluate_rule(rule, item2)
    assert matched2 is True

    item3 = create_dummy_item("image.png")
    matched3, _ = engine.evaluate_rule(rule, item3)
    assert matched3 is False


def test_filename_string_operations():
    engine = RuleEngine()

    # Starts with
    r_starts = Rule(
        name="Invoice Prefix",
        conditions=[
            RuleCondition(
                target=ConditionTarget.FILENAME,
                operator=ConditionOperator.STARTS_WITH,
                value="INV_",
            )
        ]
    )
    assert engine.evaluate_rule(r_starts, create_dummy_item("INV_2026_01.pdf"))[0] is True
    assert engine.evaluate_rule(r_starts, create_dummy_item("RECEIPT_INV.pdf"))[0] is False

    # Regex
    r_regex = Rule(
        name="Tax Pattern",
        conditions=[
            RuleCondition(
                target=ConditionTarget.FILENAME,
                operator=ConditionOperator.MATCHES_REGEX,
                value=r"TAX_\d{4}",
            )
        ]
    )
    assert engine.evaluate_rule(r_regex, create_dummy_item("TAX_2026_receipt.pdf"))[0] is True
    assert engine.evaluate_rule(r_regex, create_dummy_item("TAX_receipt.pdf"))[0] is False


def test_logical_operators_all_and_any():
    engine = RuleEngine()

    rule_all = Rule(
        name="Both PDF and Starts with INV",
        logical_op=LogicalOperator.ALL,
        conditions=[
            RuleCondition(target=ConditionTarget.EXTENSION, operator=ConditionOperator.IS_ONE_OF, value=[".pdf"]),
            RuleCondition(target=ConditionTarget.FILENAME, operator=ConditionOperator.STARTS_WITH, value="INV"),
        ]
    )

    # Both match -> True
    assert engine.evaluate_rule(rule_all, create_dummy_item("INV_file.pdf"))[0] is True
    # Only extension matches -> False
    assert engine.evaluate_rule(rule_all, create_dummy_item("OTHER_file.pdf"))[0] is False

    rule_any = Rule(
        name="Either PDF or Starts with INV",
        logical_op=LogicalOperator.ANY,
        conditions=[
            RuleCondition(target=ConditionTarget.EXTENSION, operator=ConditionOperator.IS_ONE_OF, value=[".pdf"]),
            RuleCondition(target=ConditionTarget.FILENAME, operator=ConditionOperator.STARTS_WITH, value="INV"),
        ]
    )
    # Only prefix matches -> True
    assert engine.evaluate_rule(rule_any, create_dummy_item("INV_file.png"))[0] is True
    # Neither matches -> False
    assert engine.evaluate_rule(rule_any, create_dummy_item("OTHER.png"))[0] is False


def test_date_conditions():
    engine = RuleEngine()

    rule_recent = Rule(
        name="Last 7 Days",
        conditions=[
            RuleCondition(
                target=ConditionTarget.DATE_MODIFIED,
                operator=ConditionOperator.DATE_IN_LAST_DAYS,
                value=7,
            )
        ]
    )

    item_fresh = create_dummy_item(days_ago=3)
    assert engine.evaluate_rule(rule_recent, item_fresh)[0] is True

    item_old = create_dummy_item(days_ago=30)
    assert engine.evaluate_rule(rule_recent, item_old)[0] is False


def test_rule_priority_first_match_wins():
    r1 = Rule(
        name="High Priority Rule",
        priority=10,
        conditions=[
            RuleCondition(target=ConditionTarget.EXTENSION, operator=ConditionOperator.IS_ONE_OF, value=[".pdf"])
        ],
        action=RuleAction(destination_template="HighPriority/")
    )
    r2 = Rule(
        name="Low Priority General Rule",
        priority=50,
        conditions=[
            RuleCondition(target=ConditionTarget.EXTENSION, operator=ConditionOperator.IS_ONE_OF, value=[".pdf"])
        ],
        action=RuleAction(destination_template="LowPriority/")
    )

    # Initialize engine with both
    engine = RuleEngine(rules=[r2, r1])  # out of order

    res = engine.evaluate_file(create_dummy_item("doc.pdf"))
    assert res.is_matched is True
    assert res.rule.name == "High Priority Rule"
    assert res.rule.priority == 10
