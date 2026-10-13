"""Workflow for undoing operations and exporting audit history reports."""
import csv
import json
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
import logging

from shabana_smart_sort.domain.operation_models import JournalEntry
from shabana_smart_sort.repositories.operation_repository import OperationRepository
from shabana_smart_sort.services.undo_service import UndoService

logger = logging.getLogger("ShabanaSmartSort.UndoWorkflow")


class UndoWorkflow:
    """Manages undo actions and history reporting."""

    def __init__(self, op_repo: OperationRepository, undo_service: UndoService):
        self.op_repo = op_repo
        self.undo_service = undo_service

    def get_history(self, limit: int = 200) -> List[JournalEntry]:
        return self.op_repo.get_all_journal_entries(limit=limit)

    def get_recent_jobs(self, limit: int = 50):
        return self.op_repo.get_recent_jobs(limit=limit)

    def undo_operation(self, entry_id: str) -> Tuple[bool, str]:
        entries = self.op_repo.get_all_journal_entries(limit=500)
        target = next((e for e in entries if e.id == entry_id), None)
        if not target:
            return False, "Journal entry not found"
        return self.undo_service.undo_entry(target)

    def undo_batch(self, job_id: str) -> Tuple[int, int, List[str]]:
        return self.undo_service.undo_job(job_id)

    def export_report_csv(self, output_path: Path, limit: int = 500) -> None:
        """Exports the operation journal as a CSV report."""
        entries = self.op_repo.get_all_journal_entries(limit=limit)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "ID", "Job ID", "Action", "Status", "Source Path",
                "Destination Path", "File Size (Bytes)", "Cross Volume",
                "Executed At", "Can Undo", "Error Message"
            ])
            for e in entries:
                writer.writerow([
                    e.id,
                    e.sort_job_id,
                    e.action.value,
                    e.status.value,
                    e.source_path,
                    e.destination_path,
                    e.file_size,
                    e.is_cross_volume,
                    e.executed_at.isoformat() if e.executed_at else "",
                    e.can_undo,
                    e.error_message or "",
                ])

    def export_report_json(self, output_path: Path, limit: int = 500) -> None:
        """Exports the operation journal as a JSON report."""
        entries = self.op_repo.get_all_journal_entries(limit=limit)
        data = [
            {
                "id": e.id,
                "sort_job_id": e.sort_job_id,
                "action": e.action.value,
                "status": e.status.value,
                "source_path": e.source_path,
                "destination_path": e.destination_path,
                "file_size": e.file_size,
                "is_cross_volume": e.is_cross_volume,
                "created_at": e.created_at.isoformat(),
                "executed_at": e.executed_at.isoformat() if e.executed_at else None,
                "can_undo": e.can_undo,
                "error_message": e.error_message,
            }
            for e in entries
        ]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
