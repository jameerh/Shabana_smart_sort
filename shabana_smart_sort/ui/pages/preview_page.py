"""Preview and safe execution page with side-by-side verification, collision reporting, and batch renaming."""
from pathlib import Path
from datetime import datetime, date
from typing import List, Optional, Callable
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox,
    QProgressBar, QFrame, QComboBox, QMessageBox, QFileDialog, QLineEdit,
    QDateEdit, QSpinBox
)
from PySide6.QtCore import Qt, QDate, QThreadPool

from shabana_smart_sort.app.dependency_container import DependencyContainer
from shabana_smart_sort.domain.enums import CollisionPolicy, OperationStatus
from shabana_smart_sort.domain.models import FileItem, PlannedOperation
from shabana_smart_sort.infrastructure.worker_manager import SortWorker


class PreviewPage(QWidget):
    """Calculates dry-run previews, handles batch renaming, folder overrides, and safe execution."""

    def __init__(self, container: DependencyContainer, on_complete: Callable[[], None], parent=None):
        super().__init__(parent)
        self.container = container
        self.on_complete = on_complete
        self.current_files: List[FileItem] = []
        self.planned_operations: List[PlannedOperation] = []
        self._current_worker: Optional[SortWorker] = None
        self._filter_tag: str = "ALL"
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # 1. Header & Metric Summary Card
        metric_frame = QFrame()
        metric_frame.setProperty("class", "Card")
        metric_layout = QVBoxLayout(metric_frame)
        metric_layout.setSpacing(8)

        title_layout = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Preview & One-Click Organization")
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #F8FAFC;")
        sub = QLabel("Filter by Satbara, Farmer 27_, WhatsApp, dates, optionally rename, and move with 1-click confirmation")
        sub.setStyleSheet("font-size: 12px; color: #94A3B8;")
        title_box.addWidget(title)
        title_box.addWidget(sub)
        title_layout.addLayout(title_box)
        title_layout.addStretch()

        metric_layout.addLayout(title_layout)

        # Status counts row
        self.stats_row = QHBoxLayout()
        self.lbl_total = QLabel("Total: 0")
        self.lbl_matched = QLabel("Matched: 0")
        self.lbl_unmatched = QLabel("Unmatched: 0")
        self.lbl_selected = QLabel("Selected: 0")
        self.lbl_size = QLabel("Size: 0 MB")
        self.lbl_disk = QLabel("Disk: Checking...")

        for lbl in [self.lbl_total, self.lbl_matched, self.lbl_unmatched, self.lbl_selected, self.lbl_size, self.lbl_disk]:
            lbl.setStyleSheet("font-weight: 600; padding: 3px 8px; background-color: #0F172A; border-radius: 4px; font-size: 12px;")
            self.stats_row.addWidget(lbl)
        self.stats_row.addStretch()
        metric_layout.addLayout(self.stats_row)

        layout.addWidget(metric_frame)

        # 2. Smart Quick Filter Chips & Date Range Filter Toolbar
        filter_frame = QFrame()
        filter_frame.setProperty("class", "Card")
        filter_box = QVBoxLayout(filter_frame)
        filter_box.setSpacing(8)
        filter_box.setContentsMargins(10, 8, 10, 8)

        # Row A: Quick Smart Presets & Rule Filter
        presets_row = QHBoxLayout()
        preset_lbl = QLabel("Smart Filters:")
        preset_lbl.setStyleSheet("font-weight: 600; color: #60A5FA; font-size: 12px;")
        presets_row.addWidget(preset_lbl)

        chips = [
            ("All Files", "ALL"),
            ("📜 Satbara (7/12)", "SATBARA"),
            ("🌾 Farmer IDs (27_)", "FARMER_27"),
            ("💬 WhatsApp Images", "WHATSAPP"),
            ("📑 All PDFs", "PDF"),
            ("🖼 All Images", "IMAGE"),
        ]
        self.chip_buttons = []
        for label, tag in chips:
            btn = QPushButton(label)
            btn.setStyleSheet("padding: 3px 10px; font-size: 11px;")
            btn.clicked.connect(lambda ch, t=tag: self._set_preset_filter(t))
            presets_row.addWidget(btn)
            self.chip_buttons.append(btn)

        presets_row.addSpacing(12)
        rule_lbl = QLabel("Filter by Rule:")
        rule_lbl.setStyleSheet("font-weight: 600; color: #E2E8F0; font-size: 12px;")
        presets_row.addWidget(rule_lbl)
        self.rule_combo = QComboBox()
        self.rule_combo.setMinimumWidth(160)
        self.rule_combo.addItem("All Rules", "ALL")
        self.rule_combo.currentIndexChanged.connect(self._apply_table_visibility)
        presets_row.addWidget(self.rule_combo)

        presets_row.addStretch()
        filter_box.addLayout(presets_row)

        # Row B: Date Range, Search Text & Selection Tools
        filter_ctrls_row = QHBoxLayout()
        search_lbl = QLabel("Search:")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter name...")
        self.search_input.setFixedWidth(140)
        self.search_input.textChanged.connect(self._apply_table_visibility)
        filter_ctrls_row.addWidget(search_lbl)
        filter_ctrls_row.addWidget(self.search_input)

        self.date_filter_chk = QCheckBox("Filter Date:")
        self.date_filter_chk.stateChanged.connect(self._apply_table_visibility)
        filter_ctrls_row.addWidget(self.date_filter_chk)

        # From date
        lbl_from = QLabel("From:")
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate().addDays(-30))
        self.date_from.dateChanged.connect(self._apply_table_visibility)
        filter_ctrls_row.addWidget(lbl_from)
        filter_ctrls_row.addWidget(self.date_from)

        # To date
        lbl_to = QLabel("To:")
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        self.date_to.dateChanged.connect(self._apply_table_visibility)
        filter_ctrls_row.addWidget(lbl_to)
        filter_ctrls_row.addWidget(self.date_to)

        filter_ctrls_row.addSpacing(10)

        # Targeted Selection Buttons
        sel_only_visible_btn = QPushButton("🎯 Select ONLY Filtered / Visible")
        sel_only_visible_btn.setStyleSheet("padding: 4px 10px; font-size: 11px; background-color: #2563EB; font-weight: 700; color: #FFFFFF;")
        sel_only_visible_btn.setToolTip("Unchecks all hidden files and checks ONLY currently visible files for moving")
        sel_only_visible_btn.clicked.connect(self._select_only_filtered)
        filter_ctrls_row.addWidget(sel_only_visible_btn)

        sel_all_btn = QPushButton("Select All")
        sel_all_btn.setStyleSheet("padding: 4px 8px; font-size: 11px;")
        sel_all_btn.clicked.connect(lambda: self._set_all_selected(True))
        filter_ctrls_row.addWidget(sel_all_btn)

        desel_all_btn = QPushButton("Deselect All")
        desel_all_btn.setStyleSheet("padding: 4px 8px; font-size: 11px; background-color: #475569;")
        desel_all_btn.clicked.connect(lambda: self._set_all_selected(False))
        filter_ctrls_row.addWidget(desel_all_btn)

        filter_ctrls_row.addStretch()
        filter_box.addLayout(filter_ctrls_row)
        layout.addWidget(filter_frame)

        # 3. Action Tools: Custom Destination Override & Sequential Batch Renamer
        tools_frame = QFrame()
        tools_frame.setProperty("class", "Card")
        tools_layout = QHBoxLayout(tools_frame)
        tools_layout.setContentsMargins(10, 8, 10, 8)
        tools_layout.setSpacing(10)

        # Custom Output Folder button
        override_dest_btn = QPushButton("📁 Set Output Folder for Selected Files...")
        override_dest_btn.setStyleSheet("background-color: #1E3A8A; font-weight: 600; padding: 5px 10px;")
        override_dest_btn.clicked.connect(self._override_selected_dest_folder)
        tools_layout.addWidget(override_dest_btn)

        # Divider
        div = QLabel("|")
        div.setStyleSheet("color: #475569;")
        tools_layout.addWidget(div)

        # Sequential Rename Controls
        rename_lbl = QLabel("Rename Prefix:")
        rename_lbl.setStyleSheet("font-weight: 500;")
        self.prefix_input = QLineEdit()
        self.prefix_input.setPlaceholderText("e.g. xyz")
        self.prefix_input.setFixedWidth(80)

        counter_lbl = QLabel("Start #:")
        self.counter_spin = QSpinBox()
        self.counter_spin.setRange(1, 99999)
        self.counter_spin.setValue(1)
        self.counter_spin.setFixedWidth(55)

        apply_rename_btn = QPushButton("Apply Sequential Rename (xyz_1, xyz_2...)")
        apply_rename_btn.setStyleSheet("background-color: #047857; font-weight: 600; padding: 5px 10px;")
        apply_rename_btn.clicked.connect(self._apply_batch_rename)

        reset_rename_btn = QPushButton("↺ Revert to Original Names")
        reset_rename_btn.setStyleSheet("background-color: #475569; padding: 5px 10px;")
        reset_rename_btn.clicked.connect(self._reset_batch_rename)

        tools_layout.addWidget(rename_lbl)
        tools_layout.addWidget(self.prefix_input)
        tools_layout.addWidget(counter_lbl)
        tools_layout.addWidget(self.counter_spin)
        tools_layout.addWidget(apply_rename_btn)
        tools_layout.addWidget(reset_rename_btn)
        tools_layout.addStretch()

        layout.addWidget(tools_frame)

        # 4. Operations Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Move", "Source Filename", "Target Destination Path", "Matched Rule", "Rename Applied", "Date Modified", "Size"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table)

        # 5. Progress Bar and Execution Action Row
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.exec_status_label = QLabel("")
        self.exec_status_label.setStyleSheet("color: #60A5FA; font-weight: 500;")
        layout.addWidget(self.exec_status_label)

        action_layout = QHBoxLayout()

        # Destination Root settings display
        dest_root_lbl = QLabel("Base Root:")
        default_target = self.container.config_mgr.get("default_organized_folder", str(Path.home() / "Downloads" / "Organized"))
        self.dest_root_input = QLineEdit(default_target)
        self.dest_root_input.setFixedWidth(240)
        self.dest_root_input.textChanged.connect(self._recalculate_preview)
        browse_dest_btn = QPushButton("Browse...")
        browse_dest_btn.clicked.connect(self._browse_dest_root)

        action_layout.addWidget(dest_root_lbl)
        action_layout.addWidget(self.dest_root_input)
        action_layout.addWidget(browse_dest_btn)

        action_layout.addStretch()

        self.dry_run_btn = QPushButton("🔍 Dry-Run Test")
        self.dry_run_btn.setStyleSheet("background-color: #0369A1; font-weight: 600; padding: 9px 16px;")
        self.dry_run_btn.clicked.connect(lambda: self._start_execution(is_dry_run=True))
        action_layout.addWidget(self.dry_run_btn)

        # Prominent One-Click Move Button
        self.execute_btn = QPushButton("⚡ One-Click Move Selected Files")
        self.execute_btn.setProperty("class", "SuccessButton")
        self.execute_btn.setStyleSheet("padding: 9px 24px; font-size: 14px; font-weight: 700; background-color: #059669;")
        self.execute_btn.clicked.connect(lambda: self._start_execution(is_dry_run=False))
        action_layout.addWidget(self.execute_btn)

        self.cancel_exec_btn = QPushButton("Cancel")
        self.cancel_exec_btn.setProperty("class", "DangerButton")
        self.cancel_exec_btn.setEnabled(False)
        self.cancel_exec_btn.clicked.connect(self._cancel_execution)
        action_layout.addWidget(self.cancel_exec_btn)

        layout.addLayout(action_layout)

    def set_files_to_preview(self, files: List[FileItem]) -> None:
        """Called when navigating from the Scan page."""
        self.current_files = files
        self._recalculate_preview()

    def _browse_dest_root(self) -> None:
        curr = self.dest_root_input.text()
        chosen = QFileDialog.getExistingDirectory(self, "Select Organized Destination Root", curr)
        if chosen:
            self.dest_root_input.setText(chosen)

    def _set_preset_filter(self, tag: str) -> None:
        self._filter_tag = tag
        if hasattr(self, "rule_combo"):
            self.rule_combo.blockSignals(True)
            self.rule_combo.setCurrentIndex(0)
            self.rule_combo.blockSignals(False)
        self._apply_table_visibility()

    def _recalculate_preview(self) -> None:
        if not self.current_files:
            self.lbl_total.setText("Total: 0")
            self.table.setRowCount(0)
            return

        dest_root = Path(self.dest_root_input.text().strip())
        policy = CollisionPolicy.RENAME_NEW
        rules = self.container.rule_workflow.get_all_rules(enabled_only=True)

        report = self.container.preview_workflow.generate_preview(
            files=self.current_files,
            rules=rules,
            target_root=dest_root,
            default_collision_policy=policy,
        )

        self.planned_operations = report.operations

        # Populate rule combo with unique matched rules
        if hasattr(self, "rule_combo"):
            self.rule_combo.blockSignals(True)
            self.rule_combo.clear()
            self.rule_combo.addItem("All Rules", "ALL")
            seen_rules = set()
            for op in self.planned_operations:
                rname = op.matched_rule_name or "Unmatched (Ignored)"
                if rname not in seen_rules:
                    seen_rules.add(rname)
                    self.rule_combo.addItem(rname, rname)
            self.rule_combo.blockSignals(False)

        # Update stats
        self.lbl_total.setText(f"Total: {report.total_files}")
        self.lbl_matched.setText(f"Matched: {report.matched_count}")
        self.lbl_unmatched.setText(f"Unmatched: {report.unmatched_count}")
        size_mb = report.total_bytes_to_move / (1024 * 1024)
        self.lbl_size.setText(f"Size: {size_mb:.1f} MB")

        free_gb = report.free_disk_space_bytes / (1024 * 1024 * 1024)
        if report.sufficient_disk_space:
            self.lbl_disk.setText(f"Disk: {free_gb:.1f} GB Free ✓")
            self.lbl_disk.setStyleSheet("color: #10B981; font-weight: 600; padding: 3px 8px; background-color: #0F172A;")
        else:
            self.lbl_disk.setText("Disk: Low Space ✗")
            self.lbl_disk.setStyleSheet("color: #EF4444; font-weight: 600; padding: 3px 8px; background-color: #0F172A;")

        self._populate_table()

    def _format_size(self, size_bytes: int) -> str:
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"

    def _populate_table(self) -> None:
        self.table.setRowCount(len(self.planned_operations))

        # Build mapping from source_path to FileItem for dates
        file_map = {str(item.path): item for item in self.current_files}

        for row, op in enumerate(self.planned_operations):
            # 0. Checkbox
            chk = QCheckBox()
            chk.setChecked(op.selected_for_execution)
            chk.stateChanged.connect(lambda state, idx=row: self._toggle_op_selection(idx, bool(state)))
            self.table.setCellWidget(row, 0, chk)

            # 1. Source filename
            src_name = Path(op.source_path).name
            src_item = QTableWidgetItem(src_name)
            src_item.setToolTip(op.source_path)
            self.table.setItem(row, 1, src_item)

            # 2. Destination path
            dst_item = QTableWidgetItem(op.destination_path)
            dst_item.setToolTip(op.destination_path)
            self.table.setItem(row, 2, dst_item)

            # 3. Rule
            rule_name = op.matched_rule_name or "Unmatched"
            rule_item = QTableWidgetItem(rule_name)
            rule_item.setToolTip(op.match_reason)
            self.table.setItem(row, 3, rule_item)

            # 4. Rename applied
            rename_text = op.rename_applied or "—"
            rename_item = QTableWidgetItem(rename_text)
            if op.rename_applied:
                rename_item.setForeground(Qt.cyan)
            self.table.setItem(row, 4, rename_item)

            # 5. Date Modified
            f_item = file_map.get(op.source_path)
            mod_str = f_item.modified_at.strftime("%Y-%m-%d %H:%M") if f_item else "—"
            self.table.setItem(row, 5, QTableWidgetItem(mod_str))

            # 6. Size
            self.table.setItem(row, 6, QTableWidgetItem(self._format_size(op.file_size)))

        self._apply_table_visibility()

    def _toggle_op_selection(self, index: int, selected: bool) -> None:
        if 0 <= index < len(self.planned_operations):
            self.planned_operations[index].selected_for_execution = selected
            self._update_selected_count_label()

    def _set_all_selected(self, selected: bool) -> None:
        for r in range(self.table.rowCount()):
            chk = self.table.cellWidget(r, 0)
            if isinstance(chk, QCheckBox):
                chk.setChecked(selected)
        for op in self.planned_operations:
            op.selected_for_execution = selected
        self._update_selected_count_label()

    def _select_only_filtered(self) -> None:
        """Selects ONLY visible/filtered rows and unselects all hidden rows."""
        for r in range(self.table.rowCount()):
            is_visible = not self.table.isRowHidden(r)
            chk = self.table.cellWidget(r, 0)
            if isinstance(chk, QCheckBox):
                chk.setChecked(is_visible)
            if 0 <= r < len(self.planned_operations):
                self.planned_operations[r].selected_for_execution = is_visible
        self._update_selected_count_label()

    def _set_filtered_selected(self, selected: bool) -> None:
        """Legacy helper for programmatic selection."""
        for r in range(self.table.rowCount()):
            if not self.table.isRowHidden(r):
                chk = self.table.cellWidget(r, 0)
                if isinstance(chk, QCheckBox):
                    chk.setChecked(selected)
                if 0 <= r < len(self.planned_operations):
                    self.planned_operations[r].selected_for_execution = selected
        self._update_selected_count_label()

    def _update_selected_count_label(self) -> None:
        total_selected = sum(1 for op in self.planned_operations if op.selected_for_execution)
        visible_selected = sum(
            1 for r in range(min(self.table.rowCount(), len(self.planned_operations)))
            if not self.table.isRowHidden(r) and self.planned_operations[r].selected_for_execution
        )
        self.lbl_selected.setText(f"Selected: {total_selected} ({visible_selected} visible)")
        self.execute_btn.setText(f"⚡ One-Click Move Selected Files ({total_selected})")

    def _apply_table_visibility(self) -> None:
        query = self.search_input.text().strip().lower()
        tag = self._filter_tag
        use_date = self.date_filter_chk.isChecked()

        q_from = self.date_from.date().toPython()
        q_to = self.date_to.date().toPython()

        file_map = {str(item.path): item for item in self.current_files}

        # Rule filter dropdown
        selected_rule = "ALL"
        if hasattr(self, "rule_combo"):
            selected_rule = self.rule_combo.currentData() or "ALL"

        for row in range(self.table.rowCount()):
            if row >= len(self.planned_operations):
                continue
            op = self.planned_operations[row]
            src_name = Path(op.source_path).name.lower()
            dst_name = Path(op.destination_path).name.lower()
            rule_name = (op.matched_rule_name or "").lower()

            # 1. Smart Preset filter
            tag_match = True
            if tag == "SATBARA":
                tag_match = ("satbara" in src_name and src_name.endswith(".pdf"))
            elif tag == "FARMER_27":
                tag_match = (src_name.startswith("27_") and src_name.endswith(".pdf"))
            elif tag == "WHATSAPP":
                tag_match = ("whatsapp" in src_name)
            elif tag == "PDF":
                tag_match = src_name.endswith(".pdf")
            elif tag == "IMAGE":
                tag_match = any(src_name.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp"])

            # 2. Text Search
            search_match = True
            if query:
                search_match = (query in src_name or query in dst_name or query in rule_name)

            # 3. Date Range
            date_match = True
            if use_date:
                f_item = file_map.get(op.source_path)
                if f_item:
                    f_date = f_item.modified_at.date()
                    date_match = (q_from <= f_date <= q_to)

            # 4. Rule Dropdown Match
            rule_match = True
            if selected_rule != "ALL":
                op_rule = op.matched_rule_name or "Unmatched (Ignored)"
                rule_match = (op_rule == selected_rule)

            is_visible = tag_match and search_match and date_match and rule_match
            self.table.setRowHidden(row, not is_visible)

        self._update_selected_count_label()

    def _override_selected_dest_folder(self) -> None:
        """Allows user to select an output folder directly for currently selected files."""
        selected_ops = [op for op in self.planned_operations if op.selected_for_execution]
        if not selected_ops:
            QMessageBox.information(self, "No Files Selected", "Please select the files you want to set an output folder for.")
            return

        chosen_folder = QFileDialog.getExistingDirectory(
            self, f"Select Output Folder for {len(selected_ops)} Files", str(Path.home())
        )
        if chosen_folder:
            count = self.container.preview_workflow.override_output_directory(
                self.planned_operations, Path(chosen_folder), selected_only=True
            )
            # Update table destinations
            for row, op in enumerate(self.planned_operations):
                dst_item = self.table.item(row, 2)
                if dst_item:
                    dst_item.setText(op.destination_path)
            QMessageBox.information(
                self, "Output Folder Updated",
                f"Updated destination for {count} files to:\n{chosen_folder}"
            )

    def _apply_batch_rename(self) -> None:
        """Sequentially renames selected files e.g. xyz_1, xyz_2, xyz_3..."""
        prefix = self.prefix_input.text().strip()
        if not prefix:
            QMessageBox.warning(self, "Missing Prefix", "Please enter a rename prefix (e.g. 'xyz').")
            return

        start_num = self.counter_spin.value()
        selected_ops = [op for op in self.planned_operations if op.selected_for_execution]
        if not selected_ops:
            QMessageBox.information(self, "No Files Selected", "Please select files to rename.")
            return

        count = self.container.preview_workflow.apply_sequential_rename(
            self.planned_operations, prefix=prefix, start_counter=start_num, selected_only=True
        )

        # Refresh table rows
        for row, op in enumerate(self.planned_operations):
            dst_item = self.table.item(row, 2)
            if dst_item:
                dst_item.setText(op.destination_path)
            rename_item = self.table.item(row, 4)
            if rename_item:
                rename_item.setText(op.rename_applied or "—")
                if op.rename_applied:
                    rename_item.setForeground(Qt.cyan)

        QMessageBox.information(
            self, "Sequential Rename Applied",
            f"Successfully prepared {count} files with prefix '{prefix}_' starting from {start_num}."
        )

    def _reset_batch_rename(self) -> None:
        """Reverts destination filenames back to original."""
        self.container.preview_workflow.reset_renames(self.planned_operations)
        for row, op in enumerate(self.planned_operations):
            dst_item = self.table.item(row, 2)
            if dst_item:
                dst_item.setText(op.destination_path)
            rename_item = self.table.item(row, 4)
            if rename_item:
                rename_item.setText("—")
                rename_item.setForeground(Qt.white)

    def _start_execution(self, is_dry_run: bool) -> None:
        selected_ops = [op for op in self.planned_operations if op.selected_for_execution]
        if not selected_ops:
            QMessageBox.information(self, "No Files Selected", "Please select at least one file to organize.")
            return

        if not is_dry_run:
            # Explicit confirmation dialog
            sample_dest = str(Path(selected_ops[0].destination_path).parent)
            renamed_count = sum(1 for op in selected_ops if op.rename_applied)
            rename_summary = f"• Renaming: {renamed_count} files sequentially renamed\n" if renamed_count > 0 else "• Renaming: Original filenames preserved\n"

            confirm_msg = (
                f"You are about to organize {len(selected_ops)} files.\n\n"
                f"• Target Folder: {sample_dest}\n"
                f"{rename_summary}"
                f"• All operations are logged to the audit journal.\n"
                f"• An honest Undo is available if needed.\n\n"
                f"Do you want to proceed and move these files now?"
            )
            res = QMessageBox.question(
                self,
                "Confirm File Movement",
                confirm_msg,
                QMessageBox.Yes | QMessageBox.No,
            )
            if res != QMessageBox.Yes:
                return

        self.dry_run_btn.setEnabled(False)
        self.execute_btn.setEnabled(False)
        self.cancel_exec_btn.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, len(selected_ops))
        self.progress_bar.setValue(0)

        src_folder = Path(selected_ops[0].source_path).parent
        target_folder = Path(self.dest_root_input.text().strip())

        worker = SortWorker(
            workflow=self.container.sort_workflow,
            operations=self.planned_operations,
            source_folder=src_folder,
            target_folder=target_folder,
            is_dry_run=is_dry_run,
        )
        self._current_worker = worker
        worker.signals.progress.connect(self._on_exec_progress)
        worker.signals.finished.connect(self._on_exec_finished)
        worker.signals.error.connect(self._on_exec_error)

        QThreadPool.globalInstance().start(worker)

    def _cancel_execution(self) -> None:
        if self._current_worker:
            self._current_worker.cancel()
            self.exec_status_label.setText("Cancelling execution safely...")

    def _on_exec_progress(self, current: int, total: int, filename: str, status: str) -> None:
        self.progress_bar.setValue(current)
        self.exec_status_label.setText(f"[{current}/{total}] {filename}: {status}")

    def _on_exec_finished(self, report) -> None:
        self.dry_run_btn.setEnabled(True)
        self.execute_btn.setEnabled(True)
        self.cancel_exec_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        self._current_worker = None

        mode = "Dry-Run" if report.is_dry_run else "Live Execution"
        msg = (
            f"{mode} Finished:\n"
            f"• Succeeded: {report.succeeded}\n"
            f"• Failed: {report.failed}\n"
            f"• Skipped: {report.skipped}\n\n"
            f"Audit journal record has been saved."
        )
        QMessageBox.information(self, f"{mode} Complete", msg)
        self.exec_status_label.setText(f"{mode} completed. {report.succeeded} files processed.")

        if not report.is_dry_run:
            self.on_complete()

    def _on_exec_error(self, err_msg: str) -> None:
        self.dry_run_btn.setEnabled(True)
        self.execute_btn.setEnabled(True)
        self.cancel_exec_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        self._current_worker = None
        QMessageBox.critical(self, "Execution Error", f"Execution failed:\n{err_msg}")
