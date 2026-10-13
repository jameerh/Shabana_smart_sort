"""Tests for honest undo and crash recovery mechanisms."""
import uuid
from pathlib import Path

from shabana_smart_sort.domain.enums import (
    ActionType,
    OperationStatus,
    JobStatus,
)
from shabana_smart_sort.domain.models import PlannedOperation, SortJob
from shabana_smart_sort.domain.operation_models import JournalEntry
from shabana_smart_sort.services.undo_service import UndoService


def test_honest_undo_restores_file(container, temp_dir):
    src_file = temp_dir / "my_important_doc.pdf"
    src_file.write_text("Crucial business report", encoding="utf-8")
    dst_file = temp_dir / "Organized" / "PDFs" / "my_important_doc.pdf"

    # Step 1: Move file
    op = PlannedOperation(
        id=str(uuid.uuid4()),
        sort_job_id="test_job_1",
        source_path=str(src_file),
        destination_path=str(dst_file),
        original_destination_path=str(dst_file),
        action=ActionType.MOVE,
        file_size=src_file.stat().st_size,
    )

    journal = container.safe_ops.execute_operation(op)
    container.op_repo.create_journal_entry(journal)

    assert not src_file.exists()
    assert dst_file.exists()

    # Step 2: Undo
    ok, msg = container.undo_service.undo_entry(journal)
    assert ok is True
    assert src_file.exists()
    assert not dst_file.exists()
    assert src_file.read_text(encoding="utf-8") == "Crucial business report"
    assert journal.status == OperationStatus.REVERTED


def test_undo_with_occupied_original_path_avoids_overwrite(container, temp_dir):
    src_file = temp_dir / "statement.pdf"
    src_file.write_text("Original version", encoding="utf-8")
    dst_file = temp_dir / "Organized" / "statement.pdf"

    op = PlannedOperation(
        id=str(uuid.uuid4()),
        sort_job_id="test_job_2",
        source_path=str(src_file),
        destination_path=str(dst_file),
        original_destination_path=str(dst_file),
        action=ActionType.MOVE,
        file_size=src_file.stat().st_size,
    )

    journal = container.safe_ops.execute_operation(op)
    container.op_repo.create_journal_entry(journal)

    # Now simulate another file being placed at src_file before undo
    src_file.write_text("New file occupying original slot", encoding="utf-8")

    # Undo must NOT overwrite the new file
    ok, msg = container.undo_service.undo_entry(journal)
    assert ok is True
    # Original file is preserved
    assert src_file.read_text(encoding="utf-8") == "New file occupying original slot"

    # Restored file is placed with suffix (1)
    restored = temp_dir / "statement (1).pdf"
    assert restored.exists()
    assert restored.read_text(encoding="utf-8") == "Original version"


def test_crash_recovery_reconciliation(container):
    # Insert an interrupted job stuck in RUNNING state
    job = SortJob(
        id="interrupted_job_123",
        source_folder="/src",
        target_folder="/dst",
        status=JobStatus.RUNNING,
    )
    container.op_repo.create_sort_job(job)

    reconciled = container.recovery_service.reconcile_interrupted_jobs()
    assert len(reconciled) == 1

    updated = container.op_repo.get_sort_job("interrupted_job_123")
    assert updated.status == JobStatus.CANCELLED
    assert "Interrupted" in updated.journal_notes
