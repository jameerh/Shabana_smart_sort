"""Workflow orchestrating directory discovery and metadata collection."""
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Callable, Optional, Dict

from shabana_smart_sort.domain.enums import JobStatus, FileCategory
from shabana_smart_sort.domain.models import FileItem, ScanJob
from shabana_smart_sort.engines.discovery_engine import DiscoveryEngine
from shabana_smart_sort.infrastructure.event_bus import (
    event_bus,
    ScanProgressEvent,
    ScanCompletedEvent,
)
from shabana_smart_sort.repositories.scan_repository import ScanRepository


class ScanSummary:
    def __init__(
        self,
        job_id: str,
        root_path: Path,
        items: List[FileItem],
        duration_sec: float,
        category_counts: Dict[FileCategory, int],
        total_size_bytes: int,
    ):
        self.job_id = job_id
        self.root_path = root_path
        self.items = items
        self.duration_sec = duration_sec
        self.category_counts = category_counts
        self.total_size_bytes = total_size_bytes

    @property
    def total_files(self) -> int:
        return len(self.items)


class ScanWorkflow:
    def __init__(
        self,
        scan_repo: ScanRepository,
        discovery_engine: Optional[DiscoveryEngine] = None,
    ):
        self.scan_repo = scan_repo
        self.discovery_engine = discovery_engine or DiscoveryEngine()

    def run_scan(
        self,
        folder_path: Path,
        recursive: bool = False,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> ScanSummary:
        """Executes a directory scan, records metrics, and returns summary."""
        job_id = str(uuid.uuid4())
        start_time = time.time()
        start_dt = datetime.now(timezone.utc)

        job = ScanJob(
            id=job_id,
            root_path=str(folder_path),
            is_recursive=recursive,
            started_at=start_dt,
            status=JobStatus.RUNNING,
        )
        self.scan_repo.create(job)

        def _on_progress(count: int, filename: str) -> None:
            event_bus.publish(ScanProgressEvent(filename, count))
            if progress_callback:
                progress_callback(count, filename)

        try:
            items = self.discovery_engine.scan_directory(
                directory=folder_path,
                recursive=recursive,
                progress_callback=_on_progress,
                cancel_check=cancel_check,
            )

            duration = time.time() - start_time
            total_size = sum(item.size_bytes for item in items)

            category_counts: Dict[FileCategory, int] = {}
            for item in items:
                category_counts[item.category] = category_counts.get(item.category, 0) + 1

            job.finished_at = datetime.now(timezone.utc)
            job.total_files = len(items)
            job.total_size_bytes = total_size
            job.status = JobStatus.COMPLETED
            self.scan_repo.update(job)

            event_bus.publish(ScanCompletedEvent(len(items), total_size, duration))

            return ScanSummary(
                job_id=job_id,
                root_path=folder_path,
                items=items,
                duration_sec=duration,
                category_counts=category_counts,
                total_size_bytes=total_size,
            )

        except Exception as e:
            job.finished_at = datetime.now(timezone.utc)
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            self.scan_repo.update(job)
            raise e
