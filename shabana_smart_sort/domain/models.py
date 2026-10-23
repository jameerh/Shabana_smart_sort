"""Core domain entities for file items, scan batches, and sort batches."""
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from shabana_smart_sort.domain.enums import (
    FileCategory,
    ActionType,
    CollisionPolicy,
    OperationStatus,
    JobStatus,
)


@dataclass
class FileItem:
    """Represents a discovered file and its extracted metadata."""
    path: Path
    name: str
    stem: str
    extension: str  # e.g., ".pdf" in lowercase
    size_bytes: int
    category: FileCategory
    created_at: datetime
    modified_at: datetime
    accessed_at: datetime
    is_hidden: bool = False
    is_readonly: bool = False
    is_empty: bool = False
    parent_dir: Path = field(default_factory=Path)
    relative_path: str = ""
    sha256: Optional[str] = None
    content_text: Optional[str] = None
    ocr_text: Optional[str] = None

    @property
    def extension_no_dot(self) -> str:
        return self.extension.lstrip(".")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": str(self.path),
            "name": self.name,
            "stem": self.stem,
            "extension": self.extension,
            "size_bytes": self.size_bytes,
            "category": self.category.value,
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat(),
            "accessed_at": self.accessed_at.isoformat(),
            "is_hidden": self.is_hidden,
            "is_readonly": self.is_readonly,
            "is_empty": self.is_empty,
            "relative_path": self.relative_path,
            "sha256": self.sha256,
        }


@dataclass
class ScanJob:
    """Represents a folder scan session."""
    id: str
    root_path: str
    is_recursive: bool
    started_at: datetime
    finished_at: Optional[datetime] = None
    total_files: int = 0
    total_size_bytes: int = 0
    status: JobStatus = JobStatus.PENDING
    error_message: Optional[str] = None


@dataclass
class PlannedOperation:
    """A planned single-file relocation or copy operation."""
    id: str
    sort_job_id: str
    source_path: str
    destination_path: str
    original_destination_path: str
    action: ActionType = ActionType.MOVE
    matched_rule_id: Optional[str] = None
    matched_rule_name: Optional[str] = None
    match_reason: str = ""
    is_valid: bool = True
    validation_error: Optional[str] = None
    collision_detected: bool = False
    collision_policy_applied: CollisionPolicy = CollisionPolicy.RENAME_NEW
    selected_for_execution: bool = True
    file_size: int = 0
    status: OperationStatus = OperationStatus.PLANNED
    executed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    is_cross_volume: bool = False
    rename_applied: Optional[str] = None


@dataclass
class SortJob:
    """Represents an execution run of planned operations."""
    id: str
    source_folder: str
    target_folder: str
    is_dry_run: bool = True
    scan_job_id: Optional[str] = None
    total_operations: int = 0
    succeeded_operations: int = 0
    failed_operations: int = 0
    skipped_operations: int = 0
    status: JobStatus = JobStatus.PENDING
    started_at: datetime = field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None
    journal_notes: Optional[str] = None
