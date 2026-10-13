"""Reusable statistic card widget."""
from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel
from PySide6.QtCore import Qt


class StatCard(QFrame):
    """Metric card displaying big statistic number, title, and subtitle."""

    def __init__(self, title: str, initial_value: str = "0", subtitle: str = "", parent=None):
        super().__init__(parent)
        self.setProperty("class", "Card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        self.title_label = QLabel(title)
        self.title_label.setProperty("class", "StatLabel")

        self.value_label = QLabel(initial_value)
        self.value_label.setProperty("class", "StatValue")

        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setProperty("class", "StatLabel")

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.subtitle_label)

    def set_value(self, value: str, subtitle: str = "") -> None:
        self.value_label.setText(value)
        if subtitle:
            self.subtitle_label.setText(subtitle)
