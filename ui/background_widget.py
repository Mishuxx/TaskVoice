"""
ui/background_widget.py
========================
Custom QWidget container that renders the dark background (#0D1015)
with a subtle 22px dot grid pattern (#1B2130).
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QColor, QPen
from PyQt6.QtWidgets import QWidget

from ui.tokens import BG_DARK, BG_DOTS


class DottedBackgroundWidget(QWidget):
    """
    Renders background #0D1015 with subtle dot pattern (#1B2130, every 22px).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(BG_DARK))

        pen = QPen(QColor(BG_DOTS))
        pen.setWidth(2)
        painter.setPen(pen)

        step = 22
        w = self.width()
        h = self.height()

        for x in range(step // 2, w, step):
            for y in range(step // 2, h, step):
                painter.drawPoint(x, y)
