"""Workflow for calculating dry-run destinations, collisions, and preview reports."""
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import List, Set, Optional

from shabana_smart_sort.domain.enums import (
    CollisionPolicy,
    OperationStatus,
    ActionType,
)
from shabana_smart_sort.domain.models import FileItem, PlannedOperation
from shabana_smart_sort.domain.rule_schema import Rule
from shabana_smart_sort.engines.destination_engine import DestinationEngine
from shabana_smart_sort.engines.rule_engine import RuleEngine
from shabana_smart_sort.services.conflict_resolver import ConflictResolver
from shabana_smart_sort.services.disk_space_service import DiskSpaceService


@dataclass
class PreviewReport:
    """Consolidated summary of a calculated organization plan."""
    operations: List[PlannedOperation]
    total_files: int
    matched_count: int
    unmatched_count: int
    collision_count: int
    total_bytes_to_move: int
    sufficient_disk_space: bool
    free_disk_space_bytes: int


class PreviewWorkflow:
    """Calculates non-destructive preview plans without changing the filesystem."""

    def __init__(self, rule_engine: Optional[RuleEngine] = None):
        self.rule_engine = rule_engine or RuleEngine()

    def generate_preview(
        self,
        files: List[FileItem],
        rules: List[Rule],
        target_root: Path,
        default_collision_policy: CollisionPolicy = CollisionPolicy.RENAME_NEW,
        sort_job_id: Optional[str] = None,
    ) -> PreviewReport:
        """Evaluates rules, resolves templates, checks collisions, and returns dry-run plan."""
        job_id = sort_job_id or str(uuid.uuid4())
        self.rule_engine.set_rules(rules)

        planned_ops: List[PlannedOperation] = []
        planned_destinations: Set[str] = set()

        matched_count = 0
        unmatched_count = 0
        collision_count = 0
        total_bytes = 0

        for item in files:
            match_res = self.rule_engine.evaluate_file(item)

            if match_res.is_matched and match_res.rule is not None:
                matched_count += 1
                rule = match_res.rule
                policy = rule.action.collision_policy or default_collision_policy

                # Resolve initial template destination
                initial_dest = DestinationEngine.resolve_destination(
                    base_target_root=target_root,
                    item=item,
                    rule=rule,
                )

                # Check and resolve collisions
                resolved_dest, had_collision, should_skip = ConflictResolver.resolve_destination_collision(
                    dest_path=initial_dest,
                    policy=policy,
                    planned_destinations=planned_destinations,
                )

                if had_collision:
                    collision_count += 1

                # Reserve this destination in the current batch
                planned_destinations.add(str(resolved_dest.resolve()).lower())

                # Create planned operation
                status = OperationStatus.SKIPPED if should_skip else OperationStatus.PLANNED
                op = PlannedOperation(
                    id=str(uuid.uuid4()),
                    sort_job_id=job_id,
                    source_path=str(item.path),
                    destination_path=str(resolved_dest),
                    original_destination_path=str(initial_dest),
                    action=rule.action.action_type,
                    matched_rule_id=rule.id,
                    matched_rule_name=rule.name,
                    match_reason=match_res.reason,
                    is_valid=not should_skip,
                    collision_detected=had_collision,
                    collision_policy_applied=policy,
                    selected_for_execution=(not should_skip),
                    file_size=item.size_bytes,
                    status=status,
                )
                if not should_skip:
                    total_bytes += item.size_bytes
                planned_ops.append(op)

            else:
                unmatched_count += 1
                # Unmatched file: leave in place
                op = PlannedOperation(
                    id=str(uuid.uuid4()),
                    sort_job_id=job_id,
                    source_path=str(item.path),
                    destination_path=str(item.path),  # unchanged
                    original_destination_path=str(item.path),
                    action=ActionType.MOVE,
                    matched_rule_id=None,
                    matched_rule_name=None,
                    match_reason=match_res.reason,
                    is_valid=True,
                    collision_detected=False,
                    collision_policy_applied=default_collision_policy,
                    selected_for_execution=False,  # unchecked by default
                    file_size=item.size_bytes,
                    status=OperationStatus.SKIPPED,
                )
                planned_ops.append(op)

        # Disk space verification
        sufficient_space, free_bytes, _ = DiskSpaceService.check_sufficient_space(
            target_root=target_root,
            required_bytes=total_bytes,
        )

        return PreviewReport(
            operations=planned_ops,
            total_files=len(files),
            matched_count=matched_count,
            unmatched_count=unmatched_count,
            collision_count=collision_count,
            total_bytes_to_move=total_bytes,
            sufficient_disk_space=sufficient_space,
            free_disk_space_bytes=free_bytes,
        )
