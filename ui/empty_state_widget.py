"""
ui/empty_state_widget.py
========================
Empty state widget with a custom QPainter pixel-art trophy and inviting message.
"""

from __future__ import annotations

from typing import Optional
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel

from ui.tokens import (
    ACCENT_GOLD, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    FONT_FAMILY,
)
from core.i18n import tr


class PixelTrophyWidget(QWidget):
    """Draws a crisp pixel-art golden trophy."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedSize(64, 64)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        # Scale pixel size
        s = 3
        ox = (self.width() - 16 * s) // 2
        oy = (self.height() - 16 * s) // 2

        # Color palette
        c_gold_light = QColor("#FDE68A")
        c_gold_main  = QColor("#F5B544")
        c_gold_dark  = QColor("#D97706")
        c_base_dark  = QColor("#1E2430")
        c_base_light = QColor("#334155")
        c_glow       = QColor(245, 181, 68, 50)

        # Subtle glow
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(c_glow)
        painter.drawEllipse(self.rect().adjusted(8, 8, -8, -8))

        def p(x, y, color):
            painter.fillRect(ox + x * s, oy + y * s, s, s, color)

        # Trophy Cup
        # Lip
        for x in range(4, 12):
            p(x, 2, c_gold_light if x in (5, 6) else c_gold_main)

        # Cup body
        for y in range(3, 7):
            for x in range(4, 12):
                col = c_gold_light if x in (5, 6) else (c_gold_main if x < 10 else c_gold_dark)
                p(x, y, col)

        # Cup taper
        for x in range(5, 11):
            p(x, 7, c_gold_main if x < 9 else c_gold_dark)
        for x in range(6, 10):
            p(x, 8, c_gold_main)

        # Handles
        # Left handle
        p(3, 3, c_gold_main)
        p(2, 4, c_gold_main)
        p(2, 5, c_gold_main)
        p(3, 6, c_gold_main)
        # Right handle
        p(12, 3, c_gold_dark)
        p(13, 4, c_gold_dark)
        p(13, 5, c_gold_dark)
        p(12, 6, c_gold_dark)

        # Stem
        for y in range(9, 12):
            p(7, y, c_gold_light)
            p(8, y, c_gold_main)

        # Base plate
        for x in range(5, 11):
            p(x, 12, c_gold_dark)
        for x in range(4, 12):
            p(x, 13, c_base_light)
        for x in range(3, 13):
            p(x, 14, c_base_dark)


class EmptyStateWidget(QWidget):
    """Container with trophy and empty state text."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 48, 20, 48)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._trophy = PixelTrophyWidget()
        layout.addWidget(self._trophy, alignment=Qt.AlignmentFlag.AlignCenter)

        self._title = QLabel(tr("empty_title"))
        self._title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {TEXT_PRIMARY};")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._title)

        self._subtitle = QLabel(tr("empty_subtitle"))
        self._subtitle.setStyleSheet(f"font-size: 13px; color: {TEXT_MUTED};")
        self._subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._subtitle)

    def retranslate_ui(self) -> None:
        self._title.setText(tr("empty_title"))
        self._subtitle.setText(tr("empty_subtitle"))
