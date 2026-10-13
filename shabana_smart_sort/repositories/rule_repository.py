"""Repository for rules and condition persistence."""
import json
import uuid
from datetime import datetime, timezone
from typing import List, Optional
import logging

from shabana_smart_sort.domain.enums import (
    ConditionTarget,
    ConditionOperator,
    LogicalOperator,
    ActionType,
    CollisionPolicy,
    FileCategory,
)
from shabana_smart_sort.domain.rule_schema import Rule, RuleCondition, RuleAction
from shabana_smart_sort.infrastructure.database import DatabaseManager

logger = logging.getLogger("ShabanaSmartSort.RuleRepo")


class RuleRepository:
    """Manages persistent rule storage, sorting, and defaults."""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self._ensure_default_rules()

    def get_all(self, enabled_only: bool = False) -> List[Rule]:
        """Retrieves all rules sorted by priority (lowest number = highest priority)."""
        conn = self.db.get_connection()
        cur = conn.cursor()
        query = "SELECT * FROM rules"
        if enabled_only:
            query += " WHERE is_enabled = 1"
        query += " ORDER BY priority ASC, name ASC"

        cur.execute(query)
        rows = cur.fetchall()
        rules: List[Rule] = []
        for row in rows:
            rule_id = row["id"]
            # Fetch conditions
            cur.execute(
                "SELECT * FROM rule_conditions WHERE rule_id = ? ORDER BY rowid ASC",
                (rule_id,)
            )
            cond_rows = cur.fetchall()
            conditions = []
            for c_row in cond_rows:
                # Value may be stored as JSON
                raw_val = c_row["value"]
                try:
                    val = json.loads(raw_val)
                except Exception:
                    val = raw_val

                conditions.append(RuleCondition(
                    id=c_row["id"],
                    target=ConditionTarget(c_row["target"]),
                    operator=ConditionOperator(c_row["operator"]),
                    value=val,
                    case_sensitive=bool(c_row["case_sensitive"]),
                    description=c_row["description"],
                ))

            # Action
            action_data = json.loads(row["action_json"])
            action = RuleAction(**action_data)

            rule = Rule(
                id=row["id"],
                name=row["name"],
                description=row["description"],
                priority=row["priority"],
                is_enabled=bool(row["is_enabled"]),
                logical_op=LogicalOperator(row["logical_op"]),
                conditions=conditions,
                action=action,
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
                version=row["version"],
            )
            rules.append(rule)
        return rules

    def get_by_id(self, rule_id: str) -> Optional[Rule]:
        rules = self.get_all()
        for r in rules:
            if r.id == rule_id:
                return r
        return None

    def save(self, rule: Rule) -> None:
        """Inserts or updates a rule and its conditions atomically."""
        conn = self.db.get_connection()
        now_str = datetime.now(timezone.utc).isoformat()
        action_json = rule.action.model_dump_json()

        with conn:
            conn.execute("""
                INSERT INTO rules (id, name, description, priority, is_enabled, logical_op, action_json, version, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    description = excluded.description,
                    priority = excluded.priority,
                    is_enabled = excluded.is_enabled,
                    logical_op = excluded.logical_op,
                    action_json = excluded.action_json,
                    version = rules.version + 1,
                    updated_at = excluded.updated_at
            """, (
                rule.id,
                rule.name,
                rule.description,
                rule.priority,
                1 if rule.is_enabled else 0,
                rule.logical_op.value,
                action_json,
                rule.version,
                rule.created_at.isoformat(),
                now_str,
            ))

            # Replace conditions
            conn.execute("DELETE FROM rule_conditions WHERE rule_id = ?", (rule.id,))
            for cond in rule.conditions:
                val_str = json.dumps(cond.value) if not isinstance(cond.value, str) else cond.value
                conn.execute("""
                    INSERT INTO rule_conditions (id, rule_id, target, operator, value, case_sensitive, description)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    cond.id,
                    rule.id,
                    cond.target.value,
                    cond.operator.value,
                    val_str,
                    1 if cond.case_sensitive else 0,
                    cond.description or "",
                ))

    def delete(self, rule_id: str) -> None:
        conn = self.db.get_connection()
        with conn:
            conn.execute("DELETE FROM rules WHERE id = ?", (rule_id,))

    def set_enabled(self, rule_id: str, enabled: bool) -> None:
        conn = self.db.get_connection()
        with conn:
            conn.execute(
                "UPDATE rules SET is_enabled = ?, updated_at = ? WHERE id = ?",
                (1 if enabled else 0, datetime.now(timezone.utc).isoformat(), rule_id)
            )

    def reorder(self, rule_ids_in_order: List[str]) -> None:
        """Sets priority based on list order: 10, 20, 30..."""
        conn = self.db.get_connection()
        now_str = datetime.now(timezone.utc).isoformat()
        with conn:
            for idx, r_id in enumerate(rule_ids_in_order):
                priority = (idx + 1) * 10
                conn.execute(
                    "UPDATE rules SET priority = ?, updated_at = ? WHERE id = ?",
                    (priority, now_str, r_id)
                )

    def _ensure_default_rules(self) -> None:
        """Seeds default and specialized rules if not already present."""
        conn = self.db.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT name FROM rules")
        existing_names = {row[0] for row in cur.fetchall()}

        defaults = [
            Rule(
                name="Satbara Land Records (7/12)",
                description="Sort land record Satbara PDFs (7/12 extracts) by Year",
                priority=5,
                conditions=[
                    RuleCondition(
                        target=ConditionTarget.EXTENSION,
                        operator=ConditionOperator.IS_ONE_OF,
                        value=[".pdf"],
                    ),
                    RuleCondition(
                        target=ConditionTarget.FILENAME,
                        operator=ConditionOperator.CONTAINS,
                        value="satbara",
                        case_sensitive=False,
                    ),
                ],
                action=RuleAction(
                    action_type=ActionType.MOVE,
                    destination_template="Organized/Satbara_Records/{year}/",
                    collision_policy=CollisionPolicy.RENAME_NEW,
                )
            ),
            Rule(
                name="Farmer IDs (27_ Series)",
                description="Sort Maharashtra PM-Kisan / DBT / AgriStack Farmer IDs (27_...)",
                priority=6,
                conditions=[
                    RuleCondition(
                        target=ConditionTarget.FILENAME,
                        operator=ConditionOperator.STARTS_WITH,
                        value="27_",
                        case_sensitive=False,
                    ),
                    RuleCondition(
                        target=ConditionTarget.EXTENSION,
                        operator=ConditionOperator.IS_ONE_OF,
                        value=[".pdf"],
                    ),
                ],
                action=RuleAction(
                    action_type=ActionType.MOVE,
                    destination_template="Organized/Farmer_IDs_27/",
                    collision_policy=CollisionPolicy.RENAME_NEW,
                )
            ),
            Rule(
                name="WhatsApp Images & Photos",
                description="Sort WhatsApp Image files with optional date batch renaming",
                priority=7,
                conditions=[
                    RuleCondition(
                        target=ConditionTarget.FILENAME,
                        operator=ConditionOperator.CONTAINS,
                        value="whatsapp",
                        case_sensitive=False,
                    ),
                    RuleCondition(
                        target=ConditionTarget.EXTENSION,
                        operator=ConditionOperator.IS_ONE_OF,
                        value=[".jpeg", ".jpg", ".png", ".webp"],
                    ),
                ],
                action=RuleAction(
                    action_type=ActionType.MOVE,
                    destination_template="Organized/WhatsApp_Images/{year}/{month}/",
                    collision_policy=CollisionPolicy.RENAME_NEW,
                )
            ),
            Rule(
                name="PDF Documents",
                description="Organize all PDF files by Year and Month",
                priority=10,
                conditions=[
                    RuleCondition(
                        target=ConditionTarget.EXTENSION,
                        operator=ConditionOperator.IS_ONE_OF,
                        value=[".pdf"],
                    )
                ],
                action=RuleAction(
                    action_type=ActionType.MOVE,
                    destination_template="Organized/PDFs/{year}/{month}/",
                    collision_policy=CollisionPolicy.RENAME_NEW,
                )
            ),
            Rule(
                name="Images & Photos",
                description="Organize JPG, PNG, WEBP, and GIF photos by Year and Month",
                priority=20,
                conditions=[
                    RuleCondition(
                        target=ConditionTarget.EXTENSION,
                        operator=ConditionOperator.IS_ONE_OF,
                        value=[".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".svg"],
                    )
                ],
                action=RuleAction(
                    action_type=ActionType.MOVE,
                    destination_template="Organized/Images/{year}/{month}/",
                    collision_policy=CollisionPolicy.RENAME_NEW,
                )
            ),
            Rule(
                name="Archives & Compressed",
                description="Organize ZIP, 7Z, RAR, and TAR archives",
                priority=30,
                conditions=[
                    RuleCondition(
                        target=ConditionTarget.EXTENSION,
                        operator=ConditionOperator.IS_ONE_OF,
                        value=[".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"],
                    )
                ],
                action=RuleAction(
                    action_type=ActionType.MOVE,
                    destination_template="Organized/Archives/",
                    collision_policy=CollisionPolicy.RENAME_NEW,
                )
            ),
            Rule(
                name="Installers & Setups",
                description="Organize EXE, MSI, and setup packages",
                priority=40,
                conditions=[
                    RuleCondition(
                        target=ConditionTarget.EXTENSION,
                        operator=ConditionOperator.IS_ONE_OF,
                        value=[".exe", ".msi", ".iso", ".bat", ".cmd"],
                    )
                ],
                action=RuleAction(
                    action_type=ActionType.MOVE,
                    destination_template="Organized/Installers/",
                    collision_policy=CollisionPolicy.RENAME_NEW,
                )
            ),
            Rule(
                name="Office Documents",
                description="Organize Word, Excel, PowerPoint, and CSV files",
                priority=50,
                conditions=[
                    RuleCondition(
                        target=ConditionTarget.EXTENSION,
                        operator=ConditionOperator.IS_ONE_OF,
                        value=[".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt", ".csv", ".txt"],
                    )
                ],
                action=RuleAction(
                    action_type=ActionType.MOVE,
                    destination_template="Organized/Office/",
                    collision_policy=CollisionPolicy.RENAME_NEW,
                )
            ),
            Rule(
                name="Media - Audio & Video",
                description="Organize MP4, MKV, MP3, and WAV media files",
                priority=60,
                conditions=[
                    RuleCondition(
                        target=ConditionTarget.EXTENSION,
                        operator=ConditionOperator.IS_ONE_OF,
                        value=[".mp4", ".mkv", ".mov", ".avi", ".mp3", ".wav", ".flac", ".aac"],
                    )
                ],
                action=RuleAction(
                    action_type=ActionType.MOVE,
                    destination_template="Organized/Media/{category}/",
                    collision_policy=CollisionPolicy.RENAME_NEW,
                )
            ),
            Rule(
                name="Code & Projects",
                description="Organize Python, JavaScript, HTML, and code files",
                priority=70,
                conditions=[
                    RuleCondition(
                        target=ConditionTarget.EXTENSION,
                        operator=ConditionOperator.IS_ONE_OF,
                        value=[".py", ".js", ".ts", ".html", ".css", ".json", ".xml", ".cpp", ".java", ".sql"],
                    )
                ],
                action=RuleAction(
                    action_type=ActionType.MOVE,
                    destination_template="Organized/Code/",
                    collision_policy=CollisionPolicy.RENAME_NEW,
                )
            ),
        ]
        for rule in defaults:
            if rule.name not in existing_names:
                self.save(rule)
