"""Tests for RuleWorkflow, cloning, validation, and JSON import/export."""
from pathlib import Path
from shabana_smart_sort.domain.rule_schema import Rule, RuleCondition, RuleAction
from shabana_smart_sort.domain.enums import ConditionTarget, ConditionOperator


def test_rule_workflow_crud_and_clone(container):
    wf = container.rule_workflow

    # 1. Create rule
    rule = Rule(
        name="Receipts",
        description="Scanned store receipts",
        priority=35,
        conditions=[
            RuleCondition(target=ConditionTarget.FILENAME, operator=ConditionOperator.CONTAINS, value="receipt")
        ],
        action=RuleAction(destination_template="Organized/Receipts/")
    )
    ok, err = wf.save_rule(rule)
    assert ok is True
    assert err is None

    # Verify rule retrieved
    saved = container.rule_repo.get_by_id(rule.id)
    assert saved is not None
    assert saved.name == "Receipts"

    # 2. Clone rule
    cloned = wf.clone_rule(rule.id)
    assert cloned is not None
    assert cloned.id != rule.id
    assert "Copy of Receipts" in cloned.name

    # 3. Validation failure test
    invalid_rule = Rule(
        name="Invalid Rule",
        conditions=[
            RuleCondition(target=ConditionTarget.FILENAME, operator=ConditionOperator.CONTAINS, value="")
        ],
        action=RuleAction(destination_template="")
    )
    ok_inv, err_inv = wf.save_rule(invalid_rule)
    assert ok_inv is False
    assert ("Destination template cannot be empty" in err_inv or "empty value" in err_inv)


def test_rule_json_export_and_import(container, temp_dir):
    wf = container.rule_workflow

    # Export
    export_file = temp_dir / "rules_backup.json"
    json_str = wf.export_rules_json(export_file)
    assert export_file.exists()
    assert "format_version" in json_str

    # Import
    imported_count, errors = wf.import_rules_json(str(export_file))
    assert errors == []
    assert imported_count > 0


def test_audit_report_export(container, temp_dir, sample_files):
    src_dir, items = sample_files
    target_root = temp_dir / "Organized"

    # Execute a small sort to populate the journal
    report = container.preview_workflow.generate_preview(
        files=items[:3],
        rules=container.rule_workflow.get_all_rules(enabled_only=True),
        target_root=target_root,
    )
    container.sort_workflow.execute_sort(
        operations=report.operations,
        source_folder=src_dir,
        target_folder=target_root,
        is_dry_run=False,
    )

    csv_path = temp_dir / "audit.csv"
    json_path = temp_dir / "audit.json"

    container.undo_workflow.export_report_csv(csv_path)
    container.undo_workflow.export_report_json(json_path)

    assert csv_path.exists()
    assert csv_path.stat().st_size > 0
    assert "Source Path" in csv_path.read_text(encoding="utf-8")

    assert json_path.exists()
    assert json_path.stat().st_size > 0
    assert "sort_job_id" in json_path.read_text(encoding="utf-8")


def test_selective_rule_enablement_and_isolation(container, sample_files, temp_dir):
    """Verifies that isolating a single rule only matches files matching that rule."""
    src_dir, items = sample_files
    wf = container.rule_workflow

    all_rules = wf.get_all_rules()
    satbara_rule = next((r for r in all_rules if "Satbara" in r.name), None)
    assert satbara_rule is not None

    # Enable ONLY Satbara rule, disabling all others
    for r in all_rules:
        wf.set_rule_enabled(r.id, r.id == satbara_rule.id)

    active_rules = wf.get_all_rules(enabled_only=True)
    assert len(active_rules) == 1
    assert active_rules[0].id == satbara_rule.id

    # Generate preview with sample files
    preview = container.preview_workflow.generate_preview(
        files=items,
        rules=active_rules,
        target_root=temp_dir / "Organized",
    )

    # Only files with satbara in filename should be matched
    matched_ops = [op for op in preview.operations if op.matched_rule_id == satbara_rule.id]
    for op in matched_ops:
        assert "satbara" in op.source_path.lower()

    # Other files (like generic pdfs, images, etc.) MUST be marked unmatched and unselected
    unmatched_ops = [op for op in preview.operations if op.matched_rule_id is None]
    for op in unmatched_ops:
        assert "satbara" not in op.source_path.lower()
        assert op.selected_for_execution is False

