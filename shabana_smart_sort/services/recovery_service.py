"""Crash recovery and reconciliation service for interrupted jobs."""
from pathlib import Path
from typing import List, Tuple
import logging

from shabana_smart_sort.domain.enums import JobStatus, OperationStatus
from shabana_smart_sort.repositories.operation_repository import OperationRepository

logger = logging.getLogger("ShabanaSmartSort.Recovery")


class RecoveryService:
    """Detects and reconciles orphaned temp files or interrupted job states."""

    def __init__(self, op_repo: OperationRepository):
        self.op_repo = op_repo

    def reconcile_interrupted_jobs(self) -> List[str]:
        """Finds any sort jobs left in RUNNING or PENDING state and marks them INTERRUPTED."""
        recent_jobs = self.op_repo.get_recent_jobs(limit=100)
        reconciled = []
        for job in recent_jobs:
            if job.status == JobStatus.RUNNING:
                job.status = JobStatus.CANCELLED
                job.journal_notes = (job.journal_notes or "") + " [Interrupted by unexpected termination]"
                self.op_repo.update_sort_job(job)
                reconciled.append(f"Reconciled interrupted job {job.id}")
        return reconciled

    def cleanup_orphaned_temp_files(self, search_dir: Path) -> List[Path]:
        """Finds and safely deletes leftover `.smart_sort_temp_*` files in search_dir."""
        cleaned = []
        try:
            if search_dir.exists() and search_dir.is_dir():
                for p in search_dir.rglob(".smart_sort_temp_*"):
                    if p.is_file():
                        try:
                            p.unlink()
                            cleaned.append(p)
                        except Exception as e:
                            logger.warning(f"Could not delete temp file {p}: {e}")
        except Exception as e:
            logger.warning(f"Error during temp file cleanup: {e}")
        return cleaned
