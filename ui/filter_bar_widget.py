"""
ui/filter_bar_widget.py
=======================
Filter bar with pill-shaped buttons (Todas / Hoy / Prioridad alta)
and a "Mostrar completadas" toggle on the right.
"""

from __future__ import annotations

from typing import Optional
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QCheckBox,
)

from ui.tokens import (
    BG_SURFACE, BORDER_SUBTLE, ACCENT_TURQUOISE,
    TEXT_PRIMARY, TEXT_SECONDARY,
)
from core.i18n import tr


class FilterBarWidget(QWidget):
    """Pill filters (Todas, Hoy, Prioridad alta) + Show Completed checkbox."""

    filter_changed = pyqtSignal(str)          # 'all' | 'today' | 'high'
    show_completed_toggled = pyqtSignal(bool)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedHeight(42)
        self._current_filter = "all"

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # 1. Pill buttons
        self._btn_all = QPushButton(tr("filter_all"))
        self._btn_today = QPushButton(tr("filter_today"))
        self._btn_high = QPushButton(tr("filter_high_prio"))

        self._pills = {
            "all": self._btn_all,
            "today": self._btn_today,
            "high": self._btn_high,
        }

        for key, btn in self._pills.items():
            btn.setFixedHeight(34)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, k=key: self._set_filter(k))
            layout.addWidget(btn)

        layout.addStretch()

        # 2. "Mostrar completadas" checkbox
        self._completed_cb = QCheckBox(tr("filter_show_completed"))
        self._completed_cb.setChecked(False)
        self._completed_cb.setCursor(Qt.CursorShape.PointingHandCursor)
        self._completed_cb.setStyleSheet(
            f"""
            QCheckBox {{
                color: {TEXT_SECONDARY};
                font-size: 13px;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 1px solid {BORDER_SUBTLE};
                background: {BG_SURFACE};
            }}
            QCheckBox::indicator:hover {{
                border-color: {ACCENT_TURQUOISE};
            }}
            QCheckBox::indicator:checked {{
                background: {ACCENT_TURQUOISE};
                border-color: {ACCENT_TURQUOISE};
                image: none;
            }}
            """
        )
        self._completed_cb.toggled.connect(self.show_completed_toggled.emit)
        layout.addWidget(self._completed_cb)

        self._update_styles()

    def _set_filter(self, key: str) -> None:
        if self._current_filter != key:
            self._current_filter = key
            self._update_styles()
            self.filter_changed.emit(key)

    def current_filter(self) -> str:
        return self._current_filter

    def is_showing_completed(self) -> bool:
        return self._completed_cb.isChecked()

    def retranslate_ui(self) -> None:
        self._btn_all.setText(tr("filter_all"))
        self._btn_today.setText(tr("filter_today"))
        self._btn_high.setText(tr("filter_high_prio"))
        self._completed_cb.setText(tr("filter_show_completed"))

    def _update_styles(self) -> None:
        for key, btn in self._pills.items():
            is_active = (key == self._current_filter)
            if is_active:
                btn.setStyleSheet(
                    f"""
                    QPushButton {{
                        background-color: #1E2430;
                        border: 1px solid #3B4861;
                        border-radius: 17px;
                        color: {TEXT_PRIMARY};
                        font-weight: 700;
                        font-size: 13px;
                        padding: 0 16px;
                    }}
                    """
                )
            else:
                btn.setStyleSheet(
                    f"""
                    QPushButton {{
                        background-color: transparent;
                        border: 1px solid transparent;
                        border-radius: 17px;
                        color: {TEXT_SECONDARY};
                        font-weight: 500;
                        font-size: 13px;
                        padding: 0 16px;
                    }}
                    QPushButton:hover {{
                        background-color: #161B24;
                        color: {TEXT_PRIMARY};
                    }}
                    """
                )
