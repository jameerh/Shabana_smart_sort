"""Modern Dark Theme stylesheet and styling tokens for PySide6."""

THEME_STYLESHEET = """
QMainWindow {
    background-color: #0F172A;
    color: #F8FAFC;
}

QWidget {
    font-family: "Segoe UI", -apple-system, sans-serif;
    font-size: 13px;
    color: #F8FAFC;
    background-color: transparent;
}

/* Sidebar navigation */
QFrame#Sidebar {
    background-color: #1E293B;
    border-right: 1px solid #334155;
}

QLabel#AppTitle {
    font-size: 17px;
    font-weight: 700;
    color: #60A5FA;
    padding: 6px 0px;
}

QLabel#AppSubtitle {
    font-size: 11px;
    color: #94A3B8;
}

QPushButton.NavButton {
    background-color: transparent;
    border: none;
    border-radius: 8px;
    padding: 10px 14px;
    text-align: left;
    font-size: 13px;
    font-weight: 500;
    color: #94A3B8;
}

QPushButton.NavButton:hover {
    background-color: #334155;
    color: #F8FAFC;
}

QPushButton.NavButton:checked {
    background-color: #2563EB;
    color: #FFFFFF;
    font-weight: 600;
}

/* Card panels */
QFrame.Card {
    background-color: #1E293B;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 12px;
}

QLabel.CardTitle {
    font-size: 14px;
    font-weight: 600;
    color: #E2E8F0;
}

QLabel.StatValue {
    font-size: 26px;
    font-weight: 700;
    color: #60A5FA;
}

QLabel.StatLabel {
    font-size: 12px;
    color: #94A3B8;
}

/* Standard Buttons */
QPushButton {
    background-color: #334155;
    color: #F8FAFC;
    border: 1px solid #475569;
    border-radius: 6px;
    padding: 7px 14px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #475569;
}

QPushButton:pressed {
    background-color: #1E293B;
}

QPushButton:disabled {
    background-color: #1E293B;
    color: #64748B;
    border-color: #334155;
}

QPushButton.PrimaryButton {
    background-color: #2563EB;
    border: 1px solid #3B82F6;
    color: #FFFFFF;
    font-weight: 600;
}

QPushButton.PrimaryButton:hover {
    background-color: #1D4ED8;
}

QPushButton.SuccessButton {
    background-color: #059669;
    border: 1px solid #10B981;
    color: #FFFFFF;
    font-weight: 600;
}

QPushButton.SuccessButton:hover {
    background-color: #047857;
}

QPushButton.DangerButton {
    background-color: #DC2626;
    border: 1px solid #EF4444;
    color: #FFFFFF;
}

QPushButton.DangerButton:hover {
    background-color: #B91C1C;
}

/* Input Fields */
QLineEdit, QComboBox, QSpinBox, QDateEdit {
    background-color: #0F172A;
    border: 1px solid #475569;
    border-radius: 6px;
    padding: 6px 10px;
    color: #F8FAFC;
    selection-background-color: #2563EB;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDateEdit:focus {
    border: 1px solid #3B82F6;
}

QComboBox::drop-down {
    border: none;
    padding-right: 8px;
}

QComboBox QAbstractItemView {
    background-color: #1E293B;
    color: #F8FAFC;
    border: 1px solid #475569;
    selection-background-color: #2563EB;
}

/* Tables */
QTableWidget, QTableView {
    background-color: #0F172A;
    border: 1px solid #334155;
    border-radius: 8px;
    gridline-color: #1E293B;
    color: #F8FAFC;
    selection-background-color: #1E3A8A;
    selection-color: #FFFFFF;
}

QTableWidget::item, QTableView::item {
    padding: 6px 8px;
    border-bottom: 1px solid #1E293B;
}

QHeaderView::section {
    background-color: #1E293B;
    color: #94A3B8;
    font-weight: 600;
    font-size: 12px;
    padding: 8px;
    border: none;
    border-bottom: 1px solid #334155;
    border-right: 1px solid #334155;
}

/* Progress bar */
QProgressBar {
    background-color: #0F172A;
    border: 1px solid #334155;
    border-radius: 6px;
    text-align: center;
    color: #F8FAFC;
    font-weight: 600;
}

QProgressBar::chunk {
    background-color: #2563EB;
    border-radius: 5px;
}

/* Scrollbars */
QScrollBar:vertical {
    background-color: #0F172A;
    width: 10px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background-color: #334155;
    border-radius: 5px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background-color: #475569;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background-color: #0F172A;
    height: 10px;
    margin: 0px;
}

QScrollBar::handle:horizontal {
    background-color: #334155;
    border-radius: 5px;
    min-width: 20px;
}

/* CheckBox */
QCheckBox {
    spacing: 8px;
    color: #E2E8F0;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid #475569;
    background-color: #0F172A;
}

QCheckBox::indicator:checked {
    background-color: #2563EB;
    border-color: #3B82F6;
}
"""
