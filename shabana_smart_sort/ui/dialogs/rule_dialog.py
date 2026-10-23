"""Interactive visual rule builder dialog."""
from typing import Optional, List
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QSpinBox, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QFrame, QRadioButton, QButtonGroup
)
from PySide6.QtCore import Qt

from shabana_smart_sort.domain.enums import (
    ConditionTarget,
    ConditionOperator,
    LogicalOperator,
    ActionType,
    CollisionPolicy,
)
from shabana_smart_sort.domain.rule_schema import Rule, RuleCondition, RuleAction


class RuleDialog(QDialog):
    """Dialog for creating and editing sorting rules."""

    def __init__(self, rule: Optional[Rule] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Rule" if rule else "Create New Rule")
        self.setMinimumSize(680, 560)
        self.existing_rule = rule
        self.result_rule: Optional[Rule] = None
        self._conditions: List[RuleCondition] = list(rule.conditions) if rule else []

        self._init_ui()
        if rule:
            self._populate_from_rule(rule)
        else:
            # Default first condition
            self._conditions.append(RuleCondition(
                target=ConditionTarget.EXTENSION,
                operator=ConditionOperator.IS_ONE_OF,
                value=".pdf",
            ))
            self._refresh_conditions_table()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(14)
        main_layout.setContentsMargins(18, 18, 18, 18)

        # 1. Basic Info Card
        info_frame = QFrame()
        info_frame.setProperty("class", "Card")
        info_layout = QVBoxLayout(info_frame)

        name_layout = QHBoxLayout()
        name_label = QLabel("Rule Name:")
        name_label.setFixedWidth(100)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. Invoices & Receipts")
        name_layout.addWidget(name_label)
        name_layout.addWidget(self.name_edit)

        prio_layout = QHBoxLayout()
        prio_label = QLabel("Priority:")
        prio_label.setFixedWidth(100)
        self.prio_spin = QSpinBox()
        self.prio_spin.setRange(1, 1000)
        self.prio_spin.setValue(50)
        self.prio_spin.setToolTip("Lower number = higher priority evaluated first")
        prio_layout.addWidget(prio_label)
        prio_layout.addWidget(self.prio_spin)
        prio_layout.addStretch()

        desc_layout = QHBoxLayout()
        desc_label = QLabel("Description:")
        desc_label.setFixedWidth(100)
        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText("Optional notes about this rule")
        desc_layout.addWidget(desc_label)
        desc_layout.addWidget(self.desc_edit)

        info_layout.addLayout(name_layout)
        info_layout.addLayout(prio_layout)
        info_layout.addLayout(desc_layout)
        main_layout.addWidget(info_frame)

        # 2. Conditions Section
        cond_frame = QFrame()
        cond_frame.setProperty("class", "Card")
        cond_layout = QVBoxLayout(cond_frame)

        header_layout = QHBoxLayout()
        cond_title = QLabel("Matching Conditions")
        cond_title.setStyleSheet("font-weight: 600; font-size: 14px; color: #60A5FA;")
        header_layout.addWidget(cond_title)
        header_layout.addStretch()

        # Match mode (ALL vs ANY)
        mode_label = QLabel("Match Mode:")
        self.rb_all = QRadioButton("ALL conditions (AND)")
        self.rb_any = QRadioButton("ANY condition (OR)")
        self.rb_all.setChecked(True)
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.rb_all)
        self.mode_group.addButton(self.rb_any)
        header_layout.addWidget(mode_label)
        header_layout.addWidget(self.rb_all)
        header_layout.addWidget(self.rb_any)

        cond_layout.addLayout(header_layout)

        # Table of conditions
        self.cond_table = QTableWidget()
        self.cond_table.setColumnCount(3)
        self.cond_table.setHorizontalHeaderLabels(["Target", "Condition Operator", "Value"])
        self.cond_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.cond_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.cond_table.setMinimumHeight(120)
        cond_layout.addWidget(self.cond_table)

        btn_layout = QHBoxLayout()
        add_cond_btn = QPushButton("+ Add Condition")
        add_cond_btn.clicked.connect(self._add_condition)
        rem_cond_btn = QPushButton("- Remove Selected")
        rem_cond_btn.clicked.connect(self._remove_selected_condition)
        btn_layout.addWidget(add_cond_btn)
        btn_layout.addWidget(rem_cond_btn)
        btn_layout.addStretch()
        cond_layout.addLayout(btn_layout)

        main_layout.addWidget(cond_frame)

        # 3. Destination Template & Action
        dest_frame = QFrame()
        dest_frame.setProperty("class", "Card")
        dest_layout = QVBoxLayout(dest_frame)

        dest_title = QLabel("Destination & Action")
        dest_title.setStyleSheet("font-weight: 600; font-size: 14px; color: #60A5FA;")
        dest_layout.addWidget(dest_title)

        tpl_layout = QHBoxLayout()
        tpl_label = QLabel("Folder Template:")
        tpl_label.setFixedWidth(110)
        self.tpl_edit = QLineEdit("Organized/{category}/{year}/")
        tpl_layout.addWidget(tpl_label)
        tpl_layout.addWidget(self.tpl_edit)
        dest_layout.addLayout(tpl_layout)

        # Quick variable pill buttons
        pill_layout = QHBoxLayout()
        pill_label = QLabel("Insert Variable:")
        pill_label.setFixedWidth(110)
        pill_label.setStyleSheet("color: #94A3B8; font-size: 11px;")
        pill_layout.addWidget(pill_label)

        for var in ["{year}", "{month}", "{category}", "{extension}", "{rule_name}"]:
            btn = QPushButton(var)
            btn.setStyleSheet("padding: 2px 6px; font-size: 11px; background-color: #1E3A8A;")
            btn.clicked.connect(lambda checked, v=var: self._insert_template_var(v))
            pill_layout.addWidget(btn)
        pill_layout.addStretch()
        dest_layout.addLayout(pill_layout)

        # Collision & Action Type
        extra_layout = QHBoxLayout()
        action_label = QLabel("Action:")
        self.action_combo = QComboBox()
        self.action_combo.addItem("Move File", ActionType.MOVE)
        self.action_combo.addItem("Copy File (Preserve Original)", ActionType.COPY)

        collision_label = QLabel("When file exists:")
        self.collision_combo = QComboBox()
        self.collision_combo.addItem("Rename with (1)", CollisionPolicy.RENAME_NEW)
        self.collision_combo.addItem("Skip File", CollisionPolicy.SKIP)
        self.collision_combo.addItem("Overwrite", CollisionPolicy.OVERWRITE)

        extra_layout.addWidget(action_label)
        extra_layout.addWidget(self.action_combo)
        extra_layout.addSpacing(20)
        extra_layout.addWidget(collision_label)
        extra_layout.addWidget(self.collision_combo)
        extra_layout.addStretch()
        dest_layout.addLayout(extra_layout)

        main_layout.addWidget(dest_frame)

        # 4. Dialog Buttons
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Save Rule")
        save_btn.setProperty("class", "PrimaryButton")
        save_btn.clicked.connect(self._save_rule)
        bottom_layout.addWidget(cancel_btn)
        bottom_layout.addWidget(save_btn)
        main_layout.addLayout(bottom_layout)

    def _insert_template_var(self, var: str) -> None:
        self.tpl_edit.insert(var)

    def _refresh_conditions_table(self) -> None:
        self.cond_table.setRowCount(len(self._conditions))
        for row, cond in enumerate(self._conditions):
            # Target Combobox
            target_combo = QComboBox()
            for target in ConditionTarget:
                target_combo.addItem(target.value, target)
            idx_t = target_combo.findData(cond.target)
            if idx_t >= 0:
                target_combo.setCurrentIndex(idx_t)
            target_combo.currentIndexChanged.connect(lambda idx, r=row, cb=target_combo: self._on_target_changed(r, cb.currentData()))
            self.cond_table.setCellWidget(row, 0, target_combo)

            # Operator Combobox
            op_combo = QComboBox()
            for op in ConditionOperator:
                op_combo.addItem(op.value, op)
            idx_op = op_combo.findData(cond.operator)
            if idx_op >= 0:
                op_combo.setCurrentIndex(idx_op)
            op_combo.currentIndexChanged.connect(lambda idx, r=row, cb=op_combo: self._on_op_changed(r, cb.currentData()))
            self.cond_table.setCellWidget(row, 1, op_combo)

            # Value Item
            val_str = str(cond.value)
            if isinstance(cond.value, list):
                val_str = ", ".join(str(x) for x in cond.value)
            val_item = QTableWidgetItem(val_str)
            self.cond_table.setItem(row, 2, val_item)

    def _on_target_changed(self, row: int, new_target: ConditionTarget) -> None:
        if row < len(self._conditions):
            self._conditions[row].target = new_target

    def _on_op_changed(self, row: int, new_op: ConditionOperator) -> None:
        if row < len(self._conditions):
            self._conditions[row].operator = new_op

    def _add_condition(self) -> None:
        self._sync_table_values_to_conditions()
        self._conditions.append(RuleCondition(
            target=ConditionTarget.EXTENSION,
            operator=ConditionOperator.IS_ONE_OF,
            value=".pdf",
        ))
        self._refresh_conditions_table()

    def _sync_table_values_to_conditions(self) -> None:
        for r in range(self.cond_table.rowCount()):
            if r < len(self._conditions):
                val_item = self.cond_table.item(r, 2)
                val_text = val_item.text().strip() if val_item else ""
                if "," in val_text:
                    self._conditions[r].value = [x.strip() for x in val_text.split(",") if x.strip()]
                else:
                    self._conditions[r].value = val_text

    def _remove_selected_condition(self) -> None:
        self._sync_table_values_to_conditions()
        selected_rows = sorted({idx.row() for idx in self.cond_table.selectedIndexes()}, reverse=True)
        for r in selected_rows:
            if r < len(self._conditions):
                self._conditions.pop(r)
        self._refresh_conditions_table()

    def _populate_from_rule(self, rule: Rule) -> None:
        self.name_edit.setText(rule.name)
        self.desc_edit.setText(rule.description)
        self.prio_spin.setValue(rule.priority)
        if rule.logical_op == LogicalOperator.ANY:
            self.rb_any.setChecked(True)
        else:
            self.rb_all.setChecked(True)

        self.tpl_edit.setText(rule.action.destination_template)
        idx_act = self.action_combo.findData(rule.action.action_type)
        if idx_act >= 0:
            self.action_combo.setCurrentIndex(idx_act)

        idx_col = self.collision_combo.findData(rule.action.collision_policy)
        if idx_col >= 0:
            self.collision_combo.setCurrentIndex(idx_col)

        self._refresh_conditions_table()

    def _save_rule(self) -> None:
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation Error", "Please provide a name for this rule.")
            return

        template = self.tpl_edit.text().strip()
        if not template:
            QMessageBox.warning(self, "Validation Error", "Please provide a destination folder template.")
            return

        if not self._conditions:
            QMessageBox.warning(self, "Validation Error", "Please add at least one condition.")
            return

        # Synchronize values and combobox selections
        self._sync_table_values_to_conditions()

        rule_id = self.existing_rule.id if self.existing_rule else None
        logical_op = LogicalOperator.ANY if self.rb_any.isChecked() else LogicalOperator.ALL
        action = RuleAction(
            action_type=self.action_combo.currentData(),
            destination_template=template,
            collision_policy=self.collision_combo.currentData(),
        )

        kwargs = {
            "name": name,
            "description": self.desc_edit.text().strip(),
            "priority": self.prio_spin.value(),
            "logical_op": logical_op,
            "conditions": self._conditions,
            "action": action,
        }
        if rule_id:
            kwargs["id"] = rule_id

        self.result_rule = Rule(**kwargs)
        self.accept()
