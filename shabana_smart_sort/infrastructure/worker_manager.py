"""Qt background worker manager providing responsive threaded executions."""
from pathlib import Path
from typing import List, Optional, Callable
from PySide6.QtCore import QObject, Signal, QRunnable, QThreadPool

from shabana_smart_sort.application.scan_workflow import ScanWorkflow, ScanSummary
from shabana_smart_sort.application.sort_workflow import SortWorkflow, SortExecutionReport
from shabana_smart_sort.domain.models import PlannedOperation


class WorkerSignals(QObject):
    """Standard signals emitted by background worker tasks."""
    progress = Signal(int, int, str, str)  # current, total, filename, message
    finished = Signal(object)              # result object
    error = Signal(str)                    # error message


class ScanWorker(QRunnable):
    """Executes directory scan on a background thread."""

    def __init__(self, workflow: ScanWorkflow, folder_path: Path, recursive: bool):
        super().__init__()
        self.workflow = workflow
        self.folder_path = folder_path
        self.recursive = recursive
        self.signals = WorkerSignals()
        self._is_cancelled = False

    def cancel(self) -> None:
        self._is_cancelled = True

    def run(self) -> None:
        try:
            def _progress(count: int, filename: str) -> None:
                self.signals.progress.emit(count, 0, filename, "Scanning...")

            def _cancel_check() -> bool:
                return self._is_cancelled

            summary = self.workflow.run_scan(
                folder_path=self.folder_path,
                recursive=self.recursive,
                progress_callback=_progress,
                cancel_check=_cancel_check,
            )
            self.signals.finished.emit(summary)
        except Exception as e:
            self.signals.error.emit(str(e))


class SortWorker(QRunnable):
    """Executes file operations or dry runs on a background thread."""

    def __init__(
        self,
        workflow: SortWorkflow,
        operations: List[PlannedOperation],
        source_folder: Path,
        target_folder: Path,
        is_dry_run: bool,
    ):
        super().__init__()
        self.workflow = workflow
        self.operations = operations
        self.source_folder = source_folder
        self.target_folder = target_folder
        self.is_dry_run = is_dry_run
        self.signals = WorkerSignals()
        self._is_cancelled = False

    def cancel(self) -> None:
        self._is_cancelled = True

    def run(self) -> None:
        try:
            def _progress(current: int, total: int, filename: str, status: str) -> None:
                self.signals.progress.emit(current, total, filename, status)

            def _cancel_check() -> bool:
                return self._is_cancelled

            report = self.workflow.execute_sort(
                operations=self.operations,
                source_folder=self.source_folder,
                target_folder=self.target_folder,
                is_dry_run=self.is_dry_run,
                progress_callback=_progress,
                cancel_check=_cancel_check,
            )
            self.signals.finished.emit(report)
        except Exception as e:
            self.signals.error.emit(str(e))
