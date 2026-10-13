"""Preview and safe execution page with side-by-side verification and collision reporting."""
from pathlib import Path
from typing import List, Optional, Callable
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox,
    QProgressBar, QFrame, QComboBox, QMessageBox, QFileDialog, QLineEdit
)
from PySide6.QtCore import Qt, QThreadPool

from shabana_smart_sort.app.dependency_container import DependencyContainer
from shabana_smart_sort.domain.enums import CollisionPolicy, OperationStatus
from shabana_smart_sort.domain.models import FileItem, PlannedOperation
from shabana_smart_sort.infrastructure.worker_manager import SortWorker


class PreviewPage(QWidget):
    """Calculates dry-run previews and safely executes sorting batches."""

    def __init__(self, container: DependencyContainer, on_complete: Callable[[], None], parent=None):
        super().__init__(parent)
        self.container = container
        self.on_complete = on_complete
        self.current_files: List[FileItem] = []
        self.planned_operations: List[PlannedOperation] = []
        self._current_worker: Optional[SortWorker] = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 24)

        # 1. Header & Metric Summary Card
        metric_frame = QFrame()
        metric_frame.setProperty("class", "Card")
        metric_layout = QVBoxLayout(metric_frame)

        title_layout = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Preview & Safe Execution")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #F8FAFC;")
        sub = QLabel("Dry-run preview: Verify planned source and destination paths before any changes occur")
        sub.setStyleSheet("font-size: 13px; color: #94A3B8;")
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
        self.lbl_collisions = QLabel("Collisions: 0")
        self.lbl_size = QLabel("Size: 0 MB")
        self.lbl_disk = QLabel("Disk: Checking...")

        for lbl in [self.lbl_total, self.lbl_matched, self.lbl_unmatched, self.lbl_collisions, self.lbl_size, self.lbl_disk]:
            lbl.setStyleSheet("font-weight: 600; padding: 4px 8px; background-color: #0F172A; border-radius: 4px;")
            self.stats_row.addWidget(lbl)
        self.stats_row.addStretch()
        metric_layout.addLayout(self.stats_row)

        layout.addWidget(metric_frame)

        # 2. Target Destination & Collision Configuration
        config_layout = QHBoxLayout()
        dest_label = QLabel("Organized Root:")
        default_target = self.container.config_mgr.get("default_organized_folder", str(Path.home() / "Downloads" / "Organized"))
        self.dest_root_input = QLineEdit(default_target)
        self.dest_root_input.textChanged.connect(self._recalculate_preview)
        browse_dest_btn = QPushButton("Browse...")
        browse_dest_btn.clicked.connect(self._browse_dest_root)

        col_label = QLabel("Collision Policy:")
        self.policy_combo = QComboBox()
        self.policy_combo.addItem("Auto-Rename with (1)", CollisionPolicy.RENAME_NEW)
        self.policy_combo.addItem("Skip Colliding Files", CollisionPolicy.SKIP)
        self.policy_combo.addItem("Overwrite Target", CollisionPolicy.OVERWRITE)
        self.policy_combo.currentIndexChanged.connect(self._recalculate_preview)

        recalc_btn = QPushButton("↻ Refresh Plan")
        recalc_btn.clicked.connect(self._recalculate_preview)

        config_layout.addWidget(dest_label)
        config_layout.addWidget(self.dest_root_input)
        config_layout.addWidget(browse_dest_btn)
        config_layout.addSpacing(10)
        config_layout.addWidget(col_label)
        config_layout.addWidget(self.policy_combo)
        config_layout.addWidget(recalc_btn)
        layout.addLayout(config_layout)

        # 3. Table of Operations
        table_ctrl_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.setStyleSheet("padding: 2px 8px; font-size: 11px;")
        select_all_btn.clicked.connect(lambda: self._set_all_selected(True))
        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.setStyleSheet("padding: 2px 8px; font-size: 11px;")
        deselect_all_btn.clicked.connect(lambda: self._set_all_selected(False))
        table_ctrl_layout.addWidget(select_all_btn)
        table_ctrl_layout.addWidget(deselect_all_btn)
        table_ctrl_layout.addStretch()
        layout.addLayout(table_ctrl_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Execute", "Source File", "Proposed Destination", "Matched Rule", "Collision / Status", "Size"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table)

        # 4. Progress and Execution
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.exec_status_label = QLabel("")
        self.exec_status_label.setStyleSheet("color: #60A5FA; font-weight: 500;")
        layout.addWidget(self.exec_status_label)

        action_layout = QHBoxLayout()
        action_layout.addStretch()

        self.dry_run_btn = QPushButton("🔍 Run Dry-Run (No Files Moved)")
        self.dry_run_btn.setStyleSheet("background-color: #0369A1; font-weight: 600; padding: 10px 18px;")
        self.dry_run_btn.clicked.connect(lambda: self._start_execution(is_dry_run=True))
        action_layout.addWidget(self.dry_run_btn)

        self.execute_btn = QPushButton("⚡ Execute Safe Organization")
        self.execute_btn.setProperty("class", "SuccessButton")
        self.execute_btn.setStyleSheet("padding: 10px 20px; font-size: 14px;")
        self.execute_btn.clicked.connect(lambda: self._start_execution(is_dry_run=False))
        action_layout.addWidget(self.execute_btn)

        self.cancel_exec_btn = QPushButton("Cancel Execution")
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

    def _recalculate_preview(self) -> None:
        if not self.current_files:
            self.lbl_total.setText("Total: 0")
            self.table.setRowCount(0)
            return

        dest_root = Path(self.dest_root_input.text().strip())
        policy = self.policy_combo.currentData() or CollisionPolicy.RENAME_NEW
        rules = self.container.rule_workflow.get_all_rules(enabled_only=True)

        report = self.container.preview_workflow.generate_preview(
            files=self.current_files,
            rules=rules,
            target_root=dest_root,
            default_collision_policy=policy,
        )

        self.planned_operations = report.operations

        # Update stats
        self.lbl_total.setText(f"Total: {report.total_files}")
        self.lbl_matched.setText(f"Matched: {report.matched_count}")
        self.lbl_unmatched.setText(f"Unmatched: {report.unmatched_count}")
        self.lbl_collisions.setText(f"Collisions: {report.collision_count}")
        size_mb = report.total_bytes_to_move / (1024 * 1024)
        self.lbl_size.setText(f"Size: {size_mb:.1f} MB")

        free_gb = report.free_disk_space_bytes / (1024 * 1024 * 1024)
        if report.sufficient_disk_space:
            self.lbl_disk.setText(f"Disk: {free_gb:.1f} GB Free ✓")
            self.lbl_disk.setStyleSheet("color: #10B981; font-weight: 600; padding: 4px 8px; background-color: #0F172A;")
        else:
            self.lbl_disk.setText("Disk: Insufficient Space ✗")
            self.lbl_disk.setStyleSheet("color: #EF4444; font-weight: 600; padding: 4px 8px; background-color: #0F172A;")

        self._populate_table()

    def _format_size(self, size_bytes: int) -> str:
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"

    def _populate_table(self) -> None:
        self.table.setRowCount(len(self.planned_operations))

        for row, op in enumerate(self.planned_operations):
            # Checkbox
            chk = QCheckBox()
            chk.setChecked(op.selected_for_execution)
            chk.stateChanged.connect(lambda state, idx=row: self._toggle_op_selection(idx, bool(state)))
            self.table.setCellWidget(row, 0, chk)

            # Source file
            src_name = Path(op.source_path).name
            src_item = QTableWidgetItem(src_name)
            src_item.setToolTip(op.source_path)
            self.table.setItem(row, 1, src_item)

            # Proposed Destination
            dst_item = QTableWidgetItem(op.destination_path)
            dst_item.setToolTip(op.destination_path)
            self.table.setItem(row, 2, dst_item)

            # Rule & Reason
            rule_name = op.matched_rule_name or "Unmatched"
            rule_item = QTableWidgetItem(rule_name)
            rule_item.setToolTip(op.match_reason)
            self.table.setItem(row, 3, rule_item)

            # Collision / Status
            if op.collision_detected:
                status_text = f"Collision ({op.collision_policy_applied.value})"
                status_item = QTableWidgetItem(status_text)
                status_item.setForeground(Qt.yellow)
            elif op.matched_rule_id is None:
                status_item = QTableWidgetItem("Leave in place")
                status_item.setForeground(Qt.gray)
            else:
                status_item = QTableWidgetItem("Ready")
                status_item.setForeground(Qt.green)
            self.table.setItem(row, 4, status_item)

            # Size
            self.table.setItem(row, 5, QTableWidgetItem(self._format_size(op.file_size)))

    def _toggle_op_selection(self, index: int, selected: bool) -> None:
        if 0 <= index < len(self.planned_operations):
            self.planned_operations[index].selected_for_execution = selected

    def _set_all_selected(self, selected: bool) -> None:
        for r in range(self.table.rowCount()):
            chk = self.table.cellWidget(r, 0)
            if isinstance(chk, QCheckBox):
                chk.setChecked(selected)
        for op in self.planned_operations:
            op.selected_for_execution = selected

    def _start_execution(self, is_dry_run: bool) -> None:
        selected_ops = [op for op in self.planned_operations if op.selected_for_execution]
        if not selected_ops:
            QMessageBox.information(self, "No Files Selected", "Please select at least one file to organize.")
            return

        if not is_dry_run:
            dest_root = self.dest_root_input.text().strip()
            confirm_msg = (
                f"You are about to organize {len(selected_ops)} files into:\n"
                f"{dest_root}\n\n"
                f"• All operations are logged to the audit journal.\n"
                f"• An honest Undo is available if needed.\n\n"
                f"Proceed with live execution?"
            )
            res = QMessageBox.question(self, "Confirm File Organization", confirm_msg, QMessageBox.Yes | QMessageBox.No)
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
