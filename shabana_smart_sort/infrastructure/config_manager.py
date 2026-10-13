"""Versioned JSON configuration management."""
import json
import os
from pathlib import Path
from typing import Dict, Any
import logging

from shabana_smart_sort.domain.enums import CollisionPolicy, DateField

logger = logging.getLogger("ShabanaSmartSort.Config")


class ConfigManager:
    """Manages application user preferences stored as versioned JSON."""

    def __init__(self, config_path: Path):
        self.config_path = config_path
        self._data: Dict[str, Any] = self._load_or_create_default()

    def _get_default_downloads_folder(self) -> str:
        # Resolve user's actual Windows Downloads directory
        try:
            home = Path.home()
            downloads = home / "Downloads"
            if downloads.exists():
                return str(downloads)
            return str(home)
        except Exception:
            return str(Path("C:/"))

    def _get_default_config(self) -> Dict[str, Any]:
        downloads_dir = self._get_default_downloads_folder()
        return {
            "version": 1,
            "default_source_folder": downloads_dir,
            "default_organized_folder": str(Path(downloads_dir) / "Organized"),
            "recursive_scan_default": False,
            "collision_policy": CollisionPolicy.RENAME_NEW.value,
            "date_filter_field": DateField.MODIFIED.value,
            "theme": "dark",
            "confirm_threshold": 25,
            "verify_sha256": False,
            "follow_symlinks": False,
        }

    def _load_or_create_default(self) -> Dict[str, Any]:
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    defaults = self._get_default_config()
                    # Ensure all keys exist
                    for k, v in defaults.items():
                        if k not in data:
                            data[k] = v
                    return data
            except Exception as e:
                logger.error(f"Failed to read config from {self.config_path}: {e}, regenerating defaults.")

        defaults = self._get_default_config()
        self._save(defaults)
        return defaults

    def _save(self, data: Dict[str, Any]) -> None:
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to write config to {self.config_path}: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self._save(self._data)

    def get_all(self) -> Dict[str, Any]:
        return dict(self._data)
