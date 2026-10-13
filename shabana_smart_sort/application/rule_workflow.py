"""Workflow for creating, modifying, testing, importing, and exporting rules."""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
import logging

from shabana_smart_sort.domain.models import FileItem
from shabana_smart_sort.domain.rule_schema import Rule, RuleExportPack
from shabana_smart_sort.engines.rule_engine import RuleEngine
from shabana_smart_sort.repositories.rule_repository import RuleRepository

logger = logging.getLogger("ShabanaSmartSort.RuleWorkflow")


class RuleWorkflow:
    """Manages the full lifecycle of sorting rules."""

    def __init__(self, rule_repo: RuleRepository):
        self.rule_repo = rule_repo

    def get_all_rules(self, enabled_only: bool = False) -> List[Rule]:
        return self.rule_repo.get_all(enabled_only=enabled_only)

    def save_rule(self, rule: Rule) -> Tuple[bool, Optional[str]]:
        """Validates and saves a rule."""
        is_valid, error = self.validate_rule(rule)
        if not is_valid:
            return False, error

        rule.updated_at = datetime.now(timezone.utc)
        self.rule_repo.save(rule)
        return True, None

    def delete_rule(self, rule_id: str) -> None:
        self.rule_repo.delete(rule_id)

    def set_rule_enabled(self, rule_id: str, enabled: bool) -> None:
        self.rule_repo.set_enabled(rule_id, enabled)

    def clone_rule(self, rule_id: str) -> Optional[Rule]:
        """Creates a duplicate of an existing rule with a new ID."""
        existing = self.rule_repo.get_by_id(rule_id)
        if not existing:
            return None

        data = existing.model_dump()
        data["id"] = str(uuid.uuid4())
        data["name"] = f"Copy of {existing.name}"
        data["priority"] = existing.priority + 1
        data["created_at"] = datetime.now(timezone.utc)
        data["updated_at"] = datetime.now(timezone.utc)
        for cond in data.get("conditions", []):
            cond["id"] = str(uuid.uuid4())

        cloned = Rule(**data)
        self.rule_repo.save(cloned)
        return cloned

    def reorder_rules(self, rule_ids: List[str]) -> None:
        self.rule_repo.reorder(rule_ids)

    def test_rule(self, rule: Rule, sample_files: List[FileItem]) -> List[Tuple[FileItem, bool, str]]:
        """Tests a candidate rule against sample files without saving or moving anything."""
        engine = RuleEngine()
        results = []
        for item in sample_files:
            matched, reason = engine.evaluate_rule(rule, item)
            results.append((item, matched, reason))
        return results

    def export_rules_json(self, export_path: Optional[Path] = None) -> str:
        """Exports all rules to a versioned JSON format."""
        rules = self.rule_repo.get_all()
        pack = RuleExportPack(rules=rules)
        json_str = pack.model_dump_json(indent=2)
        if export_path:
            export_path.parent.mkdir(parents=True, exist_ok=True)
            with open(export_path, "w", encoding="utf-8") as f:
                f.write(json_str)
        return json_str

    def import_rules_json(self, json_content_or_path: str, overwrite_existing: bool = False) -> Tuple[int, List[str]]:
        """Imports rules from a JSON string or file path."""
        errors: List[str] = []
        imported_count = 0

        try:
            p = Path(json_content_or_path)
            if p.exists() and p.is_file():
                with open(p, "r", encoding="utf-8") as f:
                    content = f.read()
            else:
                content = json_content_or_path

            data = json.loads(content)
            pack = RuleExportPack(**data)

            for rule in pack.rules:
                try:
                    # Give imported rule new ID if not overwriting
                    if not overwrite_existing:
                        rule.id = str(uuid.uuid4())
                        for c in rule.conditions:
                            c.id = str(uuid.uuid4())
                    self.rule_repo.save(rule)
                    imported_count += 1
                except Exception as e:
                    errors.append(f"Failed to import rule '{rule.name}': {e}")

        except Exception as e:
            errors.append(f"Invalid rules JSON schema: {e}")

        return imported_count, errors

    @staticmethod
    def validate_rule(rule: Rule) -> Tuple[bool, Optional[str]]:
        """Validates rule properties, conditions, and destination template."""
        if not rule.name or not rule.name.strip():
            return False, "Rule name cannot be empty."

        if not rule.action.destination_template or not rule.action.destination_template.strip():
            return False, "Destination template cannot be empty."

        for idx, cond in enumerate(rule.conditions):
            if cond.value is None or cond.value == "":
                return False, f"Condition #{idx + 1} has an empty value."

        return True, None
