"""Collision detection and path conflict resolver."""
from pathlib import Path
from typing import Set, Tuple
import logging

from shabana_smart_sort.domain.enums import CollisionPolicy

logger = logging.getLogger("ShabanaSmartSort.ConflictResolver")


class ConflictResolver:
    """Detects filename collisions on disk and within the current planning batch."""

    @classmethod
    def resolve_destination_collision(
        cls,
        dest_path: Path,
        policy: CollisionPolicy,
        planned_destinations: Set[str],
    ) -> Tuple[Path, bool, bool]:
        """
        Evaluates whether dest_path collides with disk or existing planned operations.
        Returns:
            (final_path, collision_detected, should_skip)
        """
        dest_str = str(dest_path.resolve()).lower()
        exists_on_disk = dest_path.exists()
        already_planned = dest_str in planned_destinations

        if not exists_on_disk and not already_planned:
            # No collision
            return dest_path, False, False

        # Collision detected!
        if policy == CollisionPolicy.SKIP:
            return dest_path, True, True

        if policy == CollisionPolicy.OVERWRITE:
            return dest_path, True, False

        # Default: CollisionPolicy.RENAME_NEW (or ASK_USER preview fallback)
        stem = dest_path.stem
        ext = dest_path.suffix
        parent = dest_path.parent

        counter = 1
        while True:
            candidate_name = f"{stem} ({counter}){ext}"
            candidate_path = parent / candidate_name
            candidate_str = str(candidate_path.resolve()).lower()

            if not candidate_path.exists() and candidate_str not in planned_destinations:
                return candidate_path, True, False

            counter += 1
            if counter > 10000:
                # Emergency fallback safety limit
                raise RuntimeError(f"Excessive filename collisions encountered for {dest_path}")
