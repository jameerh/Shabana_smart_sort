"""Destination path calculation with template expansion and path traversal security."""
import re
from pathlib import Path
from typing import Optional, Dict

from shabana_smart_sort.domain.models import FileItem
from shabana_smart_sort.domain.rule_schema import Rule

# Characters forbidden in Windows filenames/folder names
ILLEGAL_CHARS_PATTERN = re.compile(r'[<>:"/\\|?*]')


class DestinationEngine:
    """Calculates safe destination paths using whitelist-validated template variables."""

    @classmethod
    def sanitize_path_component(cls, component: str) -> str:
        """Removes or replaces illegal Windows filesystem characters."""
        # Replace illegal characters with underscore
        cleaned = ILLEGAL_CHARS_PATTERN.sub("_", component).strip()
        # Disallow Windows reserved names like CON, PRN, AUX, NUL, COM1-9, LPT1-9
        reserved_names = {
            "CON", "PRN", "AUX", "NUL",
            "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
            "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"
        }
        if cleaned.upper() in reserved_names:
            cleaned = f"_{cleaned}_"
        return cleaned or "unnamed"

    @classmethod
    def resolve_destination(
        cls,
        base_target_root: Path,
        item: FileItem,
        rule: Rule,
    ) -> Path:
        """
        Calculates destination path by resolving the template in the rule's action.
        Guarantees that the resolved path never traverses outside the target root.
        """
        template = rule.action.destination_template or "Organized/{category}/"
        # If the rule has an explicit custom root, use it; otherwise use base_target_root
        target_root = Path(rule.action.custom_root_path) if rule.action.custom_root_path else base_target_root
        target_root = target_root.resolve()

        # Variable mapping
        year_str = f"{item.modified_at.year:04d}"
        month_str = f"{item.modified_at.month:02d}"
        day_str = f"{item.modified_at.day:02d}"
        ext_clean = item.extension_no_dot or "no_ext"
        category_clean = item.category.value
        rule_name_clean = cls.sanitize_path_component(rule.name)
        stem_clean = cls.sanitize_path_component(item.stem)

        variables: Dict[str, str] = {
            "year": year_str,
            "month": month_str,
            "day": day_str,
            "extension": ext_clean,
            "category": category_clean,
            "rule_name": rule_name_clean,
            "stem": stem_clean,
            "original_name": cls.sanitize_path_component(item.name),
        }

        # Substitute template variables
        expanded_rel = template
        for key, val in variables.items():
            expanded_rel = expanded_rel.replace(f"{{{key}}}", val)

        # Normalize relative path components to prevent directory traversal
        parts = [p for p in expanded_rel.replace("\\", "/").split("/") if p and p != "."]

        sanitized_parts = []
        for part in parts:
            if part == "..":
                # Disallow parent directory navigation
                continue
            sanitized_parts.append(cls.sanitize_path_component(part))

        # Destination directory
        dest_dir = target_root.joinpath(*sanitized_parts)

        # Final file path (retaining the file's original name)
        final_path = dest_dir / item.name

        # Security check: Ensure final path is inside or child of target_root
        resolved_final = final_path.resolve()
        try:
            resolved_final.relative_to(target_root)
        except ValueError:
            # Traversal escape detected! Fallback safely to directly inside target_root
            final_path = target_root / "Organized" / category_clean / item.name

        return final_path
