"""Schema and validation models for rules and conditions using Pydantic."""
from datetime import datetime, timezone
import uuid
from typing import List, Any, Optional
from pydantic import BaseModel, Field

from shabana_smart_sort.domain.enums import (
    ConditionTarget,
    ConditionOperator,
    LogicalOperator,
    ActionType,
    CollisionPolicy,
)


class RuleCondition(BaseModel):
    """A single conditional test applied to a FileItem."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    target: ConditionTarget
    operator: ConditionOperator
    value: Any
    case_sensitive: bool = False
    description: Optional[str] = None


class RuleAction(BaseModel):
    """Destination and behavior specification for a matching rule."""
    action_type: ActionType = ActionType.MOVE
    destination_template: str = Field(
        default="Organized/{category}/",
        description="Template supporting {year}, {month}, {day}, {extension}, {category}, {rule_name}"
    )
    collision_policy: CollisionPolicy = CollisionPolicy.RENAME_NEW
    custom_root_path: Optional[str] = None  # None means relative to organized base / source


class Rule(BaseModel):
    """Complete rule definition."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., min_length=1)
    description: str = ""
    priority: int = 100
    is_enabled: bool = True
    logical_op: LogicalOperator = LogicalOperator.ALL
    conditions: List[RuleCondition] = Field(default_factory=list)
    action: RuleAction = Field(default_factory=RuleAction)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = 1

    def matches_mode_all(self) -> bool:
        return self.logical_op == LogicalOperator.ALL


class RuleExportPack(BaseModel):
    """Export container for sharing rules across systems."""
    format_version: str = "1.0"
    exported_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    rules: List[Rule] = Field(default_factory=list)
