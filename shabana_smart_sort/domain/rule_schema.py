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


class ConditionGroup(BaseModel):
    """A group of conditions evaluated together with a specific logical operator (ALL or ANY)."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    logical_op: LogicalOperator = LogicalOperator.ALL  # Default AND within group
    conditions: List[RuleCondition] = Field(default_factory=list)
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
    rename_prefix: Optional[str] = None     # Optional sequential rename prefix (e.g. "xyz")
    rename_pattern: Optional[str] = None    # Pattern such as "{prefix}_{counter}"
    start_counter: int = 1                  # Starting number for sequential rename


class Rule(BaseModel):
    """Complete rule definition."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., min_length=1)
    description: str = ""
    priority: int = 100
    is_enabled: bool = True
    logical_op: LogicalOperator = LogicalOperator.ALL  # Top-level combiner (e.g. OR across groups, or AND)
    conditions: List[RuleCondition] = Field(default_factory=list)  # Legacy / flat conditions
    condition_groups: List[ConditionGroup] = Field(default_factory=list)  # Advanced compound groups
    action: RuleAction = Field(default_factory=RuleAction)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = 1

    def matches_mode_all(self) -> bool:
        return self.logical_op == LogicalOperator.ALL

    def get_effective_groups(self) -> List[ConditionGroup]:
        """Returns condition_groups if present, or synthesizes a group from flat conditions."""
        if self.condition_groups:
            return self.condition_groups
        if self.conditions:
            return [ConditionGroup(
                id=f"{self.id}_legacy_group",
                logical_op=self.logical_op,
                conditions=self.conditions
            )]
        return []


class RuleExportPack(BaseModel):
    """Export container for sharing rules across systems."""
    format_version: str = "1.0"
    exported_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    rules: List[Rule] = Field(default_factory=list)
