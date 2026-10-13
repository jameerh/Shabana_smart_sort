"""Guarded undo service for reversing file operations honestly and safely."""
import os
from pathlib import Path
from typing import List, Tuple, Optional
import logging

from shabana_smart_sort.domain.enums import (
    ActionType,
    OperationStatus,
    CollisionPolicy,
)
from shabana_smart_sort.domain.operation_models import JournalEntry
from shabana_smart_sort.repositories.operation_repository import OperationRepository
from shabana_smart_sort.services.conflict_resolver import ConflictResolver
from shabana_smart_sort.services.safe_file_ops import SafeFileOperationService

logger = logging.getLogger("ShabanaSmartSort.Undo")


class UndoService:
    """Restores files to original locations without overwriting newer files."""

    def __init__(self, op_repo: OperationRepository, safe_ops: SafeFileOperationService):
        self.op_repo = op_repo
        self.safe_ops = safe_ops

    def undo_entry(self, entry: JournalEntry) -> Tuple[bool, str]:
        """
        Reverses a single journaled operation.
        Returns (success: bool, message: str).
        """
        if entry.status != OperationStatus.SUCCEEDED:
            return False, f"Cannot undo entry with status: {entry.status.value}"

        if not entry.can_undo:
            return False, "This entry is not eligible for undo"

        curr_file = Path(entry.destination_path)
        orig_file = Path(entry.source_path)

        # 1. Destination file (the moved file) must currently exist
        if not curr_file.exists():
            entry.can_undo = False
            entry.undo_status = "Destination file no longer exists"
            self.op_repo.update_journal_entry(entry)
            return False, f"File to restore no longer exists at: {curr_file}"

        try:
            if entry.action == ActionType.MOVE:
                # Check if original path is currently occupied
                target_path = orig_file
                if target_path.exists():
                    # Conflict: another file was created or placed at the original location
                    # Resolve using auto-rename to prevent data loss
                    target_path, _, _ = ConflictResolver.resolve_destination_collision(
                        target_path,
                        policy=CollisionPolicy.RENAME_NEW,
                        planned_destinations=set(),
                    )

                target_path.parent.mkdir(parents=True, exist_ok=True)
                same_vol = self.safe_ops.is_same_volume(curr_file, target_path)

                if same_vol:
                    os.replace(curr_file, target_path)
                else:
                    # Cross-volume reverse move
                    import shutil
                    shutil.copy2(curr_file, target_path)
                    os.unlink(curr_file)

                entry.mark_reverted()
                entry.undo_status = f"Restored to {target_path}"
                self.op_repo.update_journal_entry(entry)
                return True, f"Successfully restored to {target_path.name}"

            elif entry.action == ActionType.COPY:
                # To undo a copy, we remove the created duplicate copy
                if curr_file.exists():
                    os.unlink(curr_file)
                entry.mark_reverted()
                entry.undo_status = "Removed copied file"
                self.op_repo.update_journal_entry(entry)
                return True, "Removed copied duplicate"

            return False, "Unsupported action for undo"

        except Exception as e:
            msg = f"Failed to undo operation: {e}"
            logger.error(msg, exc_info=True)
            entry.undo_status = msg
            self.op_repo.update_journal_entry(entry)
            return False, msg

    def undo_job(self, job_id: str) -> Tuple[int, int, List[str]]:
        """
        Reverses all succeeded operations of a sort job in reverse chronological order.
        Returns (succeeded_count, failed_count, messages).
        """
        entries = self.op_repo.get_journal_entries_for_job(job_id)
        # Reverse order so last moved is first restored
        entries = [e for e in reversed(entries) if e.status == OperationStatus.SUCCEEDED and e.can_undo]

        succeeded = 0
        failed = 0
        messages = []

        for entry in entries:
            ok, msg = self.undo_entry(entry)
            if ok:
                succeeded += 1
            else:
                failed += 1
            messages.append(msg)

        return succeeded, failed, messages
