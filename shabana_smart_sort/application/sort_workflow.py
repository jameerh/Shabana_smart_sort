"""Execution workflow managing safe sort batches, progress events, and cancellation."""
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Callable, Optional
import logging

from shabana_smart_sort.domain.enums import (
    OperationStatus,
    JobStatus,
)
from shabana_smart_sort.domain.models import PlannedOperation, SortJob
from shabana_smart_sort.infrastructure.event_bus import (
    event_bus,
    SortProgressEvent,
    SortCompletedEvent,
)
from shabana_smart_sort.repositories.operation_repository import OperationRepository
from shabana_smart_sort.services.safe_file_ops import SafeFileOperationService

logger = logging.getLogger("ShabanaSmartSort.SortWorkflow")


class SortExecutionReport:
    def __init__(
        self,
        job_id: str,
        total: int,
        succeeded: int,
        failed: int,
        skipped: int,
        is_dry_run: bool,
    ):
        self.job_id = job_id
        self.total = total
        self.succeeded = succeeded
        self.failed = failed
        self.skipped = skipped
        self.is_dry_run = is_dry_run


class SortWorkflow:
    def __init__(
        self,
        op_repo: OperationRepository,
        safe_ops: SafeFileOperationService,
    ):
        self.op_repo = op_repo
        self.safe_ops = safe_ops

    def execute_sort(
        self,
        operations: List[PlannedOperation],
        source_folder: Path,
        target_folder: Path,
        is_dry_run: bool = True,
        scan_job_id: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int, str, str], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> SortExecutionReport:
        """Executes a batch of planned operations with safety checks and journaling."""
        selected_ops = [op for op in operations if op.selected_for_execution]
        total_count = len(selected_ops)

        job_id = str(uuid.uuid4())
        job = SortJob(
            id=job_id,
            scan_job_id=scan_job_id,
            source_folder=str(source_folder),
            target_folder=str(target_folder),
            is_dry_run=is_dry_run,
            total_operations=total_count,
            status=JobStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        )
        self.op_repo.create_sort_job(job)

        # Update sort_job_id on all operations and persist them
        for op in selected_ops:
            op.sort_job_id = job_id
        self.op_repo.save_planned_operations(selected_ops)

        succeeded = 0
        failed = 0
        skipped = 0

        for idx, op in enumerate(selected_ops, start=1):
            if cancel_check and cancel_check():
                logger.info(f"Sort execution cancelled by user after {idx-1} operations.")
                job.status = JobStatus.CANCELLED
                break

            filename = Path(op.source_path).name

            if is_dry_run:
                # Dry run: revalidate only
                valid, err = self.safe_ops.validate_preconditions(op)
                status_str = "Dry-Run OK" if valid else f"Dry-Run Failed: {err}"
                if valid:
                    succeeded += 1
                else:
                    failed += 1
                if progress_callback:
                    progress_callback(idx, total_count, filename, status_str)
                event_bus.publish(SortProgressEvent(idx, total_count, filename, status_str))
                continue

            # Live Execution
            try:
                journal_entry = self.safe_ops.execute_operation(op)
                self.op_repo.create_journal_entry(journal_entry)

                if journal_entry.status == OperationStatus.SUCCEEDED:
                    succeeded += 1
                    op_status = OperationStatus.SUCCEEDED
                    err_msg = None
                    status_text = "Success"
                else:
                    failed += 1
                    op_status = OperationStatus.FAILED
                    err_msg = journal_entry.error_message
                    status_text = f"Failed: {err_msg}"

                self.op_repo.update_planned_operation_status(op.id, op_status, err_msg)

                if progress_callback:
                    progress_callback(idx, total_count, filename, status_text)
                event_bus.publish(SortProgressEvent(idx, total_count, filename, status_text))

            except Exception as e:
                failed += 1
                err_text = f"Error: {e}"
                self.op_repo.update_planned_operation_status(op.id, OperationStatus.FAILED, err_text)
                if progress_callback:
                    progress_callback(idx, total_count, filename, err_text)
                event_bus.publish(SortProgressEvent(idx, total_count, filename, err_text))

        # Finalize job status
        if job.status != JobStatus.CANCELLED:
            if failed == 0:
                job.status = JobStatus.COMPLETED
            elif succeeded > 0:
                job.status = JobStatus.PARTIAL_SUCCESS
            else:
                job.status = JobStatus.FAILED

        job.finished_at = datetime.now(timezone.utc)
        job.succeeded_operations = succeeded
        job.failed_operations = failed
        job.skipped_operations = skipped
        self.op_repo.update_sort_job(job)

        event_bus.publish(SortCompletedEvent(job_id, succeeded, failed, skipped))

        return SortExecutionReport(
            job_id=job_id,
            total=total_count,
            succeeded=succeeded,
            failed=failed,
            skipped=skipped,
            is_dry_run=is_dry_run,
        )
