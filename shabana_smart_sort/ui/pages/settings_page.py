"""Application settings and user preferences configuration page."""
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QCheckBox, QComboBox, QFrame, QMessageBox
)
from PySide6.QtCore import Qt

from shabana_smart_sort.app.dependency_container import DependencyContainer
from shabana_smart_sort.domain.enums import CollisionPolicy, DateField


class SettingsPage(QWidget):
    """User preferences, default directories, and safety toggles."""

    def __init__(self, container: DependencyContainer, parent=None):
        super().__init__(parent)
        self.container = container
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # Header
        title_box = QVBoxLayout()
        title = QLabel("Settings & Preferences")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #F8FAFC;")
        sub = QLabel("Configure default paths, collision policies, and file safety parameters")
        sub.setStyleSheet("font-size: 13px; color: #94A3B8;")
        title_box.addWidget(title)
        title_box.addWidget(sub)
        layout.addLayout(title_box)

        # 1. Defaults Card
        card_defaults = QFrame()
        card_defaults.setProperty("class", "Card")
        l_defaults = QVBoxLayout(card_defaults)
        l_defaults.setSpacing(12)

        lbl_def = QLabel("Default Folders & Scope")
        lbl_def.setStyleSheet("font-size: 14px; font-weight: 600; color: #60A5FA;")
        l_defaults.addWidget(lbl_def)

        # Source
        src_row = QHBoxLayout()
        lbl_src = QLabel("Default Scan Folder:")
        lbl_src.setFixedWidth(160)
        self.src_edit = QLineEdit(self.container.config_mgr.get("default_source_folder", ""))
        btn_src = QPushButton("Browse...")
        btn_src.clicked.connect(self._browse_source)
        src_row.addWidget(lbl_src)
        src_row.addWidget(self.src_edit)
        src_row.addWidget(btn_src)
        l_defaults.addLayout(src_row)

        # Dest
        dst_row = QHBoxLayout()
        lbl_dst = QLabel("Default Organized Root:")
        lbl_dst.setFixedWidth(160)
        self.dst_edit = QLineEdit(self.container.config_mgr.get("default_organized_folder", ""))
        btn_dst = QPushButton("Browse...")
        btn_dst.clicked.connect(self._browse_dest)
        dst_row.addWidget(lbl_dst)
        dst_row.addWidget(self.dst_edit)
        dst_row.addWidget(btn_dst)
        l_defaults.addLayout(dst_row)

        # Recursive
        self.chk_recursive = QCheckBox("Scan subfolders recursively by default")
        self.chk_recursive.setChecked(self.container.config_mgr.get("recursive_scan_default", False))
        l_defaults.addWidget(self.chk_recursive)

        layout.addWidget(card_defaults)

        # 2. Safety & Collision Card
        card_safety = QFrame()
        card_safety.setProperty("class", "Card")
        l_safety = QVBoxLayout(card_safety)
        l_safety.setSpacing(12)

        lbl_safe = QLabel("Safety Policies & Verification")
        lbl_safe.setStyleSheet("font-size: 14px; font-weight: 600; color: #60A5FA;")
        l_safety.addWidget(lbl_safe)

        col_row = QHBoxLayout()
        lbl_col = QLabel("Default Collision Policy:")
        lbl_col.setFixedWidth(160)
        self.combo_collision = QComboBox()
        self.combo_collision.addItem("Auto-Rename with (1)", CollisionPolicy.RENAME_NEW.value)
        self.combo_collision.addItem("Skip Colliding Files", CollisionPolicy.SKIP.value)
        self.combo_collision.addItem("Overwrite Target", CollisionPolicy.OVERWRITE.value)
        cur_col = self.container.config_mgr.get("collision_policy", CollisionPolicy.RENAME_NEW.value)
        idx_col = self.combo_collision.findData(cur_col)
        if idx_col >= 0:
            self.combo_collision.setCurrentIndex(idx_col)
        col_row.addWidget(lbl_col)
        col_row.addWidget(self.combo_collision)
        col_row.addStretch()
        l_safety.addLayout(col_row)

        date_row = QHBoxLayout()
        lbl_date = QLabel("Default Date Field:")
        lbl_date.setFixedWidth(160)
        self.combo_date = QComboBox()
        self.combo_date.addItem("Last Modified Date", DateField.MODIFIED.value)
        self.combo_date.addItem("Creation Date", DateField.CREATED.value)
        self.combo_date.addItem("Last Accessed Date", DateField.ACCESSED.value)
        cur_date = self.container.config_mgr.get("date_filter_field", DateField.MODIFIED.value)
        idx_date = self.combo_date.findData(cur_date)
        if idx_date >= 0:
            self.combo_date.setCurrentIndex(idx_date)
        date_row.addWidget(lbl_date)
        date_row.addWidget(self.combo_date)
        date_row.addStretch()
        l_safety.addLayout(date_row)

        self.chk_sha = QCheckBox("Compute SHA-256 checksums for cross-volume verification (thorough)")
        self.chk_sha.setChecked(self.container.config_mgr.get("verify_sha256", False))
        l_safety.addWidget(self.chk_sha)

        self.chk_symlinks = QCheckBox("Follow directory symbolic links (default False for loop protection)")
        self.chk_symlinks.setChecked(self.container.config_mgr.get("follow_symlinks", False))
        l_safety.addWidget(self.chk_symlinks)

        layout.addWidget(card_safety)

        # 3. System info
        card_sys = QFrame()
        card_sys.setProperty("class", "Card")
        l_sys = QVBoxLayout(card_sys)

        lbl_sys = QLabel("Storage & Diagnostic Paths")
        lbl_sys.setStyleSheet("font-size: 14px; font-weight: 600; color: #60A5FA;")
        l_sys.addWidget(lbl_sys)

        lbl_db = QLabel(f"SQLite Database: {self.container.db_path}")
        lbl_db.setStyleSheet("color: #94A3B8; font-size: 11px;")
        l_sys.addWidget(lbl_db)

        lbl_cfg = QLabel(f"Configuration File: {self.container.config_path}")
        lbl_cfg.setStyleSheet("color: #94A3B8; font-size: 11px;")
        l_sys.addWidget(lbl_cfg)

        layout.addWidget(card_sys)

        # Bottom buttons
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save Preferences")
        save_btn.setProperty("class", "PrimaryButton")
        save_btn.clicked.connect(self._save_settings)
        btn_layout.addWidget(save_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        layout.addStretch()

    def _browse_source(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Default Scan Folder", self.src_edit.text())
        if path:
            self.src_edit.setText(path)

    def _browse_dest(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Default Destination Root", self.dst_edit.text())
        if path:
            self.dst_edit.setText(path)

    def _save_settings(self) -> None:
        self.container.config_mgr.set("default_source_folder", self.src_edit.text().strip())
        self.container.config_mgr.set("default_organized_folder", self.dst_edit.text().strip())
        self.container.config_mgr.set("recursive_scan_default", self.chk_recursive.isChecked())
        self.container.config_mgr.set("collision_policy", self.combo_collision.currentData())
        self.container.config_mgr.set("date_filter_field", self.combo_date.currentData())
        self.container.config_mgr.set("verify_sha256", self.chk_sha.isChecked())
        self.container.config_mgr.set("follow_symlinks", self.chk_symlinks.isChecked())

        QMessageBox.information(self, "Settings Saved", "Preferences have been updated successfully.")
