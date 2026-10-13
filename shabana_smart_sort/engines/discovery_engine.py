"""High performance file discovery engine with cancellation, safety, and recursion control."""
import os
from pathlib import Path
from typing import List, Callable, Optional
import logging

from shabana_smart_sort.domain.models import FileItem
from shabana_smart_sort.engines.metadata_engine import MetadataEngine

logger = logging.getLogger("ShabanaSmartSort.Discovery")


class DiscoveryEngine:
    """Scans filesystem paths safely and non-destructively."""

    def __init__(self, follow_symlinks: bool = False, compute_hashes: bool = False):
        self.follow_symlinks = follow_symlinks
        self.compute_hashes = compute_hashes

    def scan_directory(
        self,
        directory: Path,
        recursive: bool = False,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> List[FileItem]:
        """
        Discovers all files in the given directory.
        progress_callback(count, current_filename)
        cancel_check() -> bool returns True if operation was requested to cancel.
        """
        directory = directory.resolve()
        if not directory.exists() or not directory.is_dir():
            raise FileNotFoundError(f"Directory not found: {directory}")

        items: List[FileItem] = []
        count = 0
        visited_dirs = set()

        def _scan(current_dir: Path) -> None:
            nonlocal count
            if cancel_check and cancel_check():
                return

            try:
                real_path = os.path.realpath(current_dir)
                if real_path in visited_dirs:
                    return
                visited_dirs.add(real_path)

                with os.scandir(current_dir) as it:
                    dirs_to_recurse = []
                    for entry in it:
                        if cancel_check and cancel_check():
                            return

                        try:
                            # Skip directory symlinks if not following symlinks
                            if entry.is_symlink() and not self.follow_symlinks:
                                continue

                            if entry.is_file(follow_symlinks=self.follow_symlinks):
                                stat_res = entry.stat(follow_symlinks=self.follow_symlinks)
                                file_path = Path(entry.path)
                                item = MetadataEngine.create_file_item(
                                    path=file_path,
                                    root_path=directory,
                                    stat_result=stat_res,
                                    compute_hash=self.compute_hashes,
                                )
                                items.append(item)
                                count += 1
                                if progress_callback and (count % 25 == 0 or count == 1):
                                    progress_callback(count, entry.name)

                            elif recursive and entry.is_dir(follow_symlinks=self.follow_symlinks):
                                dirs_to_recurse.append(Path(entry.path))

                        except (PermissionError, OSError) as e:
                            logger.warning(f"Skipping inaccessible file {entry.name}: {e}")

                    for sub_dir in dirs_to_recurse:
                        if cancel_check and cancel_check():
                            return
                        _scan(sub_dir)

            except (PermissionError, OSError) as e:
                logger.warning(f"Could not open directory {current_dir}: {e}")

        _scan(directory)
        if progress_callback:
            progress_callback(count, "Scan complete")
        return items
