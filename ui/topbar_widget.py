"""
ui/topbar_widget.py
===================
Minimalist top bar for Taskmaster.
Shows:
- View title ("Todas las tareas")
- Subtitle ("X activas · Y completadas hoy")
- Search input with Ctrl+K shortcut badge
- Theme toggle button
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame,
)

from ui.tokens import (
    BG_DARK, BG_SURFACE, BORDER_SUBTLE, TEXT_PRIMARY,
    TEXT_SECONDARY, TEXT_MUTED, ACCENT_VIOLET,
)
from core.i18n import tr


class TopBarWidget(QWidget):
    """
    Clean top bar header.
    """
    search_changed = pyqtSignal(str)
    theme_toggled = pyqtSignal()
    settings_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(72)
        self.setStyleSheet(f"background-color: transparent;")

        self._build_ui()
        self._setup_shortcut()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 14, 24, 10)
        layout.setSpacing(16)

        # ------------------------------------------------------------------
        # Left: Title and Subtitle
        # ------------------------------------------------------------------
        title_col = QVBoxLayout()
        title_col.setSpacing(2)

        self._title_lbl = QLabel("Todas las tareas")
        self._title_lbl.setStyleSheet(
            f"font-size: 22px; font-weight: 800; color: {TEXT_PRIMARY}; letter-spacing: -0.3px;"
        )
        title_col.addWidget(self._title_lbl)

        self._subtitle_lbl = QLabel("0 activas · 0 completadas hoy")
        self._subtitle_lbl.setStyleSheet(f"font-size: 12px; color: {TEXT_SECONDARY};")
        title_col.addWidget(self._subtitle_lbl)

        layout.addLayout(title_col)
        layout.addStretch()

        # ------------------------------------------------------------------
        # Right: Search Box with Ctrl+K Pill
        # ------------------------------------------------------------------
        self._search_frame = QFrame()
        self._search_frame.setFixedHeight(40)
        self._search_frame.setFixedWidth(280)
        self._search_frame.setStyleSheet(
            f"QFrame {{ background-color: {BG_SURFACE}; border: 1px solid {BORDER_SUBTLE}; border-radius: 10px; }}"
            f"QFrame:focus-within {{ border-color: {ACCENT_VIOLET}; }}"
        )
        search_layout = QHBoxLayout(self._search_frame)
        search_layout.setContentsMargins(12, 0, 10, 0)
        search_layout.setSpacing(8)

        search_icon = QLabel("🔍")
        search_icon.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 13px;")
        search_layout.addWidget(search_icon)

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText(tr("search_placeholder"))
        self._search_edit.setStyleSheet(
            f"QLineEdit {{ background: transparent; border: none; color: {TEXT_PRIMARY}; font-size: 13px; }}"
        )
        self._search_edit.textChanged.connect(self.search_changed.emit)
        search_layout.addWidget(self._search_edit, 1)

        # Ctrl K Pill
        ctrl_k_badge = QLabel("Ctrl K")
        ctrl_k_badge.setStyleSheet(
            f"background-color: {BORDER_SUBTLE}; color: {TEXT_SECONDARY}; border-radius: 4px; "
            f"padding: 2px 6px; font-size: 10px; font-family: 'JetBrains Mono', monospace; font-weight: 600;"
        )
        search_layout.addWidget(ctrl_k_badge)

        layout.addWidget(self._search_frame)

        # ------------------------------------------------------------------
        # Theme Toggle Button
        # ------------------------------------------------------------------
        self._theme_btn = QPushButton("☀")
        self._theme_btn.setFixedSize(40, 40)
        self._theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._theme_btn.setToolTip(tr("theme_tooltip"))
        self._theme_btn.setStyleSheet(
            f"QPushButton {{ background-color: {BG_SURFACE}; border: 1px solid {BORDER_SUBTLE}; "
            f"border-radius: 10px; font-size: 16px; color: {TEXT_SECONDARY}; }}"
            f"QPushButton:hover {{ border-color: {ACCENT_VIOLET}; color: {TEXT_PRIMARY}; }}"
        )
        self._theme_btn.clicked.connect(self.theme_toggled.emit)
        layout.addWidget(self._theme_btn)

        # ------------------------------------------------------------------
        # Settings Button (Gear)
        # ------------------------------------------------------------------
        self._settings_btn = QPushButton("⚙")
        self._settings_btn.setFixedSize(40, 40)
        self._settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._settings_btn.setToolTip(tr("settings_tooltip"))
        self._settings_btn.setStyleSheet(
            f"QPushButton {{ background-color: {BG_SURFACE}; border: 1px solid {BORDER_SUBTLE}; "
            f"border-radius: 10px; font-size: 17px; color: {TEXT_SECONDARY}; }}"
            f"QPushButton:hover {{ border-color: {ACCENT_VIOLET}; color: {TEXT_PRIMARY}; }}"
        )
        self._settings_btn.clicked.connect(self.settings_clicked.emit)
        layout.addWidget(self._settings_btn)

    def _setup_shortcut(self) -> None:
        shortcut = QShortcut(QKeySequence("Ctrl+K"), self)
        shortcut.activated.connect(self._focus_search)

    def focus_search(self) -> None:
        self._focus_search()

    def _focus_search(self) -> None:
        self._search_edit.setFocus()
        self._search_edit.selectAll()

    def set_title(self, title: str) -> None:
        self._title_lbl.setText(title)

    def set_subtitle(self, subtitle: str) -> None:
        self._subtitle_lbl.setText(subtitle)

    def retranslate_ui(self) -> None:
        self._search_edit.setPlaceholderText(tr("search_placeholder"))
        self._theme_btn.setToolTip(tr("theme_tooltip"))
        self._settings_btn.setToolTip(tr("settings_tooltip"))

    def set_stats(self, active_count: int, completed_today_count: int) -> None:
        self._subtitle_lbl.setText(tr("stats_subtitle", active=active_count, completed=completed_today_count))

    def get_search_text(self) -> str:
        return self._search_edit.text()

    def search_text(self) -> str:
        return self._search_edit.text()
