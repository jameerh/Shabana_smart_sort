"""Main desktop window with sleek sidebar navigation and stacked page architecture."""
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QFrame,
    QLabel, QPushButton, QStackedWidget, QButtonGroup, QStatusBar
)
from PySide6.QtCore import Qt

from shabana_smart_sort.app.dependency_container import DependencyContainer
from shabana_smart_sort.ui.pages.dashboard_page import DashboardPage
from shabana_smart_sort.ui.pages.scan_page import ScanPage
from shabana_smart_sort.ui.pages.rules_page import RulesPage
from shabana_smart_sort.ui.pages.preview_page import PreviewPage
from shabana_smart_sort.ui.pages.history_page import HistoryPage
from shabana_smart_sort.ui.pages.settings_page import SettingsPage
from shabana_smart_sort.ui.theme import THEME_STYLESHEET


class MainWindow(QMainWindow):
    """Primary application shell containing the sidebar and page switcher."""

    def __init__(self, container: DependencyContainer):
        super().__init__()
        self.container = container
        self.setWindowTitle("Shabana Smart Sort — Windows Folder Organizer")
        self.setMinimumSize(1100, 720)
        self.resize(1200, 780)

        # Apply modern dark theme
        self.setStyleSheet(THEME_STYLESHEET)

        self._init_ui()

    def _init_ui(self) -> None:
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        root_layout = QHBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Left Sidebar
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(240)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(16, 20, 16, 20)
        sidebar_layout.setSpacing(8)

        # Branding
        title_lbl = QLabel("Shabana Smart Sort")
        title_lbl.setObjectName("AppTitle")
        sub_lbl = QLabel("Safe Windows File Organizer")
        sub_lbl.setObjectName("AppSubtitle")
        sidebar_layout.addWidget(title_lbl)
        sidebar_layout.addWidget(sub_lbl)
        sidebar_layout.addSpacing(20)

        # Navigation Buttons
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)

        self.nav_buttons = []
        nav_items = [
            ("📊  Dashboard", 0),
            ("🔍  Scan & Filter", 1),
            ("⚡  Rule Manager", 2),
            ("👁  Preview & Organize", 3),
            ("📜  History & Undo", 4),
            ("⚙  Settings", 5),
        ]

        for text, index in nav_items:
            btn = QPushButton(text)
            btn.setProperty("class", "NavButton")
            btn.setCheckable(True)
            if index == 0:
                btn.setChecked(True)
            btn.clicked.connect(lambda checked, idx=index: self.switch_page(idx))
            self.nav_group.addButton(btn, index)
            self.nav_buttons.append(btn)
            sidebar_layout.addWidget(btn)

        sidebar_layout.addStretch()

        # Offline / Safe badge
        safety_badge = QLabel("🛡 Offline-First • Safe Move Engine")
        safety_badge.setStyleSheet("color: #64748B; font-size: 11px; padding: 4px;")
        sidebar_layout.addWidget(safety_badge)

        root_layout.addWidget(sidebar)

        # 2. Main Stacked Content Pages
        self.stack = QStackedWidget()

        # Instantiate pages
        self.page_dashboard = DashboardPage(self.container, on_navigate=self.switch_page)
        self.page_scan = ScanPage(self.container, on_proceed_to_preview=self._on_proceed_to_preview)
        self.page_rules = RulesPage(self.container)
        self.page_preview = PreviewPage(self.container, on_complete=self._on_execution_complete)
        self.page_history = HistoryPage(self.container)
        self.page_settings = SettingsPage(self.container)

        self.stack.addWidget(self.page_dashboard)   # 0
        self.stack.addWidget(self.page_scan)        # 1
        self.stack.addWidget(self.page_rules)       # 2
        self.stack.addWidget(self.page_preview)     # 3
        self.stack.addWidget(self.page_history)     # 4
        self.stack.addWidget(self.page_settings)    # 5

        root_layout.addWidget(self.stack)

        # 3. Status Bar
        status_bar = QStatusBar()
        status_bar.setStyleSheet("background-color: #0F172A; color: #64748B; border-top: 1px solid #1E293B;")
        status_bar.showMessage("Shabana Smart Sort v1.0.0 — Ready")
        self.setStatusBar(status_bar)

    def switch_page(self, index: int) -> None:
        """Switches the visible page in the stacked widget."""
        self.stack.setCurrentIndex(index)
        if 0 <= index < len(self.nav_buttons):
            self.nav_buttons[index].setChecked(True)

        # Refresh page data if applicable
        if index == 0:
            self.page_dashboard.refresh_data()
        elif index == 2:
            self.page_rules.reload_rules()
        elif index == 4:
            self.page_history.reload_history()

    def _on_proceed_to_preview(self) -> None:
        """Triggered from Scan page when user clicks 'Proceed to Preview'."""
        self.page_preview.set_files_to_preview(self.page_scan.scanned_files)
        self.switch_page(3)  # Preview page

    def _on_execution_complete(self) -> None:
        """Triggered when file organization successfully completes."""
        self.page_dashboard.refresh_data()
        self.page_history.reload_history()
