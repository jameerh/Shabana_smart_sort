"""Rule manager page for viewing, creating, reordering, and testing rules."""
from pathlib import Path
from typing import List, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QFileDialog, QFrame, QCheckBox
)
from PySide6.QtCore import Qt

from shabana_smart_sort.app.dependency_container import DependencyContainer
from shabana_smart_sort.domain.rule_schema import Rule
from shabana_smart_sort.ui.dialogs.rule_dialog import RuleDialog


class RulesPage(QWidget):
    """Rule Manager UI for managing prioritized rule sets."""

    def __init__(self, container: DependencyContainer, parent=None):
        super().__init__(parent)
        self.container = container
        self.rules: List[Rule] = []
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 24)

        # Header
        top_layout = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Rule Manager")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #F8FAFC;")
        sub = QLabel("Rules are evaluated from highest priority to lowest (first match wins)")
        sub.setStyleSheet("font-size: 13px; color: #94A3B8;")
        title_box.addWidget(title)
        title_box.addWidget(sub)
        top_layout.addLayout(title_box)
        top_layout.addStretch()

        # Action buttons
        add_btn = QPushButton("+ Create Rule")
        add_btn.setProperty("class", "PrimaryButton")
        add_btn.clicked.connect(self._add_rule)
        top_layout.addWidget(add_btn)

        import_btn = QPushButton("Import JSON")
        import_btn.clicked.connect(self._import_rules)
        top_layout.addWidget(import_btn)

        export_btn = QPushButton("Export JSON")
        export_btn.clicked.connect(self._export_rules)
        top_layout.addWidget(export_btn)

        layout.addLayout(top_layout)

        # Rules Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Priority", "Rule Name", "Conditions", "Destination Folder", "Action", "Enabled", "ID"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.doubleClicked.connect(self._edit_selected_rule)
        layout.addWidget(self.table)

        # Bottom control toolbar
        bottom_layout = QHBoxLayout()
        edit_btn = QPushButton("Edit Rule")
        edit_btn.clicked.connect(self._edit_selected_rule)
        bottom_layout.addWidget(edit_btn)

        clone_btn = QPushButton("Clone Rule")
        clone_btn.clicked.connect(self._clone_selected_rule)
        bottom_layout.addWidget(clone_btn)

        up_btn = QPushButton("▲ Higher Priority")
        up_btn.clicked.connect(self._move_priority_up)
        bottom_layout.addWidget(up_btn)

        down_btn = QPushButton("▼ Lower Priority")
        down_btn.clicked.connect(self._move_priority_down)
        bottom_layout.addWidget(down_btn)

        delete_btn = QPushButton("Delete Rule")
        delete_btn.setProperty("class", "DangerButton")
        delete_btn.clicked.connect(self._delete_selected_rule)
        bottom_layout.addWidget(delete_btn)

        bottom_layout.addStretch()

        # Selective Rule Activation Controls
        enable_only_btn = QPushButton("⭐ Enable ONLY Selected Rule")
        enable_only_btn.setStyleSheet("background-color: #2563EB; font-weight: 600; padding: 6px 12px;")
        enable_only_btn.setToolTip("Deactivates all other rules so only the selected rule will match files")
        enable_only_btn.clicked.connect(self._enable_only_selected_rule)
        bottom_layout.addWidget(enable_only_btn)

        enable_all_btn = QPushButton("✓ Enable All")
        enable_all_btn.setStyleSheet("background-color: #059669; font-weight: 500; padding: 6px 10px;")
        enable_all_btn.setToolTip("Enables all rules for full comprehensive folder sorting")
        enable_all_btn.clicked.connect(self._enable_all_rules)
        bottom_layout.addWidget(enable_all_btn)

        disable_all_btn = QPushButton("✗ Disable All")
        disable_all_btn.setStyleSheet("background-color: #475569; font-weight: 500; padding: 6px 10px;")
        disable_all_btn.setToolTip("Disables all rules")
        disable_all_btn.clicked.connect(self._disable_all_rules)
        bottom_layout.addWidget(disable_all_btn)

        layout.addLayout(bottom_layout)

        self.reload_rules()

    def reload_rules(self) -> None:
        """Fetches all rules from repository and populates the table."""
        self.rules = self.container.rule_workflow.get_all_rules()
        self.table.setRowCount(len(self.rules))

        for row, rule in enumerate(self.rules):
            prio_item = QTableWidgetItem(f"#{rule.priority}")
            prio_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 0, prio_item)

            name_item = QTableWidgetItem(rule.name)
            name_item.setToolTip(rule.description)
            self.table.setItem(row, 1, name_item)

            # Conditions summary
            cond_str = ", ".join(f"{c.target.value} {c.operator.value}" for c in rule.conditions)
            if not cond_str:
                cond_str = "Matches all"
            self.table.setItem(row, 2, QTableWidgetItem(cond_str))

            dest_item = QTableWidgetItem(rule.action.destination_template)
            self.table.setItem(row, 3, dest_item)

            action_item = QTableWidgetItem(rule.action.action_type.value.upper())
            self.table.setItem(row, 4, action_item)

            # Checkbox for enabled/disabled
            chk = QCheckBox()
            chk.setChecked(rule.is_enabled)
            chk.setStyleSheet("margin-left: 12px;")
            chk.stateChanged.connect(lambda state, rid=rule.id: self._toggle_enabled(rid, bool(state)))
            self.table.setCellWidget(row, 5, chk)

            id_item = QTableWidgetItem(rule.id[:8])
            id_item.setForeground(Qt.gray)
            self.table.setItem(row, 6, id_item)

    def _toggle_enabled(self, rule_id: str, enabled: bool) -> None:
        self.container.rule_workflow.set_rule_enabled(rule_id, enabled)

    def _enable_only_selected_rule(self) -> None:
        """Enables ONLY the currently selected rule in the table, disabling all others."""
        rule = self._get_selected_rule()
        if not rule:
            QMessageBox.information(
                self, "Select Rule First",
                "Please click a rule row in the table (e.g. Satbara or Farmer IDs) then click this button."
            )
            return

        for r in self.rules:
            should_enable = (r.id == rule.id)
            self.container.rule_workflow.set_rule_enabled(r.id, should_enable)
        self.reload_rules()
        QMessageBox.information(
            self, "Selective Rule Mode Active",
            f"✓ Rule '{rule.name}' is now the ONLY active rule.\n\nAll other rules have been disabled. Only files matching this rule will be organized."
        )

    def _enable_all_rules(self) -> None:
        """Enables all rules for comprehensive sorting."""
        for r in self.rules:
            self.container.rule_workflow.set_rule_enabled(r.id, True)
        self.reload_rules()
        QMessageBox.information(self, "All Rules Enabled", "All rules are now active and will be evaluated together.")

    def _disable_all_rules(self) -> None:
        """Disables all rules."""
        for r in self.rules:
            self.container.rule_workflow.set_rule_enabled(r.id, False)
        self.reload_rules()

    def _get_selected_rule(self) -> Optional[Rule]:
        curr = self.table.currentRow()
        if 0 <= curr < len(self.rules):
            return self.rules[curr]
        return None

    def _add_rule(self) -> None:
        dlg = RuleDialog(parent=self)
        if dlg.exec() and dlg.result_rule:
            self.container.rule_workflow.save_rule(dlg.result_rule)
            self.reload_rules()

    def _edit_selected_rule(self) -> None:
        rule = self._get_selected_rule()
        if not rule:
            QMessageBox.information(self, "Select Rule", "Please select a rule from the table to edit.")
            return

        dlg = RuleDialog(rule=rule, parent=self)
        if dlg.exec() and dlg.result_rule:
            self.container.rule_workflow.save_rule(dlg.result_rule)
            self.reload_rules()

    def _clone_selected_rule(self) -> None:
        rule = self._get_selected_rule()
        if not rule:
            QMessageBox.information(self, "Select Rule", "Please select a rule to clone.")
            return
        self.container.rule_workflow.clone_rule(rule.id)
        self.reload_rules()

    def _delete_selected_rule(self) -> None:
        rule = self._get_selected_rule()
        if not rule:
            QMessageBox.information(self, "Select Rule", "Please select a rule to delete.")
            return

        res = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to permanently delete rule '{rule.name}'?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if res == QMessageBox.Yes:
            self.container.rule_workflow.delete_rule(rule.id)
            self.reload_rules()

    def _move_priority_up(self) -> None:
        row = self.table.currentRow()
        if row > 0:
            rule_ids = [r.id for r in self.rules]
            rule_ids[row], rule_ids[row - 1] = rule_ids[row - 1], rule_ids[row]
            self.container.rule_workflow.reorder_rules(rule_ids)
            self.reload_rules()
            self.table.selectRow(row - 1)

    def _move_priority_down(self) -> None:
        row = self.table.currentRow()
        if 0 <= row < len(self.rules) - 1:
            rule_ids = [r.id for r in self.rules]
            rule_ids[row], rule_ids[row + 1] = rule_ids[row + 1], rule_ids[row]
            self.container.rule_workflow.reorder_rules(rule_ids)
            self.reload_rules()
            self.table.selectRow(row + 1)

    def _export_rules(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Rules JSON", "smart_sort_rules.json", "JSON Files (*.json)"
        )
        if path:
            self.container.rule_workflow.export_rules_json(Path(path))
            QMessageBox.information(self, "Export Success", f"Rules exported successfully to:\n{path}")

    def _import_rules(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Rules JSON", "", "JSON Files (*.json)"
        )
        if path:
            count, errs = self.container.rule_workflow.import_rules_json(path)
            if errs:
                QMessageBox.warning(self, "Import Completed with Warnings", f"Imported {count} rules.\nErrors:\n" + "\n".join(errs))
            else:
                QMessageBox.information(self, "Import Success", f"Successfully imported {count} rules.")
            self.reload_rules()
