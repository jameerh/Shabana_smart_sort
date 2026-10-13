"""Repository for recording scan jobs and statistics."""
from datetime import datetime
from typing import List, Optional
import logging

from shabana_smart_sort.domain.enums import JobStatus
from shabana_smart_sort.domain.models import ScanJob
from shabana_smart_sort.infrastructure.database import DatabaseManager

logger = logging.getLogger("ShabanaSmartSort.ScanRepo")


class ScanRepository:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def create(self, job: ScanJob) -> None:
        conn = self.db.get_connection()
        with conn:
            conn.execute("""
                INSERT INTO scan_jobs (id, root_path, is_recursive, started_at, finished_at, total_files, total_size_bytes, status, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job.id,
                job.root_path,
                1 if job.is_recursive else 0,
                job.started_at.isoformat(),
                job.finished_at.isoformat() if job.finished_at else None,
                job.total_files,
                job.total_size_bytes,
                job.status.value,
                job.error_message,
            ))

    def update(self, job: ScanJob) -> None:
        conn = self.db.get_connection()
        with conn:
            conn.execute("""
                UPDATE scan_jobs SET
                    finished_at = ?,
                    total_files = ?,
                    total_size_bytes = ?,
                    status = ?,
                    error_message = ?
                WHERE id = ?
            """, (
                job.finished_at.isoformat() if job.finished_at else None,
                job.total_files,
                job.total_size_bytes,
                job.status.value,
                job.error_message,
                job.id,
            ))

    def get_latest(self) -> Optional[ScanJob]:
        conn = self.db.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM scan_jobs ORDER BY started_at DESC LIMIT 1")
        row = cur.fetchone()
        if not row:
            return None
        return ScanJob(
            id=row["id"],
            root_path=row["root_path"],
            is_recursive=bool(row["is_recursive"]),
            started_at=datetime.fromisoformat(row["started_at"]),
            finished_at=datetime.fromisoformat(row["finished_at"]) if row["finished_at"] else None,
            total_files=row["total_files"],
            total_size_bytes=row["total_size_bytes"],
            status=JobStatus(row["status"]),
            error_message=row["error_message"],
        )
