"""End-to-end integration tests validating scan, preview, sort, and undo workflows."""
import pytest
from pathlib import Path

from shabana_smart_sort.domain.enums import CollisionPolicy, OperationStatus, JobStatus


def test_full_sort_and_undo_lifecycle(container, sample_files, temp_dir):
    src_dir, items = sample_files
    target_root = temp_dir / "Organized"
    target_root.mkdir(parents=True, exist_ok=True)

    # 1. Rules should be initialized by default in container
    rules = container.rule_workflow.get_all_rules(enabled_only=True)
    assert len(rules) >= 5

    # 2. Preview workflow
    preview_report = container.preview_workflow.generate_preview(
        files=items,
        rules=rules,
        target_root=target_root,
        default_collision_policy=CollisionPolicy.RENAME_NEW,
    )

    assert preview_report.total_files == len(items)
    # Most files (pdf, jpg, zip, exe, docx, py) should match default rules
    assert preview_report.matched_count >= 5
    assert preview_report.sufficient_disk_space is True

    # 3. Dry-Run execution
    dry_run_report = container.sort_workflow.execute_sort(
        operations=preview_report.operations,
        source_folder=src_dir,
        target_folder=target_root,
        is_dry_run=True,
    )
    assert dry_run_report.is_dry_run is True
    assert dry_run_report.failed == 0
    # In dry-run, files must NOT have moved
    assert (src_dir / "contract_2026.pdf").exists()

    # 4. Live Execution
    live_report = container.sort_workflow.execute_sort(
        operations=preview_report.operations,
        source_folder=src_dir,
        target_folder=target_root,
        is_dry_run=False,
    )
    assert live_report.is_dry_run is False
    assert live_report.succeeded >= 5

    # Verify moved files exist in organized hierarchy
    organized_pdf = list(target_root.rglob("*.pdf"))
    assert len(organized_pdf) >= 1
    assert not (src_dir / "contract_2026.pdf").exists()

    # 5. Undo the entire batch
    succeeded_undo, failed_undo, msgs = container.undo_workflow.undo_batch(live_report.job_id)
    assert succeeded_undo == live_report.succeeded
    assert failed_undo == 0

    # Verify file is restored back to src_dir
    assert (src_dir / "contract_2026.pdf").exists()
