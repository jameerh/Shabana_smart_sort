"""Rule evaluation engine with condition matchers, date range semantics, and priority ordering."""
import fnmatch
import re
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple, Any

from shabana_smart_sort.domain.enums import (
    ConditionTarget,
    ConditionOperator,
    LogicalOperator,
)
from shabana_smart_sort.domain.models import FileItem
from shabana_smart_sort.domain.rule_schema import Rule, RuleCondition


class MatchResult:
    """Contains outcome and explanation of rule matching for a file."""
    def __init__(self, rule: Optional[Rule], reason: str):
        self.rule = rule
        self.reason = reason

    @property
    def is_matched(self) -> bool:
        return self.rule is not None


class RuleEngine:
    """Evaluates files against prioritized rules."""

    def __init__(self, rules: Optional[List[Rule]] = None):
        self._rules: List[Rule] = []
        if rules:
            self.set_rules(rules)

    def set_rules(self, rules: List[Rule]) -> None:
        """Sets and sorts rules by priority (ascending: lower number = higher priority)."""
        self._rules = sorted([r for r in rules if r.is_enabled], key=lambda r: (r.priority, r.name))

    def evaluate_file(self, file_item: FileItem) -> MatchResult:
        """
        Evaluates a file against all enabled rules in priority order.
        Returns the first matching rule and detailed reason.
        """
        for rule in self._rules:
            is_match, reason = self.evaluate_rule(rule, file_item)
            if is_match:
                return MatchResult(rule=rule, reason=reason)

        return MatchResult(rule=None, reason="No matching rule found (Unmatched)")

    def evaluate_rule(self, rule: Rule, item: FileItem) -> Tuple[bool, str]:
        """Evaluates a single rule against a file item."""
        if not rule.conditions:
            return True, f"Rule '{rule.name}' has no conditions (matches all)"

        matched_conditions: List[str] = []
        failed_conditions: List[str] = []

        for cond in rule.conditions:
            cond_matches, cond_reason = self._evaluate_condition(cond, item)
            if cond_matches:
                matched_conditions.append(cond_reason)
            else:
                failed_conditions.append(cond_reason)

        if rule.logical_op == LogicalOperator.ALL:
            # AND
            if len(matched_conditions) == len(rule.conditions):
                return True, f"Rule '{rule.name}' matched all conditions: " + "; ".join(matched_conditions)
            else:
                return False, f"Rule '{rule.name}' failed conditions: " + "; ".join(failed_conditions)
        else:
            # ANY (OR)
            if len(matched_conditions) > 0:
                return True, f"Rule '{rule.name}' matched condition: " + "; ".join(matched_conditions)
            else:
                return False, f"Rule '{rule.name}' matched none of the conditions"

    def _evaluate_condition(self, cond: RuleCondition, item: FileItem) -> Tuple[bool, str]:
        """Evaluates a single condition against a FileItem."""
        target_val = self._extract_target_value(cond.target, item)
        op = cond.operator
        val = cond.value

        # 1. String operations
        if op in (
            ConditionOperator.EQUALS,
            ConditionOperator.NOT_EQUALS,
            ConditionOperator.CONTAINS,
            ConditionOperator.NOT_CONTAINS,
            ConditionOperator.STARTS_WITH,
            ConditionOperator.ENDS_WITH,
            ConditionOperator.MATCHES_REGEX,
            ConditionOperator.MATCHES_WILDCARD,
        ):
            target_str = str(target_val)
            val_str = str(val)

            if not cond.case_sensitive:
                target_str_cmp = target_str.lower()
                val_str_cmp = val_str.lower()
            else:
                target_str_cmp = target_str
                val_str_cmp = val_str

            if op == ConditionOperator.EQUALS:
                res = (target_str_cmp == val_str_cmp)
                return res, f"{cond.target.value} == '{val_str}'"
            elif op == ConditionOperator.NOT_EQUALS:
                res = (target_str_cmp != val_str_cmp)
                return res, f"{cond.target.value} != '{val_str}'"
            elif op == ConditionOperator.CONTAINS:
                res = (val_str_cmp in target_str_cmp)
                return res, f"{cond.target.value} contains '{val_str}'"
            elif op == ConditionOperator.NOT_CONTAINS:
                res = (val_str_cmp not in target_str_cmp)
                return res, f"{cond.target.value} does not contain '{val_str}'"
            elif op == ConditionOperator.STARTS_WITH:
                res = target_str_cmp.startswith(val_str_cmp)
                return res, f"{cond.target.value} starts with '{val_str}'"
            elif op == ConditionOperator.ENDS_WITH:
                res = target_str_cmp.endswith(val_str_cmp)
                return res, f"{cond.target.value} ends with '{val_str}'"
            elif op == ConditionOperator.MATCHES_WILDCARD:
                res = fnmatch.fnmatch(target_str_cmp, val_str_cmp)
                return res, f"{cond.target.value} wildcard '{val_str}'"
            elif op == ConditionOperator.MATCHES_REGEX:
                flags = 0 if cond.case_sensitive else re.IGNORECASE
                try:
                    res = bool(re.search(val_str, target_str, flags=flags))
                except re.error:
                    res = False
                return res, f"{cond.target.value} matches regex '{val_str}'"

        # 2. List / Set operations (e.g. extension in [".pdf", ".docx"])
        elif op in (ConditionOperator.IS_ONE_OF, ConditionOperator.IS_NOT_ONE_OF):
            if isinstance(val, str):
                # allow comma-separated string
                items_set = {x.strip().lower() for x in val.split(",") if x.strip()}
            elif isinstance(val, (list, tuple, set)):
                items_set = {str(x).strip().lower() for x in val}
            else:
                items_set = {str(val).strip().lower()}

            target_cmp = str(target_val).lower()
            if cond.target == ConditionTarget.EXTENSION:
                # normalize dot
                normalized_items = set()
                for item_str in items_set:
                    normalized_items.add("." + item_str.lstrip("."))
                items_set = normalized_items
                target_cmp = "." + target_cmp.lstrip(".")

            is_in = target_cmp in items_set
            if op == ConditionOperator.IS_ONE_OF:
                return is_in, f"{cond.target.value} in {list(items_set)}"
            else:
                return not is_in, f"{cond.target.value} not in {list(items_set)}"

        # 3. Numeric / Size operations
        elif op in (
            ConditionOperator.LESS_THAN,
            ConditionOperator.GREATER_THAN,
            ConditionOperator.EQUALS_NUMERIC,
            ConditionOperator.BETWEEN_NUMERIC,
        ):
            try:
                target_num = float(target_val)
                if op == ConditionOperator.LESS_THAN:
                    res = target_num < float(val)
                    return res, f"{cond.target.value} < {val}"
                elif op == ConditionOperator.GREATER_THAN:
                    res = target_num > float(val)
                    return res, f"{cond.target.value} > {val}"
                elif op == ConditionOperator.EQUALS_NUMERIC:
                    res = target_num == float(val)
                    return res, f"{cond.target.value} == {val}"
                elif op == ConditionOperator.BETWEEN_NUMERIC:
                    min_val, max_val = float(val[0]), float(val[1])
                    res = min_val <= target_num <= max_val
                    return res, f"{cond.target.value} between {min_val} and {max_val}"
            except (ValueError, TypeError, IndexError):
                return False, f"Invalid numeric comparison on {cond.target.value}"

        # 4. Date operations
        elif op in (
            ConditionOperator.DATE_BEFORE,
            ConditionOperator.DATE_AFTER,
            ConditionOperator.DATE_BETWEEN,
            ConditionOperator.DATE_IN_LAST_DAYS,
        ):
            if not isinstance(target_val, datetime):
                return False, f"{cond.target.value} is not a valid datetime"

            # Compare using dates or timestamps
            now = datetime.now()
            # If target_val is timezone-aware, compare with timezone-aware now
            if target_val.tzinfo is not None:
                now = datetime.now(timezone.utc)

            if op == ConditionOperator.DATE_IN_LAST_DAYS:
                try:
                    days = int(val)
                    cutoff = now - timedelta(days=days)
                    res = target_val >= cutoff
                    return res, f"{cond.target.value} in last {days} days"
                except Exception:
                    return False, f"Invalid days value: {val}"

            elif op == ConditionOperator.DATE_BEFORE:
                dt_val = self._parse_datetime(val)
                if dt_val:
                    res = target_val < dt_val
                    return res, f"{cond.target.value} before {dt_val.date()}"
                return False, f"Invalid date: {val}"

            elif op == ConditionOperator.DATE_AFTER:
                dt_val = self._parse_datetime(val)
                if dt_val:
                    res = target_val > dt_val
                    return res, f"{cond.target.value} after {dt_val.date()}"
                return False, f"Invalid date: {val}"

            elif op == ConditionOperator.DATE_BETWEEN:
                if isinstance(val, (list, tuple)) and len(val) == 2:
                    dt_start = self._parse_datetime(val[0])
                    dt_end = self._parse_datetime(val[1])
                    if dt_start and dt_end:
                        res = dt_start <= target_val <= dt_end
                        return res, f"{cond.target.value} between {dt_start.date()} and {dt_end.date()}"
                return False, f"Invalid date range: {val}"

        # 5. Boolean operations
        elif op in (ConditionOperator.IS_TRUE, ConditionOperator.IS_FALSE):
            target_bool = bool(target_val)
            if op == ConditionOperator.IS_TRUE:
                return target_bool is True, f"{cond.target.value} is True"
            else:
                return target_bool is False, f"{cond.target.value} is False"

        return False, f"Unsupported condition: {cond.target.value} {op.value}"

    def _extract_target_value(self, target: ConditionTarget, item: FileItem) -> Any:
        if target == ConditionTarget.FILENAME:
            return item.name
        elif target == ConditionTarget.EXTENSION:
            return item.extension
        elif target == ConditionTarget.CATEGORY:
            return item.category.value
        elif target == ConditionTarget.SIZE_BYTES:
            return item.size_bytes
        elif target == ConditionTarget.DATE_MODIFIED:
            return item.modified_at
        elif target == ConditionTarget.DATE_CREATED:
            return item.created_at
        elif target == ConditionTarget.DATE_ACCESSED:
            return item.accessed_at
        elif target == ConditionTarget.IS_HIDDEN:
            return item.is_hidden
        elif target == ConditionTarget.IS_READONLY:
            return item.is_readonly
        elif target == ConditionTarget.IS_EMPTY:
            return item.is_empty
        return ""

    def _parse_datetime(self, val: Any) -> Optional[datetime]:
        if isinstance(val, datetime):
            return val
        if isinstance(val, str):
            try:
                return datetime.fromisoformat(val)
            except ValueError:
                # try date format YYYY-MM-DD
                try:
                    return datetime.strptime(val, "%Y-%m-%d")
                except ValueError:
                    return None
        return None
