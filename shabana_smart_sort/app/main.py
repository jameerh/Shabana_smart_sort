"""Main application entry point."""
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from shabana_smart_sort.app.bootstrap import bootstrap_application
from shabana_smart_sort.ui.main_window import MainWindow


def main() -> int:
    """Bootstraps backend services and launches the PySide6 desktop GUI."""
    # Enable high-DPI scaling on Windows
    if hasattr(Qt, "HighDpiScaleFactorRoundingPolicy"):
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )

    app = QApplication(sys.argv)
    app.setApplicationName("Shabana Smart Sort")
    app.setOrganizationName("ShabanaSmartSort")

    # Bootstrap container
    container = bootstrap_application()

    # Launch UI
    window = MainWindow(container)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
