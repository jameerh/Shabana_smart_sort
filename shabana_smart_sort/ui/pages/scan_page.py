"""Scan and filter page for discovering folder contents with background workers."""
from pathlib import Path
from typing import List, Optional, Callable
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QCheckBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QProgressBar, QFrame, QComboBox, QMessageBox
)
from PySide6.QtCore import Qt, QThreadPool

from shabana_smart_sort.app.dependency_container import DependencyContainer
from shabana_smart_sort.domain.enums import FileCategory
from shabana_smart_sort.domain.models import FileItem
from shabana_smart_sort.infrastructure.worker_manager import ScanWorker


class ScanPage(QWidget):
    """Allows selecting a directory, initiating async scans, and filtering files."""

    def __init__(self, container: DependencyContainer, on_proceed_to_preview: Callable[[], None], parent=None):
        super().__init__(parent)
        self.container = container
        self.on_proceed_to_preview = on_proceed_to_preview
        self.scanned_files: List[FileItem] = []
        self._current_worker: Optional[ScanWorker] = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 24)

        # 1. Folder Selection Card
        sel_frame = QFrame()
        sel_frame.setProperty("class", "Card")
        sel_layout = QVBoxLayout(sel_frame)

        top_sel_layout = QHBoxLayout()
        folder_label = QLabel("Folder to Organize:")
        folder_label.setStyleSheet("font-weight: 600; color: #E2E8F0;")
        top_sel_layout.addWidget(folder_label)

        default_folder = self.container.config_mgr.get("default_source_folder", str(Path.home() / "Downloads"))
        self.folder_input = QLineEdit(default_folder)
        top_sel_layout.addWidget(self.folder_input)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._on_browse_folder)
        top_sel_layout.addWidget(browse_btn)

        self.recursive_chk = QCheckBox("Scan subfolders recursively")
        self.recursive_chk.setChecked(self.container.config_mgr.get("recursive_scan_default", False))
        top_sel_layout.addWidget(self.recursive_chk)

        self.scan_btn = QPushButton("Scan Folder")
        self.scan_btn.setProperty("class", "PrimaryButton")
        self.scan_btn.clicked.connect(self._start_scan)
        top_sel_layout.addWidget(self.scan_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setProperty("class", "DangerButton")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel_scan)
        top_sel_layout.addWidget(self.cancel_btn)

        sel_layout.addLayout(top_sel_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 0)  # indeterminate during scan
        sel_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Ready to scan.")
        self.status_label.setStyleSheet("color: #94A3B8; font-size: 12px;")
        sel_layout.addWidget(self.status_label)

        layout.addWidget(sel_frame)

        # 2. Filters & Search Bar
        filter_layout = QHBoxLayout()
        search_label = QLabel("Search Name:")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter files by name...")
        self.search_input.textChanged.connect(self._apply_table_filters)
        filter_layout.addWidget(search_label)
        filter_layout.addWidget(self.search_input)

        cat_label = QLabel("Category:")
        self.cat_filter_combo = QComboBox()
        self.cat_filter_combo.addItem("All Categories", "ALL")
        for cat in FileCategory:
            self.cat_filter_combo.addItem(cat.value.capitalize(), cat.value)
        self.cat_filter_combo.currentIndexChanged.connect(self._apply_table_filters)
        filter_layout.addWidget(cat_label)
        filter_layout.addWidget(self.cat_filter_combo)

        # Quick preset buttons
        filter_layout.addSpacing(10)
        preset_label = QLabel("Presets:")
        preset_label.setStyleSheet("color: #94A3B8;")
        filter_layout.addWidget(preset_label)

        presets = [
            ("📜 Satbara", "preset_satbara"),
            ("🌾 Farmer 27_", "preset_farmer"),
            ("💬 WhatsApp", "preset_whatsapp"),
            ("PDFs", "document"),
            ("Images", "image"),
            ("Archives", "archive"),
        ]
        for p_name, p_target in presets:
            btn = QPushButton(p_name)
            btn.setStyleSheet("padding: 3px 8px; font-size: 11px;")
            btn.clicked.connect(lambda ch, t=p_target: self._handle_preset_click(t))
            filter_layout.addWidget(btn)

        all_btn = QPushButton("Reset Filters")
        all_btn.setStyleSheet("padding: 3px 8px; font-size: 11px; background-color: #475569;")
        all_btn.clicked.connect(self._reset_filters)
        filter_layout.addWidget(all_btn)
        filter_layout.addStretch()

        layout.addLayout(filter_layout)

        # 3. File Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Filename", "Ext", "Category", "Size", "Date Modified", "Path"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSortingEnabled(True)
        layout.addWidget(self.table)

        # 4. Summary & Navigation Footer
        footer_layout = QHBoxLayout()
        self.summary_label = QLabel("0 files loaded")
        self.summary_label.setStyleSheet("color: #94A3B8; font-weight: 500;")
        footer_layout.addWidget(self.summary_label)
        footer_layout.addStretch()

        self.proceed_btn = QPushButton("Review Rules & Preview Organization →")
        self.proceed_btn.setProperty("class", "PrimaryButton")
        self.proceed_btn.setMinimumHeight(38)
        self.proceed_btn.setEnabled(False)
        self.proceed_btn.clicked.connect(self.on_proceed_to_preview)
        footer_layout.addWidget(self.proceed_btn)

        layout.addLayout(footer_layout)

    def _on_browse_folder(self) -> None:
        curr = self.folder_input.text()
        chosen = QFileDialog.getExistingDirectory(self, "Select Folder to Organize", curr)
        if chosen:
            self.folder_input.setText(chosen)

    def _handle_preset_click(self, target: str) -> None:
        if target == "preset_satbara":
            self.cat_filter_combo.setCurrentIndex(0)
            self.search_input.setText("satbara")
        elif target == "preset_farmer":
            self.cat_filter_combo.setCurrentIndex(0)
            self.search_input.setText("27_")
        elif target == "preset_whatsapp":
            self.cat_filter_combo.setCurrentIndex(0)
            self.search_input.setText("whatsapp")
        else:
            self.search_input.clear()
            self._set_category_preset(target)

    def _set_category_preset(self, cat_val: str) -> None:
        idx = self.cat_filter_combo.findData(cat_val)
        if idx >= 0:
            self.cat_filter_combo.setCurrentIndex(idx)

    def _reset_filters(self) -> None:
        self.search_input.clear()
        self.cat_filter_combo.setCurrentIndex(0)

    def _start_scan(self) -> None:
        path_str = self.folder_input.text().strip()
        folder_path = Path(path_str)
        if not folder_path.exists() or not folder_path.is_dir():
            QMessageBox.warning(self, "Invalid Directory", f"The folder does not exist:\n{path_str}")
            return

        self.scan_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.status_label.setText(f"Scanning {folder_path.name}...")

        worker = ScanWorker(
            workflow=self.container.scan_workflow,
            folder_path=folder_path,
            recursive=self.recursive_chk.isChecked(),
        )
        self._current_worker = worker
        worker.signals.progress.connect(self._on_scan_progress)
        worker.signals.finished.connect(self._on_scan_finished)
        worker.signals.error.connect(self._on_scan_error)

        QThreadPool.globalInstance().start(worker)

    def _cancel_scan(self) -> None:
        if self._current_worker:
            self._current_worker.cancel()
            self.status_label.setText("Cancelling scan...")

    def _on_scan_progress(self, count: int, total: int, filename: str, msg: str) -> None:
        self.status_label.setText(f"Found {count} files... {filename}")

    def _on_scan_finished(self, summary) -> None:
        self.scan_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        self._current_worker = None

        self.scanned_files = summary.items
        self.status_label.setText(
            f"Scan finished: {len(self.scanned_files)} files discovered in {summary.duration_sec:.2f}s"
        )
        self.proceed_btn.setEnabled(len(self.scanned_files) > 0)
        self._populate_table()

    def _on_scan_error(self, err_msg: str) -> None:
        self.scan_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        self._current_worker = None
        self.status_label.setText(f"Scan error: {err_msg}")
        QMessageBox.critical(self, "Scan Error", f"An error occurred while scanning:\n{err_msg}")

    def _format_size(self, size_bytes: int) -> str:
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"

    def _populate_table(self) -> None:
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self.scanned_files))

        for row, item in enumerate(self.scanned_files):
            self.table.setItem(row, 0, QTableWidgetItem(item.name))
            self.table.setItem(row, 1, QTableWidgetItem(item.extension))
            self.table.setItem(row, 2, QTableWidgetItem(item.category.value))
            self.table.setItem(row, 3, QTableWidgetItem(self._format_size(item.size_bytes)))
            self.table.setItem(row, 4, QTableWidgetItem(item.modified_at.strftime("%Y-%m-%d %H:%M")))
            self.table.setItem(row, 5, QTableWidgetItem(str(item.path)))

        self.table.setSortingEnabled(True)
        self._apply_table_filters()

    def _apply_table_filters(self) -> None:
        query = self.search_input.text().strip().lower()
        selected_cat = self.cat_filter_combo.currentData()

        visible_count = 0
        total_visible_bytes = 0

        for row in range(self.table.rowCount()):
            name_item = self.table.item(row, 0)
            cat_item = self.table.item(row, 2)
            if not name_item or not cat_item:
                continue

            name_match = (query in name_item.text().lower()) if query else True
            cat_match = (selected_cat == "ALL" or cat_item.text().lower() == selected_cat.lower())

            match = name_match and cat_match
            self.table.setRowHidden(row, not match)
            if match:
                visible_count += 1

        self.summary_label.setText(
            f"Showing {visible_count} of {len(self.scanned_files)} files"
        )
