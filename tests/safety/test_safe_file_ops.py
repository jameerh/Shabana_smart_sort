"""Safety tests for file operations, verification, and collision handling."""
import uuid
from pathlib import Path

from shabana_smart_sort.domain.enums import (
    ActionType,
    OperationStatus,
    CollisionPolicy,
    VerificationLevel,
)
from shabana_smart_sort.domain.models import PlannedOperation
from shabana_smart_sort.services.conflict_resolver import ConflictResolver
from shabana_smart_sort.services.safe_file_ops import SafeFileOperationService


def test_safe_same_volume_move(temp_dir):
    src_file = temp_dir / "original.txt"
    src_file.write_text("Safe move data content", encoding="utf-8")
    dst_file = temp_dir / "target_sub" / "moved.txt"

    op = PlannedOperation(
        id=str(uuid.uuid4()),
        sort_job_id="test_job",
        source_path=str(src_file),
        destination_path=str(dst_file),
        original_destination_path=str(dst_file),
        action=ActionType.MOVE,
        file_size=src_file.stat().st_size,
    )

    service = SafeFileOperationService(verification_level=VerificationLevel.SIZE_ONLY)
    journal = service.execute_operation(op)

    assert journal.status == OperationStatus.SUCCEEDED
    assert dst_file.exists()
    assert not src_file.exists()
    assert dst_file.read_text(encoding="utf-8") == "Safe move data content"


def test_safe_copy_preserves_source(temp_dir):
    src_file = temp_dir / "source_copy.txt"
    src_file.write_text("Keep original intact", encoding="utf-8")
    dst_file = temp_dir / "copies" / "destination_copy.txt"

    op = PlannedOperation(
        id=str(uuid.uuid4()),
        sort_job_id="test_job",
        source_path=str(src_file),
        destination_path=str(dst_file),
        original_destination_path=str(dst_file),
        action=ActionType.COPY,
        file_size=src_file.stat().st_size,
    )

    service = SafeFileOperationService()
    journal = service.execute_operation(op)

    assert journal.status == OperationStatus.SUCCEEDED
    assert dst_file.exists()
    assert src_file.exists()  # Source preserved!


def test_collision_auto_rename_policy(temp_dir):
    # Pre-create an existing file at destination
    dest = temp_dir / "document.pdf"
    dest.write_text("Existing file", encoding="utf-8")

    # ConflictResolver should suggest "document (1).pdf"
    resolved_path, had_collision, should_skip = ConflictResolver.resolve_destination_collision(
        dest_path=dest,
        policy=CollisionPolicy.RENAME_NEW,
        planned_destinations=set(),
    )

    assert had_collision is True
    assert should_skip is False
    assert resolved_path.name == "document (1).pdf"


def test_missing_source_fails_cleanly(temp_dir):
    non_existent = temp_dir / "ghost_file.txt"
    dest = temp_dir / "destination.txt"

    op = PlannedOperation(
        id=str(uuid.uuid4()),
        sort_job_id="test_job",
        source_path=str(non_existent),
        destination_path=str(dest),
        original_destination_path=str(dest),
        action=ActionType.MOVE,
        file_size=100,
    )

    service = SafeFileOperationService()
    journal = service.execute_operation(op)

    assert journal.status == OperationStatus.FAILED
    assert "no longer exists" in journal.error_message
