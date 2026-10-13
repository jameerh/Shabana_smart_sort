"""Duplicate file detection engine using tiered size-filtering and SHA256 checksums."""
from collections import defaultdict
from pathlib import Path
from typing import List, Dict
import logging

from shabana_smart_sort.domain.models import FileItem
from shabana_smart_sort.engines.metadata_engine import MetadataEngine

logger = logging.getLogger("ShabanaSmartSort.Duplicate")


class DuplicateEngine:
    """Detects potential duplicate files safely without pre-hashing everything."""

    @classmethod
    def find_duplicates(cls, items: List[FileItem]) -> Dict[str, List[FileItem]]:
        """
        Groups files that share identical size and SHA-256 hash.
        Returns a dictionary mapping hash -> list of identical FileItems (length >= 2).
        """
        # Tier 1: Group by file size (files of different sizes cannot be duplicates)
        size_groups: Dict[int, List[FileItem]] = defaultdict(list)
        for item in items:
            if item.size_bytes > 0:  # Ignore 0-byte empty files
                size_groups[item.size_bytes].append(item)

        potential_candidates = [
            group for group in size_groups.values() if len(group) > 1
        ]

        # Tier 2: For items sharing size, compute SHA-256
        duplicates_by_hash: Dict[str, List[FileItem]] = defaultdict(list)

        for candidate_list in potential_candidates:
            for item in candidate_list:
                if not item.sha256:
                    item.sha256 = MetadataEngine.compute_sha256(item.path)
                if item.sha256:
                    duplicates_by_hash[item.sha256].append(item)

        # Filter down to entries that actually have 2 or more files
        return {
            h: group for h, group in duplicates_by_hash.items() if len(group) > 1
        }
