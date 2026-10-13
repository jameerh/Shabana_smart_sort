"""Dashboard overview page showing metrics, quick actions, and recent jobs."""
from pathlib import Path
from typing import Callable, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox
)
from PySide6.QtCore import Qt

from shabana_smart_sort.app.dependency_container import DependencyContainer
from shabana_smart_sort.ui.widgets.stat_card import StatCard


class DashboardPage(QWidget):
    """Main dashboard displaying high-level statistics and quick actions."""

    def __init__(self, container: DependencyContainer, on_navigate: Callable[[int], None], parent=None):
        super().__init__(parent)
        self.container = container
        self.on_navigate = on_navigate
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(18)
        layout.setContentsMargins(24, 24, 24, 24)

        # Header section
        header_layout = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Dashboard Overview")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #F8FAFC;")
        sub = QLabel("Intelligent, rule-driven folder organizer for Windows")
        sub.setStyleSheet("font-size: 13px; color: #94A3B8;")
        title_box.addWidget(title)
        title_box.addWidget(sub)
        header_layout.addLayout(title_box)
        header_layout.addStretch()

        # Quick action button
        self.quick_scan_btn = QPushButton("⚡ Scan Downloads Now")
        self.quick_scan_btn.setProperty("class", "PrimaryButton")
        self.quick_scan_btn.setMinimumHeight(38)
        self.quick_scan_btn.clicked.connect(self._on_quick_scan_downloads)
        header_layout.addWidget(self.quick_scan_btn)
        layout.addLayout(header_layout)

        # Stat cards row
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(14)
        self.card_files = StatCard("Total Scanned", "0", "Files discovered")
        self.card_rules = StatCard("Active Rules", "0", "Prioritized rules")
        self.card_ops = StatCard("Past Operations", "0", "Organized files")
        self.card_status = StatCard("Storage Status", "Ready", "Drive health verified")

        cards_layout.addWidget(self.card_files)
        cards_layout.addWidget(self.card_rules)
        cards_layout.addWidget(self.card_ops)
        cards_layout.addWidget(self.card_status)
        layout.addLayout(cards_layout)

        # Recent Sort Jobs section
        jobs_frame = QFrame()
        jobs_frame.setProperty("class", "Card")
        jobs_layout = QVBoxLayout(jobs_frame)

        jobs_title_layout = QHBoxLayout()
        jobs_title = QLabel("Recent Sorting Jobs")
        jobs_title.setStyleSheet("font-size: 15px; font-weight: 600; color: #E2E8F0;")
        view_history_btn = QPushButton("View Full History →")
        view_history_btn.clicked.connect(lambda: self.on_navigate(4))  # Tab 4: History

        jobs_title_layout.addWidget(jobs_title)
        jobs_title_layout.addStretch()
        jobs_title_layout.addWidget(view_history_btn)
        jobs_layout.addLayout(jobs_title_layout)

        self.jobs_table = QTableWidget()
        self.jobs_table.setColumnCount(6)
        self.jobs_table.setHorizontalHeaderLabels([
            "Job ID", "Date", "Source Folder", "Total Operations", "Status", "Action"
        ])
        self.jobs_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.jobs_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.jobs_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.jobs_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.jobs_table.setMinimumHeight(240)
        jobs_layout.addWidget(self.jobs_table)

        layout.addWidget(jobs_frame)
        self.refresh_data()

    def refresh_data(self) -> None:
        """Reloads metrics and past jobs from database."""
        # Active rules count
        rules = self.container.rule_workflow.get_all_rules(enabled_only=True)
        self.card_rules.set_value(str(len(rules)), f"{len(rules)} enabled rules")

        # Latest scan info
        latest_scan = self.container.scan_repo.get_latest()
        if latest_scan:
            self.card_files.set_value(str(latest_scan.total_files), f"in {Path(latest_scan.root_path).name}")
        else:
            self.card_files.set_value("0", "No scans yet")

        # Recent jobs
        recent_jobs = self.container.op_repo.get_recent_jobs(limit=10)
        total_ops = sum(j.succeeded_operations for j in recent_jobs)
        self.card_ops.set_value(str(total_ops), f"{len(recent_jobs)} completed jobs")

        self.jobs_table.setRowCount(len(recent_jobs))
        for row, job in enumerate(recent_jobs):
            self.jobs_table.setItem(row, 0, QTableWidgetItem(job.id[:8] + "..."))
            self.jobs_table.setItem(row, 1, QTableWidgetItem(job.started_at.strftime("%Y-%m-%d %H:%M")))
            self.jobs_table.setItem(row, 2, QTableWidgetItem(job.source_folder))
            self.jobs_table.setItem(row, 3, QTableWidgetItem(str(job.succeeded_operations)))

            status_item = QTableWidgetItem(job.status.value.upper())
            if job.status.value == "completed":
                status_item.setForeground(Qt.green)
            elif "fail" in job.status.value:
                status_item.setForeground(Qt.red)
            self.jobs_table.setItem(row, 4, status_item)

            # Undo button for completed jobs
            undo_btn = QPushButton("Undo Batch")
            undo_btn.setStyleSheet("padding: 3px 8px; font-size: 11px;")
            if not job.is_dry_run and job.succeeded_operations > 0:
                undo_btn.clicked.connect(lambda ch, jid=job.id: self._undo_job(jid))
            else:
                undo_btn.setEnabled(False)
            self.jobs_table.setCellWidget(row, 5, undo_btn)

    def _on_quick_scan_downloads(self) -> None:
        # Navigate to Scan page (Tab index 1)
        self.on_navigate(1)

    def _undo_job(self, job_id: str) -> None:
        res = QMessageBox.question(
            self,
            "Confirm Undo Batch",
            f"Are you sure you want to reverse all operations for job {job_id[:8]}?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if res == QMessageBox.Yes:
            succ, fail, _ = self.container.undo_workflow.undo_batch(job_id)
            QMessageBox.information(
                self,
                "Undo Completed",
                f"Batch undo finished:\n{succ} files restored safely, {fail} errors."
            )
            self.refresh_data()
