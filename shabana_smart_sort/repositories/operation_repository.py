"""Repository for planned operations, sort jobs, and audit journal entries."""
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any
import logging

from shabana_smart_sort.domain.enums import (
    ActionType,
    CollisionPolicy,
    OperationStatus,
    JobStatus,
)
from shabana_smart_sort.domain.models import PlannedOperation, SortJob
from shabana_smart_sort.domain.operation_models import JournalEntry
from shabana_smart_sort.infrastructure.database import DatabaseManager

logger = logging.getLogger("ShabanaSmartSort.OperationRepo")


class OperationRepository:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def create_sort_job(self, job: SortJob) -> None:
        conn = self.db.get_connection()
        with conn:
            conn.execute("""
                INSERT INTO sort_jobs (id, scan_job_id, source_folder, target_folder, is_dry_run, total_operations, succeeded_operations, failed_operations, skipped_operations, status, started_at, finished_at, journal_notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job.id,
                job.scan_job_id,
                job.source_folder,
                job.target_folder,
                1 if job.is_dry_run else 0,
                job.total_operations,
                job.succeeded_operations,
                job.failed_operations,
                job.skipped_operations,
                job.status.value,
                job.started_at.isoformat(),
                job.finished_at.isoformat() if job.finished_at else None,
                job.journal_notes,
            ))

    def update_sort_job(self, job: SortJob) -> None:
        conn = self.db.get_connection()
        with conn:
            conn.execute("""
                UPDATE sort_jobs SET
                    total_operations = ?,
                    succeeded_operations = ?,
                    failed_operations = ?,
                    skipped_operations = ?,
                    status = ?,
                    finished_at = ?,
                    journal_notes = ?
                WHERE id = ?
            """, (
                job.total_operations,
                job.succeeded_operations,
                job.failed_operations,
                job.skipped_operations,
                job.status.value,
                job.finished_at.isoformat() if job.finished_at else None,
                job.journal_notes,
                job.id,
            ))

    def get_sort_job(self, job_id: str) -> Optional[SortJob]:
        conn = self.db.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM sort_jobs WHERE id = ?", (job_id,))
        row = cur.fetchone()
        if not row:
            return None
        return SortJob(
            id=row["id"],
            scan_job_id=row["scan_job_id"],
            source_folder=row["source_folder"],
            target_folder=row["target_folder"],
            is_dry_run=bool(row["is_dry_run"]),
            total_operations=row["total_operations"],
            succeeded_operations=row["succeeded_operations"],
            failed_operations=row["failed_operations"],
            skipped_operations=row["skipped_operations"],
            status=JobStatus(row["status"]),
            started_at=datetime.fromisoformat(row["started_at"]),
            finished_at=datetime.fromisoformat(row["finished_at"]) if row["finished_at"] else None,
            journal_notes=row["journal_notes"],
        )

    def get_recent_jobs(self, limit: int = 50) -> List[SortJob]:
        conn = self.db.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM sort_jobs ORDER BY started_at DESC LIMIT ?", (limit,))
        rows = cur.fetchall()
        jobs = []
        for row in rows:
            jobs.append(SortJob(
                id=row["id"],
                scan_job_id=row["scan_job_id"],
                source_folder=row["source_folder"],
                target_folder=row["target_folder"],
                is_dry_run=bool(row["is_dry_run"]),
                total_operations=row["total_operations"],
                succeeded_operations=row["succeeded_operations"],
                failed_operations=row["failed_operations"],
                skipped_operations=row["skipped_operations"],
                status=JobStatus(row["status"]),
                started_at=datetime.fromisoformat(row["started_at"]),
                finished_at=datetime.fromisoformat(row["finished_at"]) if row["finished_at"] else None,
                journal_notes=row["journal_notes"],
            ))
        return jobs

    def save_planned_operations(self, ops: List[PlannedOperation]) -> None:
        conn = self.db.get_connection()
        with conn:
            for op in ops:
                conn.execute("""
                    INSERT INTO planned_operations (
                        id, sort_job_id, source_path, destination_path, original_destination_path,
                        action, matched_rule_id, matched_rule_name, match_reason, is_valid,
                        validation_error, collision_detected, collision_policy_applied,
                        selected_for_execution, file_size, status, executed_at, error_message, is_cross_volume
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        sort_job_id = excluded.sort_job_id,
                        destination_path = excluded.destination_path,
                        status = excluded.status,
                        selected_for_execution = excluded.selected_for_execution,
                        executed_at = excluded.executed_at,
                        error_message = excluded.error_message
                """, (
                    op.id,
                    op.sort_job_id,
                    op.source_path,
                    op.destination_path,
                    op.original_destination_path,
                    op.action.value,
                    op.matched_rule_id,
                    op.matched_rule_name,
                    op.match_reason,
                    1 if op.is_valid else 0,
                    op.validation_error,
                    1 if op.collision_detected else 0,
                    op.collision_policy_applied.value,
                    1 if op.selected_for_execution else 0,
                    op.file_size,
                    op.status.value,
                    op.executed_at.isoformat() if op.executed_at else None,
                    op.error_message,
                    1 if op.is_cross_volume else 0,
                ))

    def update_planned_operation_status(self, op_id: str, status: OperationStatus, error: Optional[str] = None) -> None:
        conn = self.db.get_connection()
        now_str = datetime.now(timezone.utc).isoformat()
        with conn:
            conn.execute("""
                UPDATE planned_operations SET
                    status = ?,
                    executed_at = ?,
                    error_message = ?
                WHERE id = ?
            """, (status.value, now_str, error, op_id))

    def create_journal_entry(self, entry: JournalEntry) -> None:
        conn = self.db.get_connection()
        with conn:
            # Ensure referenced sort_job exists for foreign key constraint
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM sort_jobs WHERE id = ?", (entry.sort_job_id,))
            if not cur.fetchone():
                conn.execute("""
                    INSERT INTO sort_jobs (id, source_folder, target_folder, status, started_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    entry.sort_job_id,
                    str(Path(entry.source_path).parent),
                    str(Path(entry.destination_path).parent),
                    JobStatus.COMPLETED.value,
                    entry.created_at.isoformat(),
                ))

            conn.execute("""
                INSERT INTO operation_journal (
                    id, operation_id, sort_job_id, source_path, destination_path, action,
                    status, file_size, is_cross_volume, created_at, executed_at, reverted_at,
                    sha256_before, sha256_after, temp_path, error_message, can_undo, undo_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.id,
                entry.operation_id,
                entry.sort_job_id,
                entry.source_path,
                entry.destination_path,
                entry.action.value,
                entry.status.value,
                entry.file_size,
                1 if entry.is_cross_volume else 0,
                entry.created_at.isoformat(),
                entry.executed_at.isoformat() if entry.executed_at else None,
                entry.reverted_at.isoformat() if entry.reverted_at else None,
                entry.sha256_before,
                entry.sha256_after,
                entry.temp_path,
                entry.error_message,
                1 if entry.can_undo else 0,
                entry.undo_status,
            ))

    def update_journal_entry(self, entry: JournalEntry) -> None:
        conn = self.db.get_connection()
        with conn:
            conn.execute("""
                UPDATE operation_journal SET
                    status = ?,
                    executed_at = ?,
                    reverted_at = ?,
                    sha256_after = ?,
                    error_message = ?,
                    can_undo = ?,
                    undo_status = ?
                WHERE id = ?
            """, (
                entry.status.value,
                entry.executed_at.isoformat() if entry.executed_at else None,
                entry.reverted_at.isoformat() if entry.reverted_at else None,
                entry.sha256_after,
                entry.error_message,
                1 if entry.can_undo else 0,
                entry.undo_status,
                entry.id,
            ))

    def get_journal_entries_for_job(self, job_id: str) -> List[JournalEntry]:
        conn = self.db.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM operation_journal WHERE sort_job_id = ? ORDER BY rowid ASC", (job_id,))
        rows = cur.fetchall()
        entries = []
        for row in rows:
            entries.append(self._row_to_journal(row))
        return entries

    def get_all_journal_entries(self, limit: int = 200) -> List[JournalEntry]:
        conn = self.db.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM operation_journal ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = cur.fetchall()
        return [self._row_to_journal(r) for r in rows]

    def _row_to_journal(self, row: Any) -> JournalEntry:
        return JournalEntry(
            id=row["id"],
            operation_id=row["operation_id"],
            sort_job_id=row["sort_job_id"],
            source_path=row["source_path"],
            destination_path=row["destination_path"],
            action=ActionType(row["action"]),
            status=OperationStatus(row["status"]),
            file_size=row["file_size"],
            is_cross_volume=bool(row["is_cross_volume"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            executed_at=datetime.fromisoformat(row["executed_at"]) if row["executed_at"] else None,
            reverted_at=datetime.fromisoformat(row["reverted_at"]) if row["reverted_at"] else None,
            sha256_before=row["sha256_before"],
            sha256_after=row["sha256_after"],
            temp_path=row["temp_path"],
            error_message=row["error_message"],
            can_undo=bool(row["can_undo"]),
            undo_status=row["undo_status"],
        )
