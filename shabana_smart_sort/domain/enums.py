"""Domain enumerations for Shabana Smart Sort."""
from enum import Enum, auto


class FileCategory(str, Enum):
    DOCUMENT = "document"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    ARCHIVE = "archive"
    INSTALLER = "installer"
    CODE = "code"
    SPREADSHEET = "spreadsheet"
    PRESENTATION = "presentation"
    MISC = "misc"


class DateField(str, Enum):
    MODIFIED = "modified"
    CREATED = "created"
    ACCESSED = "accessed"
    FIRST_OBSERVED = "first_observed"


class ConditionTarget(str, Enum):
    FILENAME = "filename"
    EXTENSION = "extension"
    CATEGORY = "category"
    SIZE_BYTES = "size_bytes"
    DATE_MODIFIED = "date_modified"
    DATE_CREATED = "date_created"
    DATE_ACCESSED = "date_accessed"
    IS_HIDDEN = "is_hidden"
    IS_READONLY = "is_readonly"
    IS_EMPTY = "is_empty"
    FILE_CONTENT = "file_content"       # Text found inside files (.txt, .csv, .pdf, .docx, .xlsx, .pptx)
    IMAGE_OCR_TEXT = "image_ocr_text"   # Text recognized inside images via OCR


class ConditionOperator(str, Enum):
    # String operations
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    MATCHES_REGEX = "matches_regex"
    MATCHES_WILDCARD = "matches_wildcard"

    # List / Set operations
    IS_ONE_OF = "is_one_of"
    IS_NOT_ONE_OF = "is_not_one_of"

    # Numeric / Size operations
    LESS_THAN = "less_than"
    GREATER_THAN = "greater_than"
    EQUALS_NUMERIC = "equals_numeric"
    BETWEEN_NUMERIC = "between_numeric"

    # Date operations
    DATE_BEFORE = "date_before"
    DATE_AFTER = "date_after"
    DATE_BETWEEN = "date_between"
    DATE_IN_LAST_DAYS = "date_in_last_days"

    # Boolean operations
    IS_TRUE = "is_true"
    IS_FALSE = "is_false"


class LogicalOperator(str, Enum):
    ALL = "all"  # AND
    ANY = "any"  # OR


class ActionType(str, Enum):
    MOVE = "move"
    COPY = "copy"


class CollisionPolicy(str, Enum):
    RENAME_NEW = "rename_new"          # auto-suffix e.g. "document (1).pdf"
    SKIP = "skip"                      # skip operation with logged explanation
    OVERWRITE = "overwrite"            # overwrite existing target if user permitted
    ASK_USER = "ask_user"              # flag in preview for explicit decision


class OperationStatus(str, Enum):
    PLANNED = "planned"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
    REVERTED = "reverted"
    NEEDS_RECONCILIATION = "needs_reconciliation"


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIAL_SUCCESS = "partial_success"


class VerificationLevel(str, Enum):
    SIZE_ONLY = "size_only"
    SHA256_HASH = "sha256_hash"
