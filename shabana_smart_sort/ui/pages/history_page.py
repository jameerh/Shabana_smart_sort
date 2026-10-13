"""History and Recovery page with audit journal inspection, CSV export, and guarded undo."""
from pathlib import Path
from typing import List, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QFileDialog, QComboBox, QLineEdit
)
from PySide6.QtCore import Qt

from shabana_smart_sort.app.dependency_container import DependencyContainer
from shabana_smart_sort.domain.operation_models import JournalEntry


class HistoryPage(QWidget):
    """Inspects operations journal, performs audited undos, and exports reports."""

    def __init__(self, container: DependencyContainer, parent=None):
        super().__init__(parent)
        self.container = container
        self.entries: List[JournalEntry] = []
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 24)

        # Header
        top_layout = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("History & Recovery")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #F8FAFC;")
        sub = QLabel("Every file operation has an audited journal entry with honest, safe undo support")
        sub.setStyleSheet("font-size: 13px; color: #94A3B8;")
        title_box.addWidget(title)
        title_box.addWidget(sub)
        top_layout.addLayout(title_box)
        top_layout.addStretch()

        # Export and reconcile buttons
        reconcile_btn = QPushButton("🛠 Reconcile Interrupted")
        reconcile_btn.clicked.connect(self._reconcile_interrupted)
        top_layout.addWidget(reconcile_btn)

        csv_btn = QPushButton("Export CSV")
        csv_btn.clicked.connect(self._export_csv)
        top_layout.addWidget(csv_btn)

        json_btn = QPushButton("Export JSON")
        json_btn.clicked.connect(self._export_json)
        top_layout.addWidget(json_btn)

        layout.addLayout(top_layout)

        # Filter bar
        filter_layout = QHBoxLayout()
        search_lbl = QLabel("Search:")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter by path or name...")
        self.search_input.textChanged.connect(self._apply_filters)
        filter_layout.addWidget(search_lbl)
        filter_layout.addWidget(self.search_input)

        status_lbl = QLabel("Status:")
        self.status_combo = QComboBox()
        self.status_combo.addItem("All Statuses", "ALL")
        self.status_combo.addItem("Succeeded", "succeeded")
        self.status_combo.addItem("Reverted", "reverted")
        self.status_combo.addItem("Failed", "failed")
        self.status_combo.currentIndexChanged.connect(self._apply_filters)
        filter_layout.addWidget(status_lbl)
        filter_layout.addWidget(self.status_combo)

        refresh_btn = QPushButton("↻ Refresh")
        refresh_btn.clicked.connect(self.reload_history)
        filter_layout.addWidget(refresh_btn)
        filter_layout.addStretch()

        layout.addLayout(filter_layout)

        # Journal Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Timestamp", "Action", "Status", "Source File", "Destination", "Undo Info", "ID"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table)

        # Action toolbar
        bottom_layout = QHBoxLayout()
        undo_single_btn = QPushButton("↩ Undo Selected Operation")
        undo_single_btn.setProperty("class", "PrimaryButton")
        undo_single_btn.clicked.connect(self._undo_selected)
        bottom_layout.addWidget(undo_single_btn)

        self.summary_label = QLabel("0 operations loaded")
        self.summary_label.setStyleSheet("color: #94A3B8; margin-left: 14px;")
        bottom_layout.addWidget(self.summary_label)

        bottom_layout.addStretch()
        layout.addLayout(bottom_layout)

        self.reload_history()

    def reload_history(self) -> None:
        """Loads journal entries from database."""
        self.entries = self.container.undo_workflow.get_history(limit=500)
        self.table.setRowCount(len(self.entries))

        for row, e in enumerate(self.entries):
            # Timestamp
            ts_str = e.executed_at.strftime("%Y-%m-%d %H:%M:%S") if e.executed_at else e.created_at.strftime("%Y-%m-%d %H:%M:%S")
            self.table.setItem(row, 0, QTableWidgetItem(ts_str))

            # Action
            self.table.setItem(row, 1, QTableWidgetItem(e.action.value.upper()))

            # Status
            status_item = QTableWidgetItem(e.status.value.upper())
            if e.status.value == "succeeded":
                status_item.setForeground(Qt.green)
            elif e.status.value == "reverted":
                status_item.setForeground(Qt.yellow)
            elif e.status.value == "failed":
                status_item.setForeground(Qt.red)
            self.table.setItem(row, 2, status_item)

            # Source
            src_item = QTableWidgetItem(Path(e.source_path).name)
            src_item.setToolTip(e.source_path)
            self.table.setItem(row, 3, src_item)

            # Destination
            dst_item = QTableWidgetItem(Path(e.destination_path).name)
            dst_item.setToolTip(e.destination_path)
            self.table.setItem(row, 4, dst_item)

            # Undo info
            undo_info = e.undo_status or ("Eligible for undo" if e.can_undo else "Not reversible")
            self.table.setItem(row, 5, QTableWidgetItem(undo_info))

            # ID
            id_item = QTableWidgetItem(e.id[:8])
            id_item.setForeground(Qt.gray)
            self.table.setItem(row, 6, id_item)

        self.summary_label.setText(f"{len(self.entries)} audit entries")
        self._apply_filters()

    def _apply_filters(self) -> None:
        query = self.search_input.text().strip().lower()
        stat_filter = self.status_combo.currentData()

        for row in range(self.table.rowCount()):
            status_item = self.table.item(row, 2)
            src_item = self.table.item(row, 3)
            dst_item = self.table.item(row, 4)

            status_match = (stat_filter == "ALL" or (status_item and status_item.text().lower() == stat_filter.lower()))
            search_match = True
            if query:
                s_text = (src_item.text().lower() if src_item else "") + (dst_item.text().lower() if dst_item else "")
                search_match = (query in s_text)

            self.table.setRowHidden(row, not (status_match and search_match))

    def _undo_selected(self) -> None:
        curr = self.table.currentRow()
        if 0 <= curr < len(self.entries):
            entry = self.entries[curr]
            if not entry.can_undo or entry.status.value != "succeeded":
                QMessageBox.warning(self, "Cannot Undo", "This operation is not eligible for undo.")
                return

            res = QMessageBox.question(
                self,
                "Confirm Undo Operation",
                f"Restore file '{Path(entry.destination_path).name}' back to its original location?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if res == QMessageBox.Yes:
                ok, msg = self.container.undo_workflow.undo_operation(entry.id)
                if ok:
                    QMessageBox.information(self, "Undo Succeeded", msg)
                else:
                    QMessageBox.warning(self, "Undo Failed", msg)
                self.reload_history()
        else:
            QMessageBox.information(self, "Select Row", "Please select an operation row to undo.")

    def _reconcile_interrupted(self) -> None:
        reconciled = self.container.recovery_service.reconcile_interrupted_jobs()
        if reconciled:
            QMessageBox.information(self, "Reconciliation Complete", f"Reconciled jobs:\n" + "\n".join(reconciled))
        else:
            QMessageBox.information(self, "Reconciliation Complete", "No interrupted jobs found in journal.")
        self.reload_history()

    def _export_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export Operations CSV", "smart_sort_audit.csv", "CSV Files (*.csv)")
        if path:
            self.container.undo_workflow.export_report_csv(Path(path))
            QMessageBox.information(self, "Export Complete", f"Report saved to:\n{path}")

    def _export_json(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export Operations JSON", "smart_sort_audit.json", "JSON Files (*.json)")
        if path:
            self.container.undo_workflow.export_report_json(Path(path))
            QMessageBox.information(self, "Export Complete", f"Report saved to:\n{path}")
