"""
ui/quick_add_widget.py
======================
Quick capture input bar for adding tasks via keyboard or voice dictation.

Features:
- Large input: "Agregar tarea…"
- Mic button (dictar por voz) with animated/colored state
- Violet "Agregar" button (height >= 44px)
"""

from __future__ import annotations

from typing import Optional
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLineEdit, QPushButton,
)

from ui.tokens import (
    BG_SURFACE, BORDER_SUBTLE, ACCENT_VIOLET,
    TEXT_PRIMARY, TEXT_MUTED,
)


class QuickAddWidget(QWidget):
    """Bar for rapid task creation with text input and microphone button."""

    add_task_requested = pyqtSignal(str)
    voice_toggled = pyqtSignal(bool)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedHeight(54)
        self._is_listening = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # 1. Text input
        self._input = QLineEdit()
        self._input.setPlaceholderText("Agregar tarea…")
        self._input.setFixedHeight(46)
        self._input.setStyleSheet(
            f"""
            QLineEdit {{
                background-color: {BG_SURFACE};
                border: 1px solid {BORDER_SUBTLE};
                border-radius: 12px;
                padding: 0 16px;
                font-size: 14px;
                color: {TEXT_PRIMARY};
            }}
            QLineEdit:focus {{
                border: 1px solid {ACCENT_VIOLET};
                background-color: #191F2B;
            }}
            """
        )
        self._input.returnPressed.connect(self._on_add)
        layout.addWidget(self._input, stretch=1)

        # 2. Mic button
        self._mic_btn = QPushButton("🎙")
        self._mic_btn.setFixedSize(46, 46)
        self._mic_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mic_btn.setToolTip("Dictar por voz")
        self._update_mic_style()
        self._mic_btn.clicked.connect(self._on_mic_clicked)
        layout.addWidget(self._mic_btn)

        # 3. Add button (violet)
        self._add_btn = QPushButton("Agregar")
        self._add_btn.setFixedHeight(46)
        self._add_btn.setMinimumWidth(100)
        self._add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {ACCENT_VIOLET};
                color: #FFFFFF;
                border-radius: 12px;
                font-size: 14px;
                font-weight: 700;
                padding: 0 18px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: #6D28D9;
            }}
            QPushButton:pressed {{
                background-color: #5B21B6;
            }}
            """
        )
        self._add_btn.clicked.connect(self._on_add)
        layout.addWidget(self._add_btn)

    def _on_add(self) -> None:
        text = self._input.text().strip()
        if text:
            self.add_task_requested.emit(text)
            self._input.clear()

    def _on_mic_clicked(self) -> None:
        self._is_listening = not self._is_listening
        self._update_mic_style()
        self.voice_toggled.emit(self._is_listening)

    def set_listening(self, listening: bool) -> None:
        self._is_listening = listening
        self._update_mic_style()

    def _update_mic_style(self) -> None:
        if self._is_listening:
            self._mic_btn.setStyleSheet(
                """
                QPushButton {
                    background-color: #DC2626;
                    color: #FFFFFF;
                    border-radius: 12px;
                    font-size: 18px;
                    border: 1px solid #EF4444;
                }
                QPushButton:hover {
                    background-color: #B91C1C;
                }
                """
            )
            self._mic_btn.setToolTip("Escuchando... Haz clic para detener")
        else:
            self._mic_btn.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {BG_SURFACE};
                    color: {TEXT_PRIMARY};
                    border: 1px solid {BORDER_SUBTLE};
                    border-radius: 12px;
                    font-size: 18px;
                }}
                QPushButton:hover {{
                    border-color: #3B82F6;
                    background-color: #1A2230;
                }}
                """
            )
            self._mic_btn.setToolTip("Dictar por voz")
