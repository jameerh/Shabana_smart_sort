"""Disk space verification service."""
import shutil
from pathlib import Path
from typing import Tuple
import logging

logger = logging.getLogger("ShabanaSmartSort.DiskSpace")


class DiskSpaceService:
    """Verifies available drive storage before executing file operations."""

    @staticmethod
    def get_free_space(path: Path) -> int:
        """Returns free space in bytes on the drive containing path."""
        try:
            # Find an existing parent if path does not exist yet
            target = path.resolve()
            while not target.exists() and target.parent != target:
                target = target.parent
            usage = shutil.disk_usage(target)
            return usage.free
        except Exception as e:
            logger.warning(f"Failed to check disk usage for {path}: {e}")
            return 1024 * 1024 * 1024 * 100  # Fallback 100GB if undetectable

    @classmethod
    def check_sufficient_space(cls, target_root: Path, required_bytes: int, safety_buffer_bytes: int = 50 * 1024 * 1024) -> Tuple[bool, int, int]:
        """
        Returns (is_sufficient, free_bytes, required_bytes + buffer)
        """
        free_bytes = cls.get_free_space(target_root)
        total_needed = required_bytes + safety_buffer_bytes
        return (free_bytes >= total_needed), free_bytes, total_needed
