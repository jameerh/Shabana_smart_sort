"""Operation journal and audit models for safe execution and honest undo."""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from shabana_smart_sort.domain.enums import (
    ActionType,
    OperationStatus,
)


@dataclass
class JournalEntry:
    """Detailed audit record of an executed file operation."""
    id: str
    operation_id: str
    sort_job_id: str
    source_path: str
    destination_path: str
    action: ActionType
    status: OperationStatus
    file_size: int
    is_cross_volume: bool
    created_at: datetime
    executed_at: Optional[datetime] = None
    reverted_at: Optional[datetime] = None
    sha256_before: Optional[str] = None
    sha256_after: Optional[str] = None
    temp_path: Optional[str] = None
    error_message: Optional[str] = None
    can_undo: bool = True
    undo_status: Optional[str] = None

    def mark_succeeded(self) -> None:
        self.status = OperationStatus.SUCCEEDED
        self.executed_at = datetime.now(timezone.utc)
        self.can_undo = (self.action == ActionType.MOVE or self.action == ActionType.COPY)

    def mark_failed(self, error: str) -> None:
        self.status = OperationStatus.FAILED
        self.error_message = error
        self.can_undo = False

    def mark_reverted(self) -> None:
        self.status = OperationStatus.REVERTED
        self.reverted_at = datetime.now(timezone.utc)
        self.can_undo = False
