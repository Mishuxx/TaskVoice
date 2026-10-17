"""
ui/main_window.py
=================
Main application window for TaskVoice.

Layout
------
┌─────────────────────────────────────────────────────┐
│  Toolbar: [+Nueva] [🎙 Voz] [Search…] [Filtro ▾]   │
├──────────────┬──────────────────────────────────────┤
│  Sidebar     │  Task list (scrollable)               │
│  (categories)│                                       │
├──────────────┴──────────────────────────────────────┤
│  Status bar: total | completed today | voice status  │
└─────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional, Dict, Any, List

from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve,
    pyqtSlot, QSize, QPoint,
)
from PyQt6.QtGui import (
    QIcon, QAction, QKeySequence, QFont, QColor, QPalette,
)
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QListWidget, QListWidgetItem, QScrollArea, QToolBar,
    QPushButton, QLineEdit, QComboBox, QLabel, QStatusBar,
    QSplitter, QFrame, QDialog, QFormLayout, QTextEdit,
    QDateTimeEdit, QSpinBox, QCheckBox, QDialogButtonBox,
    QMessageBox, QSystemTrayIcon, QMenu, QApplication,
    QSizePolicy, QStackedWidget, QProgressBar, QTimeEdit,
)
from PyQt6.QtCore import QDateTime, QTime

from core.tasks import DatabaseManager
from core.recurrence import (
    parse_recurrence_days,
    serialize_recurrence_days,
    parse_recurrence_times,
    serialize_recurrence_times,
    extract_recurrence,
    calculate_next_occurrence,
)
from core.voice import VoiceManager, extract_task_number
from core.notifier import NotificationManager
from ui.task_widget import TaskWidget
from ui.settings_dialog import SettingsDialog
from ui.dashboard_widget import DashboardWidget
from ui.gamification_widget import GamificationWidget, LevelUpDialog
from ui.mission_banner import MissionBannerWidget
from ui.quick_add_widget import QuickAddWidget
from ui.filter_bar_widget import FilterBarWidget
from ui.empty_state_widget import EmptyStateWidget
from ui.tokens import (
    BG_DARK, BG_SIDEBAR, BG_SURFACE, BORDER_SUBTLE,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    ACCENT_VIOLET, ACCENT_TURQUOISE, ACCENT_GOLD,
    COLOR_SALUD, TASKMASTER_QSS, FONT_FAMILY, FONT_MONO,
)
from ui.sidebar_widget import SidebarWidget
from ui.topbar_widget import TopBarWidget
from ui.background_widget import DottedBackgroundWidget
from core.i18n import tr, set_language, get_language

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Settings persistence
# ---------------------------------------------------------------------------
SETTINGS_PATH = Path.home() / ".taskvoice" / "settings.json"

DEFAULT_SETTINGS: Dict[str, Any] = {
    "theme": "dark",
    "language": "es",
    # Local Notifications
    "notifications_enabled": True,
    "reminder_minutes": 30,
    "notify_on_due_time": True,
    "notify_overdue": False,
    "notification_duration": 10,
    "daily_summary_enabled": True,
    "daily_summary_hour": 9,
    "daily_summary_minute": 0,
    "evening_summary_enabled": True,
    "evening_summary_hour": 21,
    "evening_summary_minute": 0,
    "desktop_notify_level_up": True,
    "desktop_notify_quests": True,

    # Voice
    "voice_enabled": True,
    "voice_engine": "google",
    "voice_language": "auto",
    "vosk_model_path": "",
    "push_to_talk": False,
    "global_hotkey_enabled": True,

    # Telegram Bot
    "telegram_enabled": False,
    "telegram_bot_token": "",
    "telegram_chat_id": "",
    "tg_notify_tasks": True,
    "tg_notify_due_now": True,
    "tg_notify_morning_summary": True,
    "tg_notify_evening_summary": True,
    "tg_notify_level_up": True,
    "tg_notify_quests": True,
    "tg_notify_high_prio": True,
    "tg_silent_notifications": False,
}

# ---------------------------------------------------------------------------
# Dark (StarCraft / PoE Cyber-Gothic) / Light QSS themes
# ---------------------------------------------------------------------------
DARK_QSS = """
QMainWindow, QWidget {
    background-color: #090c13;
    color: #e2e8f0;
    font-family: 'Segoe UI', Arial, sans-serif;
}
QToolBar {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #121724, stop:1 #0c0f18);
    border-bottom: 1px solid #1f2d42;
    padding: 6px 10px;
    spacing: 8px;
}
QToolBar QToolButton {
    background: #141b29;
    color: #cbd5e1;
    border: 1px solid #1f2d42;
    border-radius: 6px;
    padding: 5px 12px;
}
QToolBar QToolButton:hover {
    background: #1e283d;
    border-color: #00f0ff;
    color: #00f0ff;
}
QLineEdit {
    background: #0f1420;
    color: #f1f5f9;
    border: 1px solid #1f2d42;
    border-radius: 6px;
    padding: 5px 10px;
}
QLineEdit:focus {
    border: 1px solid #00f0ff;
    background: #131929;
}
QComboBox {
    background: #0f1420;
    color: #f1f5f9;
    border: 1px solid #1f2d42;
    border-radius: 6px;
    padding: 4px 8px;
}
QComboBox:focus { border: 1px solid #00f0ff; }
QComboBox::drop-down { border: none; }
QComboBox QAbstractItemView {
    background: #0f1420;
    color: #f1f5f9;
    selection-background-color: #0284c7;
    border: 1px solid #1f2d42;
}
QScrollBar:vertical {
    background: #090c13;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #1f2d42;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: #00b4d8;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QStatusBar {
    background: #090c13;
    color: #64748b;
    font-size: 12px;
    border-top: 1px solid #1f2d42;
}
QSplitter::handle { background: #1f2d42; width: 1px; }
QLabel { color: #e2e8f0; }
QGroupBox {
    color: #00f0ff;
    font-weight: 700;
    border: 1px solid #1f2d42;
    border-radius: 6px;
    margin-top: 10px;
}
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
QSpinBox, QDateTimeEdit {
    background: #0f1420;
    color: #f1f5f9;
    border: 1px solid #1f2d42;
    border-radius: 6px;
    padding: 4px 8px;
}
QCheckBox { color: #e2e8f0; }
QCheckBox::indicator {
    border: 1px solid #1f2d42;
    background: #0f1420;
    border-radius: 4px;
    width: 14px;
    height: 14px;
}
QCheckBox::indicator:checked {
    background: #00f0ff;
    border-color: #00f0ff;
}
QTextEdit {
    background: #0f1420;
    color: #f1f5f9;
    border: 1px solid #1f2d42;
    border-radius: 6px;
    padding: 6px;
}
QDialog { background: #0c1017; }
QTabWidget::pane { border: 1px solid #1f2d42; background: #0c1017; }
QTabBar::tab {
    background: #101624;
    color: #94a3b8;
    padding: 8px 18px;
}
QTabBar::tab:selected {
    background: #182236;
    color: #00f0ff;
    border-bottom: 2px solid #00f0ff;
    font-weight: 700;
}
QMessageBox { background: #0c1017; }
"""

LIGHT_QSS = """
QMainWindow, QWidget {
    background-color: #f8f8f2;
    color: #282a36;
    font-family: 'Segoe UI', Arial, sans-serif;
}
QToolBar {
    background: #e8e8e8;
    border-bottom: 1px solid #d0d0d0;
    padding: 4px;
    spacing: 6px;
}
QLineEdit {
    background: #ffffff;
    color: #282a36;
    border: 1px solid #d0d0d0;
    border-radius: 6px;
    padding: 5px 10px;
}
QLineEdit:focus { border: 1px solid #7c3aed; }
QComboBox {
    background: #ffffff;
    color: #282a36;
    border: 1px solid #d0d0d0;
    border-radius: 6px;
    padding: 4px 8px;
}
QScrollBar:vertical { background: #f0f0f0; width: 8px; border-radius: 4px; }
QScrollBar::handle:vertical { background: #c0c0c0; border-radius: 4px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QStatusBar { background: #e8e8e8; color: #6c6c6c; font-size: 12px; }
QSplitter::handle { background: #d0d0d0; width: 1px; }
QSpinBox, QDateTimeEdit { background: #ffffff; color: #282a36; border: 1px solid #d0d0d0; border-radius: 6px; padding: 4px 8px; }
QTextEdit { background: #ffffff; color: #282a36; border: 1px solid #d0d0d0; border-radius: 6px; padding: 6px; }
QDialog { background: #f8f8f2; }
"""


# ===========================================================================
# Task Edit Dialog
# ===========================================================================

class TaskEditDialog(QDialog):
    """Dialog for creating or editing a task (with subtasks)."""

    def __init__(
        self,
        db: DatabaseManager,
        task_id: Optional[int] = None,
        initial_title: str = "",
        initial_category_id: Optional[int] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._db = db
        self._task_id = task_id
        self._initial_title = initial_title
        self._initial_category_id = initial_category_id
        self._task: Optional[Dict[str, Any]] = None
        self._subtasks: List[Dict[str, Any]] = []
        self._new_subtask_edits: List[QLineEdit] = []

        if task_id:
            self._task = db.get_task(task_id)
            self._subtasks = db.get_subtasks(task_id)
            self.setWindowTitle("Editar Tarea")
        else:
            self.setWindowTitle("Nueva Tarea Compleja")

        self.setMinimumWidth(440)
        self._build_ui()
        self._load_data()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._title_edit = QLineEdit()
        self._title_edit.setPlaceholderText("Título de la tarea…")
        form.addRow("Título*:", self._title_edit)

        self._desc_edit = QTextEdit()
        self._desc_edit.setPlaceholderText("Descripción (opcional)…")
        self._desc_edit.setFixedHeight(80)
        form.addRow("Descripción:", self._desc_edit)

        self._cat_combo = QComboBox()
        self._cat_combo.addItem("Sin categoría", None)
        for cat in self._db.get_categories():
            self._cat_combo.addItem(cat["name"], cat["id"])
        form.addRow("Categoría:", self._cat_combo)

        self._priority_combo = QComboBox()
        self._priority_combo.addItems(["Baja (1)", "Media (2)", "Alta (3)"])
        self._priority_combo.setCurrentIndex(1)
        form.addRow("Prioridad:", self._priority_combo)

        self._due_edit = QDateTimeEdit()
        self._due_edit.setDisplayFormat("dd/MM/yyyy HH:mm")
        self._due_edit.setDateTime(QDateTime.currentDateTime())
        self._due_edit.setCalendarPopup(True)

        self._due_cb = QCheckBox("Definir fecha de vencimiento")
        self._due_cb.stateChanged.connect(lambda s: self._due_edit.setEnabled(bool(s)))
        self._due_edit.setEnabled(False)
        form.addRow(self._due_cb)
        form.addRow("Vencimiento:", self._due_edit)

        # Recurrence section
        self._rec_cb = QCheckBox("🔁 Tarea recurrente")
        self._rec_cb.setStyleSheet(f"color: {ACCENT_TURQUOISE}; font-size: 13px; font-weight: 600;")
        form.addRow(self._rec_cb)

        self._rec_container = QWidget()
        rec_layout = QVBoxLayout(self._rec_container)
        rec_layout.setContentsMargins(0, 4, 0, 8)
        rec_layout.setSpacing(8)

        # Recurrence type row
        rec_type_row = QHBoxLayout()
        rec_type_lbl = QLabel("Frecuencia:")
        rec_type_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        rec_type_row.addWidget(rec_type_lbl)

        self._rec_type_combo = QComboBox()
        self._rec_type_combo.addItem("Todos los días (Diario)", "daily")
        self._rec_type_combo.addItem("Lunes a Viernes (Días hábiles)", "weekdays")
        self._rec_type_combo.addItem("Días personalizados", "custom")
        rec_type_row.addWidget(self._rec_type_combo, stretch=1)
        rec_layout.addLayout(rec_type_row)

        # Days selector buttons
        self._rec_days_widget = QWidget()
        days_row = QHBoxLayout(self._rec_days_widget)
        days_row.setContentsMargins(0, 0, 0, 0)
        days_row.setSpacing(4)

        self._day_buttons: List[QPushButton] = []
        day_letters = ["L", "M", "X", "J", "V", "S", "D"]
        for idx, letter in enumerate(day_letters):
            btn = QPushButton(letter)
            btn.setCheckable(True)
            btn.setChecked(True)
            btn.setFixedSize(34, 32)
            btn.setFont(QFont(FONT_MONO, 11, QFont.Weight.Bold))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                f"""
                QPushButton {{
                    background: #161B24;
                    color: {TEXT_MUTED};
                    border: 1px solid {BORDER_SUBTLE};
                    border-radius: 6px;
                }}
                QPushButton:hover {{
                    border-color: {ACCENT_TURQUOISE};
                    color: {TEXT_PRIMARY};
                }}
                QPushButton:checked {{
                    background: {ACCENT_TURQUOISE};
                    color: #0D1015;
                    border: 1px solid #5EEAD4;
                    font-weight: bold;
                }}
                """
            )
            btn.toggled.connect(self._on_day_button_toggled)
            days_row.addWidget(btn)
            self._day_buttons.append(btn)

        rec_layout.addWidget(self._rec_days_widget)

        # Multi-instance time selector
        time_section = QFrame()
        time_section.setStyleSheet(
            f"""
            QFrame {{
                background-color: #11151C;
                border: 1px solid {BORDER_SUBTLE};
                border-radius: 8px;
            }}
            """
        )
        time_sec_layout = QVBoxLayout(time_section)
        time_sec_layout.setContentsMargins(10, 8, 10, 8)
        time_sec_layout.setSpacing(8)

        # Presets header
        inst_header = QHBoxLayout()
        inst_lbl = QLabel("Instancias al día:")
        inst_lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 12px; font-weight: 700; border: none; background: transparent;")
        inst_header.addWidget(inst_lbl)
        inst_header.addStretch()

        self._preset_1x = QPushButton("1x día")
        self._preset_1x.setCursor(Qt.CursorShape.PointingHandCursor)
        self._preset_1x.setToolTip("1 instancia diaria (09:00)")
        self._preset_1x.clicked.connect(lambda: self._set_preset_times(["09:00"]))
        inst_header.addWidget(self._preset_1x)

        self._preset_2x = QPushButton("2x día")
        self._preset_2x.setCursor(Qt.CursorShape.PointingHandCursor)
        self._preset_2x.setToolTip("2 instancias al día (09:00 y 18:00)")
        self._preset_2x.clicked.connect(lambda: self._set_preset_times(["09:00", "18:00"]))
        inst_header.addWidget(self._preset_2x)

        self._preset_3x = QPushButton("3x día")
        self._preset_3x.setCursor(Qt.CursorShape.PointingHandCursor)
        self._preset_3x.setToolTip("3 instancias al día (08:00, 14:00 y 20:00)")
        self._preset_3x.clicked.connect(lambda: self._set_preset_times(["08:00", "14:00", "20:00"]))
        inst_header.addWidget(self._preset_3x)

        time_sec_layout.addLayout(inst_header)

        # Active instances chips container
        self._chips_widget = QWidget()
        self._chips_widget.setStyleSheet("border: none; background: transparent;")
        self._chips_layout = QHBoxLayout(self._chips_widget)
        self._chips_layout.setContentsMargins(0, 2, 0, 2)
        self._chips_layout.setSpacing(6)
        time_sec_layout.addWidget(self._chips_widget)

        # Add custom time row
        add_time_row = QHBoxLayout()
        add_time_row.setSpacing(8)

        add_time_lbl = QLabel("Horario:")
        add_time_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; border: none; background: transparent;")
        add_time_row.addWidget(add_time_lbl)

        self._new_time_edit = QTimeEdit()
        self._new_time_edit.setDisplayFormat("HH:mm")
        self._new_time_edit.setTime(QTime(18, 0))
        self._new_time_edit.setFixedWidth(90)
        self._new_time_edit.setFixedHeight(30)
        self._new_time_edit.setStyleSheet(
            f"""
            QTimeEdit {{
                background-color: {BG_SURFACE};
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER_SUBTLE};
                border-radius: 6px;
                padding: 2px 6px;
                font-family: 'JetBrains Mono', monospace;
                font-size: 12px;
                font-weight: 600;
            }}
            QTimeEdit:focus {{
                border-color: {ACCENT_TURQUOISE};
            }}
            """
        )
        add_time_row.addWidget(self._new_time_edit)

        self._add_time_btn = QPushButton("➕ Añadir hora")
        self._add_time_btn.setFixedHeight(30)
        self._add_time_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add_time_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: #161B24;
                color: #5EEAD4;
                border: 1px solid rgba(45, 212, 191, 0.4);
                border-radius: 6px;
                padding: 0 12px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: rgba(45, 212, 191, 0.15);
                border-color: #2DD4BF;
            }}
            """
        )
        self._add_time_btn.clicked.connect(self._add_custom_time)
        add_time_row.addWidget(self._add_time_btn)
        add_time_row.addStretch()

        time_sec_layout.addLayout(add_time_row)

        # Informative note
        inst_note = QLabel("💡 Se creará 1 sola tarea: al completarla, avanza automáticamente a la siguiente instancia.")
        inst_note.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px; border: none; background: transparent;")
        time_sec_layout.addWidget(inst_note)

        rec_layout.addWidget(time_section)

        self._times_list: List[str] = ["09:00"]
        self._refresh_time_chips()

        self._rec_container.setVisible(False)
        self._rec_cb.toggled.connect(self._rec_container.setVisible)
        self._rec_type_combo.currentIndexChanged.connect(self._on_rec_type_changed)

        form.addRow(self._rec_container)

        # Dynamic category auto-deduction as the user types
        self._cat_user_modified = False
        self._cat_combo.activated.connect(lambda: setattr(self, "_cat_user_modified", True))
        self._title_edit.textChanged.connect(self._on_title_changed)

        layout.addLayout(form)

        # --- Subtasks ---
        sub_label = QLabel("Subtareas:")
        sub_label.setStyleSheet("font-weight: 600; margin-top: 6px;")
        layout.addWidget(sub_label)

        self._subtask_container = QVBoxLayout()
        layout.addLayout(self._subtask_container)

        add_sub_btn = QPushButton("➕ Añadir subtarea")
        add_sub_btn.setStyleSheet(
            "QPushButton { background: #313244; color: #cdd6f4; border-radius: 6px; padding: 4px 10px; }"
            "QPushButton:hover { background: #45475a; }"
        )
        add_sub_btn.clicked.connect(self._add_subtask_row)
        layout.addWidget(add_sub_btn)

        # --- Dialog buttons ---
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _on_rec_type_changed(self, index: int) -> None:
        rec_type = self._rec_type_combo.currentData()
        if rec_type == "daily":
            for btn in self._day_buttons:
                btn.blockSignals(True)
                btn.setChecked(True)
                btn.blockSignals(False)
        elif rec_type == "weekdays":
            for idx, btn in enumerate(self._day_buttons):
                btn.blockSignals(True)
                btn.setChecked(idx < 5)
                btn.blockSignals(False)

    def _on_day_button_toggled(self, checked: bool) -> None:
        active_days = [i for i, b in enumerate(self._day_buttons) if b.isChecked()]
        self._rec_type_combo.blockSignals(True)
        if len(active_days) == 7:
            self._rec_type_combo.setCurrentIndex(0)
        elif active_days == [0, 1, 2, 3, 4]:
            self._rec_type_combo.setCurrentIndex(1)
        else:
            self._rec_type_combo.setCurrentIndex(2)
        self._rec_type_combo.blockSignals(False)

    def _preset_btn_style(self, active: bool) -> str:
        if active:
            return (
                f"QPushButton {{ background-color: {ACCENT_TURQUOISE}; color: #0D1015; "
                f"border: 1px solid #5EEAD4; border-radius: 6px; padding: 3px 8px; font-weight: 700; font-size: 11px; }}"
            )
        else:
            return (
                f"QPushButton {{ background-color: #161B24; color: {TEXT_SECONDARY}; "
                f"border: 1px solid {BORDER_SUBTLE}; border-radius: 6px; padding: 3px 8px; font-weight: 500; font-size: 11px; }}"
                f"QPushButton:hover {{ border-color: {ACCENT_TURQUOISE}; color: {TEXT_PRIMARY}; }}"
            )

    def _set_preset_times(self, times: List[str]) -> None:
        self._times_list = list(times)
        self._refresh_time_chips()

    def _add_custom_time(self) -> None:
        new_time = self._new_time_edit.time().toString("HH:mm")
        if new_time not in self._times_list:
            self._times_list.append(new_time)
            self._times_list.sort()
            self._refresh_time_chips()

    def _remove_time(self, t_str: str) -> None:
        if len(self._times_list) > 1 and t_str in self._times_list:
            self._times_list.remove(t_str)
            self._refresh_time_chips()

    def _refresh_time_chips(self) -> None:
        while self._chips_layout.count() > 0:
            item = self._chips_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Update presets styling
        self._preset_1x.setStyleSheet(self._preset_btn_style(self._times_list == ["09:00"]))
        self._preset_2x.setStyleSheet(self._preset_btn_style(self._times_list == ["09:00", "18:00"]))
        self._preset_3x.setStyleSheet(self._preset_btn_style(self._times_list == ["08:00", "14:00", "20:00"]))

        for t_str in self._times_list:
            chip = QFrame()
            chip.setStyleSheet(
                f"""
                QFrame {{
                    background-color: rgba(45, 212, 191, 0.12);
                    border: 1px solid rgba(45, 212, 191, 0.35);
                    border-radius: 6px;
                }}
                """
            )
            c_lay = QHBoxLayout(chip)
            c_lay.setContentsMargins(8, 3, 6, 3)
            c_lay.setSpacing(6)

            lbl = QLabel(f"⏰ {t_str}")
            lbl.setFont(QFont(FONT_MONO, 12, QFont.Weight.Bold))
            lbl.setStyleSheet(f"color: {ACCENT_TURQUOISE}; border: none; background: transparent;")
            c_lay.addWidget(lbl)

            if len(self._times_list) > 1:
                del_btn = QPushButton("✕")
                del_btn.setFixedSize(18, 18)
                del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                del_btn.setToolTip("Eliminar horario")
                del_btn.setStyleSheet(
                    f"""
                    QPushButton {{
                        background: transparent;
                        color: {TEXT_MUTED};
                        border: none;
                        font-size: 11px;
                        font-weight: bold;
                    }}
                    QPushButton:hover {{
                        color: #EF4444;
                    }}
                    """
                )
                del_btn.clicked.connect(lambda _, t=t_str: self._remove_time(t))
                c_lay.addWidget(del_btn)

            self._chips_layout.addWidget(chip)

        self._chips_layout.addStretch()

    def _load_data(self) -> None:
        if self._task is None:
            if self._initial_category_id is not None:
                for i in range(self._cat_combo.count()):
                    if self._cat_combo.itemData(i) == self._initial_category_id:
                        self._cat_combo.setCurrentIndex(i)
                        break
            if self._initial_title:
                self._title_edit.setText(self._initial_title)
            return
        t = self._task
        self._title_edit.setText(t.get("title", ""))
        self._desc_edit.setPlainText(t.get("description", ""))

        cat_id = t.get("category_id")
        for i in range(self._cat_combo.count()):
            if self._cat_combo.itemData(i) == cat_id:
                self._cat_combo.setCurrentIndex(i)
                break

        self._priority_combo.setCurrentIndex(t.get("priority", 2) - 1)

        due = t.get("due_date")
        if due:
            self._due_cb.setChecked(True)
            self._due_edit.setEnabled(True)
            try:
                dt = QDateTime.fromString(due, "yyyy-MM-dd HH:mm:ss")
                if not dt.isValid():
                    dt = QDateTime.fromString(due[:16], "yyyy-MM-ddTHH:mm")
                if dt.isValid():
                    self._due_edit.setDateTime(dt)
            except Exception:
                pass

        # Recurrence
        is_rec = bool(t.get("is_recurring", 0))
        if is_rec:
            self._rec_cb.setChecked(True)
            self._rec_container.setVisible(True)

            r_type = t.get("recurrence_type") or "daily"
            idx = self._rec_type_combo.findData(r_type)
            if idx >= 0:
                self._rec_type_combo.setCurrentIndex(idx)

            r_days = parse_recurrence_days(t.get("recurrence_days"))
            for i, btn in enumerate(self._day_buttons):
                btn.blockSignals(True)
                btn.setChecked(i in r_days)
                btn.blockSignals(False)

            r_time = t.get("recurrence_time") or "09:00"
            self._times_list = parse_recurrence_times(r_time)
            self._refresh_time_chips()
        else:
            self._times_list = ["09:00"]
            self._refresh_time_chips()

        # Existing subtasks
        for st in self._subtasks:
            self._add_existing_subtask_row(st)

    def _add_existing_subtask_row(self, st: Dict[str, Any]) -> None:
        row = QHBoxLayout()
        cb = QCheckBox(st["title"])
        cb.setChecked(bool(st["completed"]))
        cb.setProperty("subtask_id", st["id"])
        row.addWidget(cb)
        self._subtask_container.addLayout(row)

    def _add_subtask_row(self) -> None:
        row = QHBoxLayout()
        edit = QLineEdit()
        edit.setPlaceholderText("Título de la subtarea…")
        row.addWidget(edit)
        self._new_subtask_edits.append(edit)
        self._subtask_container.addLayout(row)

    def _on_title_changed(self, text: str) -> None:
        if self._task_id is not None or self._cat_user_modified:
            return
        from core.categorizer import deduce_category_name
        cat_name = deduce_category_name(text)
        if cat_name:
            for i in range(self._cat_combo.count()):
                if self._cat_combo.itemText(i).lower() == cat_name.lower():
                    self._cat_combo.setCurrentIndex(i)
                    return
            if cat_name.lower() == "hogar":
                self._cat_combo.addItem("Hogar", None)
                self._cat_combo.setCurrentIndex(self._cat_combo.count() - 1)

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def _save(self) -> None:
        title = self._title_edit.text().strip()
        if not title:
            QMessageBox.warning(self, "Error", "El título no puede estar vacío.")
            return

        desc     = self._desc_edit.toPlainText().strip()
        cat_id   = self._cat_combo.currentData()
        priority = self._priority_combo.currentIndex() + 1
        due_date = None
        is_recurring = self._rec_cb.isChecked()
        recurrence_days = None
        recurrence_time = None
        recurrence_type = None

        if is_recurring:
            selected_days = [i for i, b in enumerate(self._day_buttons) if b.isChecked()]
            if not selected_days:
                selected_days = [0, 1, 2, 3, 4, 5, 6]
            recurrence_days = selected_days
            recurrence_time = self._times_list if self._times_list else ["09:00"]
            recurrence_type = self._rec_type_combo.currentData() or "daily"

        due_date = None
        if self._due_cb.isChecked():
            due_date = self._due_edit.dateTime().toString("yyyy-MM-dd HH:mm:ss")
        elif is_recurring:
            next_dt = calculate_next_occurrence(recurrence_days, recurrence_time)
            due_date = next_dt.isoformat(sep=" ", timespec="seconds")
        else:
            due_date = ""

        if self._task_id is None:
            # New task
            task_id = self._db.add_task(
                title=title,
                description=desc,
                category_id=cat_id,
                due_date=due_date,
                priority=priority,
                is_recurring=is_recurring,
                recurrence_days=recurrence_days,
                recurrence_time=recurrence_time,
                recurrence_type=recurrence_type,
            )
        else:
            task_id = self._task_id
            self._db.update_task(
                task_id=task_id,
                title=title,
                description=desc,
                category_id=cat_id,
                due_date=due_date,
                priority=priority,
                is_recurring=is_recurring,
                recurrence_days=recurrence_days,
                recurrence_time=recurrence_time,
                recurrence_type=recurrence_type,
            )
            # Update existing subtask completion
            for i in range(self._subtask_container.count()):
                layout_item = self._subtask_container.itemAt(i)
                if layout_item and layout_item.layout():
                    for j in range(layout_item.layout().count()):
                        widget = layout_item.layout().itemAt(j).widget()
                        if isinstance(widget, QCheckBox):
                            sub_id = widget.property("subtask_id")
                            if sub_id:
                                self._db.complete_subtask(sub_id, widget.isChecked())

        # Add new subtasks
        for edit in self._new_subtask_edits:
            text = edit.text().strip()
            if text:
                self._db.add_subtask(task_id, text)

        self.saved_task_id = task_id
        self.accept()


# ===========================================================================
# Category Add Dialog
# ===========================================================================

class CategoryAddDialog(QDialog):
    """Clean popup to add a category with name and color selection."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nueva Categoría")
        self.setFixedSize(360, 220)
        self.setStyleSheet(
            f"""
            QDialog {{
                background-color: {BG_SURFACE};
                color: {TEXT_PRIMARY};
            }}
            QLineEdit {{
                background-color: #0F1420;
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER_SUBTLE};
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border-color: {ACCENT_VIOLET};
            }}
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title_lbl = QLabel("Crear Nueva Categoría")
        title_lbl.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {TEXT_PRIMARY};")
        layout.addWidget(title_lbl)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("Nombre de la categoría…")
        layout.addWidget(self._name_edit)

        color_lbl = QLabel("Color distintivo:")
        color_lbl.setStyleSheet(f"font-size: 12px; color: {TEXT_SECONDARY};")
        layout.addWidget(color_lbl)

        colors = ["#60A5FA", "#C084FC", "#34D399", "#F59E0B", "#EC4899", "#14B8A6", "#F43F5E", "#8B5CF6"]
        self._selected_color = colors[0]

        palette_layout = QHBoxLayout()
        palette_layout.setSpacing(8)
        self._color_btns = []

        for c in colors:
            btn = QPushButton()
            btn.setFixedSize(26, 26)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                f"background-color: {c}; border-radius: 13px; border: 2px solid transparent;"
            )
            btn.clicked.connect(lambda checked=False, col=c, b=btn: self._select_color(col, b))
            palette_layout.addWidget(btn)
            self._color_btns.append((btn, c))

        self._select_color(colors[0], self._color_btns[0][0])
        layout.addLayout(palette_layout)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _select_color(self, color: str, active_btn: QPushButton) -> None:
        self._selected_color = color
        for btn, c in self._color_btns:
            if btn is active_btn:
                btn.setStyleSheet(f"background-color: {c}; border-radius: 13px; border: 2px solid #FFFFFF;")
            else:
                btn.setStyleSheet(f"background-color: {c}; border-radius: 13px; border: 2px solid transparent;")

    def get_data(self) -> tuple[str, str]:
        return self._name_edit.text().strip(), self._selected_color


# ===========================================================================
# MainWindow
# ===========================================================================

class MainWindow(QMainWindow):
    """Primary application window for Taskmaster."""

    def __init__(
        self,
        db: DatabaseManager,
        notifier: NotificationManager,
        settings: Dict[str, Any],
    ):
        super().__init__()
        self._db       = db
        self._notifier = notifier
        self._settings = settings

        self._voice_mgr: Optional[VoiceManager] = None
        self._hotkey_listener = None
        self._active_category_id: Optional[int] = None
        self._task_widgets: Dict[int, TaskWidget] = {}
        self._current_tasks: List[Dict[str, Any]] = []

        self.setWindowTitle("BountyHunter")
        self.setMinimumSize(1060, 680)

        self._build_ui()
        self._setup_tray()
        self._setup_shortcuts()
        self._apply_theme(settings.get("theme", "dark"))

        if settings.get("voice_enabled", True):
            self._init_voice()

        self._init_global_hotkey()

        self._refresh_categories_sidebar()
        self._refresh_tasks()
        self._refresh_gamification_hud()
        self._start_status_refresh()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Sidebar (fixed 260px)
        self._sidebar = SidebarWidget(self)
        self._sidebar.view_changed.connect(self._on_sidebar_view_changed)
        self._sidebar.category_selected.connect(self._on_sidebar_category_selected)
        self._sidebar.add_category_requested.connect(self._on_add_category_dialog)
        self._sidebar.player_card_clicked.connect(self._show_missions_view)
        self._sidebar.settings_requested.connect(self._open_settings)
        root_layout.addWidget(self._sidebar)

        # 2. Main content area (right side)
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Top Bar
        self._topbar = TopBarWidget(self)
        self._topbar.search_changed.connect(self._on_search_changed)
        self._topbar.theme_toggled.connect(self._toggle_theme)
        self._topbar.settings_clicked.connect(self._open_settings)
        right_layout.addWidget(self._topbar)

        # Dotted background with StackedWidget
        self._dotted_bg = DottedBackgroundWidget(self)
        dotted_layout = QVBoxLayout(self._dotted_bg)
        dotted_layout.setContentsMargins(0, 0, 0, 0)
        dotted_layout.setSpacing(0)

        self._stack = QStackedWidget()

        # Page 0: Tasks View
        self._tasks_page = QWidget()
        tasks_page_layout = QVBoxLayout(self._tasks_page)
        tasks_page_layout.setContentsMargins(24, 16, 24, 16)
        tasks_page_layout.setSpacing(16)

        # Scroll area for tasks page
        tasks_scroll = QScrollArea()
        tasks_scroll.setWidgetResizable(True)
        tasks_scroll.setFrameShape(QFrame.Shape.NoFrame)
        tasks_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        tasks_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        tasks_scroll_content = QWidget()
        tasks_scroll_content.setStyleSheet("background: transparent;")
        self._tasks_content_layout = QVBoxLayout(tasks_scroll_content)
        self._tasks_content_layout.setContentsMargins(0, 0, 8, 0)
        self._tasks_content_layout.setSpacing(14)

        # Banner "Misión del día" (~170px)
        self._mission_banner = MissionBannerWidget(self)
        self._tasks_content_layout.addWidget(self._mission_banner)

        # Quick capture bar
        self._quick_add = QuickAddWidget(self)
        self._quick_add.add_task_requested.connect(self._on_quick_add_task)
        self._quick_add.complex_task_requested.connect(self._open_new_task)
        self._quick_add.voice_toggled.connect(self._toggle_voice)
        self._tasks_content_layout.addWidget(self._quick_add)

        # Filter bar (Todas / Hoy / Prioridad alta + Mostrar completadas)
        self._filter_bar = FilterBarWidget(self)
        self._filter_bar.filter_changed.connect(self._on_filter_bar_changed)
        self._filter_bar.show_completed_toggled.connect(self._on_show_completed_toggled)
        self._tasks_content_layout.addWidget(self._filter_bar)

        # Section: HOY
        self._section_today_header = self._create_section_header("section_today", 0)
        self._tasks_content_layout.addWidget(self._section_today_header)
        self._section_today_container = QVBoxLayout()
        self._section_today_container.setSpacing(8)
        self._tasks_content_layout.addLayout(self._section_today_container)

        # Section: PRÓXIMAS
        self._section_upcoming_header = self._create_section_header("section_upcoming", 0)
        self._tasks_content_layout.addWidget(self._section_upcoming_header)
        self._section_upcoming_container = QVBoxLayout()
        self._section_upcoming_container.setSpacing(8)
        self._tasks_content_layout.addLayout(self._section_upcoming_container)

        # Empty state widget
        self._empty_state = EmptyStateWidget(self)
        self._tasks_content_layout.addWidget(self._empty_state)
        self._empty_state.hide()

        self._tasks_content_layout.addStretch()
        tasks_scroll.setWidget(tasks_scroll_content)
        tasks_page_layout.addWidget(tasks_scroll)

        self._stack.addWidget(self._tasks_page)

        # Page 1: Dashboard
        self._dashboard_view = DashboardWidget(self._db, parent=self)
        self._dashboard_view.data_reset.connect(self._on_dashboard_reset)
        self._stack.addWidget(self._dashboard_view)

        # Page 2: Gamification / Missions
        self._gamification_view = GamificationWidget(self._db, parent=self)
        self._gamification_view.profile_updated.connect(self._refresh_gamification_hud)
        self._stack.addWidget(self._gamification_view)

        dotted_layout.addWidget(self._stack)
        right_layout.addWidget(self._dotted_bg, stretch=1)

        # Status Bar
        self._build_status_bar(right_layout)

        root_layout.addWidget(right_container, stretch=1)

    def _build_status_bar(self, parent_layout: QVBoxLayout) -> None:
        bar = QWidget()
        bar.setFixedHeight(34)
        bar.setStyleSheet(
            f"background-color: {BG_SIDEBAR}; border-top: 1px solid {BORDER_SUBTLE};"
        )
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(16, 0, 16, 0)
        bar_layout.setSpacing(12)

        # Left: "Total N · Activas N · Completadas hoy N"
        self._status_counts = QLabel("Total 0 · Activas 0 · Completadas hoy 0")
        self._status_counts.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 12px; font-weight: 500;"
        )
        bar_layout.addWidget(self._status_counts)

        bar_layout.addStretch()

        # Right: green dot + "Voz lista · di «Oye Taskmaster»"
        self._voice_status_dot = QLabel("●")
        self._voice_status_dot.setStyleSheet("color: #22C55E; font-size: 10px;")
        bar_layout.addWidget(self._voice_status_dot)

        self._voice_status_lbl = QLabel("Voz lista · di «Oye Taskmaster»")
        self._voice_status_lbl.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 12px; font-weight: 500;"
        )
        bar_layout.addWidget(self._voice_status_lbl)

        parent_layout.addWidget(bar)

    def _create_section_header(self, key: str, count: int) -> QWidget:
        w = QWidget()
        w.setFixedHeight(28)
        w.setStyleSheet("background: transparent;")
        w.setProperty("section_key", key)
        l = QHBoxLayout(w)
        l.setContentsMargins(2, 0, 2, 0)
        l.setSpacing(8)

        lbl = QLabel(f"{tr(key)} ({count})")
        lbl.setObjectName(f"header_label_{key}")
        lbl.setFont(QFont(FONT_FAMILY, 11, QFont.Weight.Bold))
        lbl.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 11px; font-weight: 700; letter-spacing: 1px;"
        )
        l.addWidget(lbl)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"border: none; border-top: 1px solid {BORDER_SUBTLE};")
        l.addWidget(line, stretch=1)
        return w

    def _update_section_header(self, header_widget: QWidget, key: str, count: int) -> None:
        lbl = header_widget.findChild(QLabel, f"header_label_{key}")
        if lbl:
            lbl.setText(f"{tr(key)} ({count})")

    # ------------------------------------------------------------------
    # System tray & Shortcuts
    # ------------------------------------------------------------------

    def _setup_tray(self) -> None:
        self._tray = QSystemTrayIcon(self)
        icon_path = Path(__file__).parent.parent / "assets" / "icon.ico"
        if icon_path.exists():
            self._tray.setIcon(QIcon(str(icon_path)))
        else:
            self._tray.setIcon(self.style().standardIcon(
                self.style().StandardPixmap.SP_ComputerIcon
            ))

        tray_menu = QMenu()
        tray_menu.setStyleSheet(
            f"QMenu {{ background: {BG_SURFACE}; color: {TEXT_PRIMARY}; border: 1px solid {BORDER_SUBTLE}; }}"
            f"QMenu::item:selected {{ background: {ACCENT_VIOLET}; }}"
        )
        show_action = tray_menu.addAction("Mostrar BountyHunter")
        new_task_action = tray_menu.addAction("➕ Nueva Tarea")
        tray_menu.addSeparator()
        quit_action = tray_menu.addAction("Salir")

        show_action.triggered.connect(self.show)
        new_task_action.triggered.connect(self._open_new_task)
        quit_action.triggered.connect(QApplication.quit)

        self._tray.setContextMenu(tray_menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show()
            self.raise_()

    def _setup_shortcuts(self) -> None:
        new_task = QAction("Nueva Tarea", self)
        new_task.setShortcut(QKeySequence("Ctrl+N"))
        new_task.triggered.connect(self._open_new_task)
        self.addAction(new_task)

        focus_search = QAction("Buscar", self)
        focus_search.setShortcut(QKeySequence("Ctrl+K"))
        focus_search.triggered.connect(self._topbar.focus_search)
        self.addAction(focus_search)

        toggle_voice = QAction("Toggle Voz", self)
        toggle_voice.setShortcut(QKeySequence("Ctrl+M"))
        toggle_voice.triggered.connect(lambda: self._quick_add._on_mic_clicked())
        self.addAction(toggle_voice)

    # ------------------------------------------------------------------
    # Voice manager
    # ------------------------------------------------------------------

    def _init_voice(self) -> None:
        engine = self._settings.get("voice_engine", "google")
        model_path = self._settings.get("vosk_model_path", "")
        lang = self._settings.get("voice_language", "auto")
        self._voice_mgr = VoiceManager(engine=engine, vosk_model_path=model_path, language=lang, parent=self)
        self._voice_mgr.command_recognized.connect(self._on_voice_command)
        self._voice_mgr.listening_state_changed.connect(self._on_listening_changed)
        self._voice_mgr.error_occurred.connect(self._on_voice_error)
        self._voice_mgr.raw_text_recognised.connect(
            lambda t: self._voice_status_lbl.setText(f'Escuchado: "{t}"')
        )

    def _toggle_voice(self, checked: bool) -> None:
        if self._voice_mgr is None:
            self._init_voice()
        if checked:
            self._voice_mgr.start_listening()
        else:
            self._voice_mgr.stop_listening()

    def _init_global_hotkey(self) -> None:
        """Register Windows global hotkey (Win + Alt + Space) for instant hands-free voice dictation."""
        if hasattr(self, "_hotkey_listener") and self._hotkey_listener:
            try:
                self._hotkey_listener.stop()
            except Exception:
                pass
            self._hotkey_listener = None

        if self._settings.get("global_hotkey_enabled", True):
            try:
                from core.hotkey import GlobalHotkeyListener
                self._hotkey_listener = GlobalHotkeyListener(parent=self)
                self._hotkey_listener.hotkey_triggered.connect(self._on_global_voice_hotkey)
                self._hotkey_listener.start()
            except Exception as exc:
                logger.warning("Failed to start GlobalHotkeyListener: %s", exc)

    def _on_global_voice_hotkey(self) -> None:
        """Called when user presses Win+Alt+Space anywhere in Windows."""
        # Restore window if hidden or minimized
        if self.isMinimized() or not self.isVisible():
            self.showNormal()
            self.raise_()
            self.activateWindow()

        # Trigger voice dictation toggle
        self._quick_add._on_mic_clicked()

    @pyqtSlot(bool)
    def _on_listening_changed(self, listening: bool) -> None:
        self._quick_add.set_listening(listening)
        if listening:
            self._voice_status_dot.setStyleSheet("color: #EF4444; font-size: 10px;")
            self._voice_status_lbl.setText("🎙 Escuchando...")
        else:
            self._voice_status_dot.setStyleSheet("color: #22C55E; font-size: 10px;")
            self._voice_status_lbl.setText("Voz lista · di «Oye Taskmaster»")

    @pyqtSlot(str)
    def _on_voice_error(self, message: str) -> None:
        self._voice_status_lbl.setText(f"⚠ Voz: {message}")
        self._quick_add.set_listening(False)

    @pyqtSlot(str, dict)
    def _on_voice_command(self, cmd_type: str, params: dict) -> None:
        title = params.get("title", "")

        # Record action in RPG progression
        v_res = self._db.record_action("voice_command", {"command": cmd_type})
        self._refresh_gamification_hud()
        if hasattr(self, "_gamification_view"):
            self._gamification_view.refresh_data()
        if v_res.get("leveled_up"):
            dlg = LevelUpDialog(v_res["new_level"], v_res["rank"]["title"], v_res["rank"]["icon"], self)
            dlg.exec()
        elif v_res.get("newly_completed_quests"):
            q_titles = ", ".join(q["title"] for q in v_res["newly_completed_quests"])
            self._voice_status_lbl.setText(f"🎯 ¡Misión cumplida: {q_titles}!")

        if cmd_type == "add_task":
            if title:
                priority = params.get("priority", 2)
                is_recurring = params.get("is_recurring", False)
                r_days = params.get("recurrence_days")
                r_time = params.get("recurrence_time")
                r_type = params.get("recurrence_type")
                task_id = self._db.add_task(
                    title=title,
                    priority=priority,
                    category_id=self._active_category_id,
                    is_recurring=is_recurring,
                    recurrence_days=r_days,
                    recurrence_time=r_time,
                    recurrence_type=r_type,
                )
                task = self._db.get_task(task_id)
                if task:
                    self._notifier.schedule_reminder(task)
                self._refresh_tasks()
                self._refresh_categories_sidebar()
                prio_name = {1: "Baja", 2: "Media", 3: "Alta"}.get(priority, "Media")
                cat_name = task.get("category_name") if task else None
                cat_badge = f" [{cat_name}]" if cat_name else ""
                rec_badge = f" [🔁 {task.get('recurrence_time', '')}]" if is_recurring else ""
                self._voice_status_lbl.setText(f'🎙 Tarea añadida{cat_badge}{rec_badge} [{prio_name}]: "{title}"')
        elif cmd_type == "complete_task":
            target_num = params.get("number")
            if target_num is None:
                target_num = extract_task_number(title)

            if target_num is not None:
                if 1 <= target_num <= len(self._current_tasks):
                    task_to_complete = self._current_tasks[target_num - 1]
                    self._on_task_completed(task_to_complete["id"])
                    self._voice_status_lbl.setText(
                        f'✅ Tarea #{target_num} completada: "{task_to_complete["title"]}"'
                    )
                else:
                    self._voice_status_lbl.setText(
                        f'⚠ Tarea #{target_num} no encontrada. Hay {len(self._current_tasks)} tareas visibles.'
                    )
            else:
                tasks = self._db.get_all_tasks(search=title)
                if tasks:
                    self._on_task_completed(tasks[0]["id"])
                    self._voice_status_lbl.setText(f'✅ Completada: "{tasks[0]["title"]}"')
                else:
                    self._voice_status_lbl.setText(f'⚠ No se encontró la tarea: "{title}"')
        elif cmd_type == "delete_task":
            target_num = params.get("number")
            if target_num is None:
                target_num = extract_task_number(title)

            if target_num is not None:
                if 1 <= target_num <= len(self._current_tasks):
                    task_to_delete = self._current_tasks[target_num - 1]
                    self._db.delete_task(task_to_delete["id"])
                    self._refresh_tasks()
                    self._refresh_categories_sidebar()
                    self._voice_status_lbl.setText(
                        f'🗑 Tarea #{target_num} eliminada: "{task_to_delete["title"]}"'
                    )
                else:
                    self._voice_status_lbl.setText(
                        f'⚠ Tarea #{target_num} no encontrada. Hay {len(self._current_tasks)} tareas visibles.'
                    )
            else:
                tasks = self._db.get_all_tasks(search=title)
                if tasks:
                    self._db.delete_task(tasks[0]["id"])
                    self._refresh_tasks()
                    self._refresh_categories_sidebar()
                    self._voice_status_lbl.setText(f'🗑 Eliminada: "{tasks[0]["title"]}"')
                else:
                    self._voice_status_lbl.setText(f'⚠ No se encontró la tarea: "{title}"')

        elif cmd_type in ("show_progress", "show_dashboard"):
            self._show_dashboard_view()
            self._voice_status_lbl.setText("📊 Mostrando Dashboard gráfico")
        elif cmd_type == "show_missions":
            self._show_missions_view()
            self._voice_status_lbl.setText("⚔️ Mostrando Centro de Misiones & RPG")
        elif cmd_type == "show_level":
            prof = self._db.get_gamification_profile()
            self._voice_status_lbl.setText(
                f"⚔️ Nivel {prof['level']} – {prof['rank']['title']} | XP: {prof['xp']}/{prof['xp_needed']}"
            )
        elif cmd_type == "show_tasks":
            self._show_tasks_view()
            self._voice_status_lbl.setText("📋 Mostrando lista de tareas")
        else:
            raw = params.get("raw", "").strip()
            if raw:
                title = params.get("title", raw)
                priority = params.get("priority", 2)
                is_recurring = params.get("is_recurring", False)
                r_days = params.get("recurrence_days")
                r_time = params.get("recurrence_time")
                r_type = params.get("recurrence_type")
                task_id = self._db.add_task(
                    title=title,
                    priority=priority,
                    category_id=self._active_category_id,
                    is_recurring=is_recurring,
                    recurrence_days=r_days,
                    recurrence_time=r_time,
                    recurrence_type=r_type,
                )
                task = self._db.get_task(task_id)
                if task:
                    self._notifier.schedule_reminder(task)
                self._refresh_tasks()
                self._refresh_categories_sidebar()
                prio_name = {1: "Baja", 2: "Media", 3: "Alta"}.get(priority, "Media")
                cat_name = task.get("category_name") if task else None
                cat_badge = f" [{cat_name}]" if cat_name else ""
                rec_badge = f" [🔁 {task.get('recurrence_time', '')}]" if is_recurring else ""
                self._voice_status_lbl.setText(f'🎙 Tarea creada{cat_badge}{rec_badge} [{prio_name}]: "{title}"')

    # ------------------------------------------------------------------
    # View Switching (Tasks vs Dashboard vs Missions)
    # ------------------------------------------------------------------

    def _on_sidebar_view_changed(self, index: int) -> None:
        if index == 0:
            self._show_tasks_view()
        elif index == 1:
            self._show_dashboard_view()
        elif index == 2:
            self._show_missions_view()

    def _show_tasks_view(self) -> None:
        self._stack.setCurrentIndex(0)
        self._sidebar.set_nav_index(0)
        self._update_topbar_title()
        self._refresh_tasks()
        self._refresh_gamification_hud()

    def _show_dashboard_view(self) -> None:
        self._stack.setCurrentIndex(1)
        self._sidebar.set_nav_index(1)
        self._topbar.set_title(tr("nav_dashboard"))
        if hasattr(self, "_dashboard_view"):
            self._dashboard_view.refresh_data()

    def _show_missions_view(self) -> None:
        self._stack.setCurrentIndex(2)
        self._sidebar.set_nav_index(2)
        self._topbar.set_title(tr("missions_title"))
        if hasattr(self, "_gamification_view"):
            self._gamification_view.refresh_data()
        self._refresh_gamification_hud()

    def _update_topbar_title(self) -> None:
        if self._active_category_id is None:
            self._topbar.set_title(tr("all_tasks_title"))
        else:
            categories = self._db.get_categories()
            cat = next((c for c in categories if c["id"] == self._active_category_id), None)
            if cat:
                cat_display = tr(f"cat_{cat['name'].lower()}", cat["name"])
                self._topbar.set_title(cat_display)
            else:
                self._topbar.set_title(tr("all_tasks_title"))

    def _on_sidebar_category_selected(self, cat_id: Optional[int]) -> None:
        self._active_category_id = cat_id
        if self._stack.currentIndex() != 0:
            self._show_tasks_view()
        else:
            self._update_topbar_title()
            self._refresh_tasks()

    def _on_add_category_dialog(self) -> None:
        dlg = CategoryAddDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            name, color = dlg.get_data()
            if name:
                self._db.add_category(name, color)
                self._refresh_categories_sidebar()
                self._voice_status_lbl.setText(f'Categoría "{name}" creada.')

    def _refresh_gamification_hud(self) -> None:
        """Update sidebar player card with latest level and XP."""
        profile = self._db.get_gamification_profile()
        self._sidebar.update_player_card(profile)

    def _on_dashboard_reset(self) -> None:
        self._refresh_tasks()
        self._refresh_categories_sidebar()
        self._refresh_gamification_hud()
        if hasattr(self, "_gamification_view"):
            self._gamification_view.refresh_data()
        self._voice_status_lbl.setText("🔄 Tareas y estadísticas reiniciadas")

    # ------------------------------------------------------------------
    # Category sidebar
    # ------------------------------------------------------------------

    def _refresh_categories_sidebar(self) -> None:
        counts = {}
        all_uncompleted = self._db.get_all_tasks(include_completed=False)
        counts[None] = len(all_uncompleted)
        for t in all_uncompleted:
            cid = t.get("category_id")
            counts[cid] = counts.get(cid, 0) + 1
        self._sidebar.update_categories(self._db.get_categories(), counts)

    # ------------------------------------------------------------------
    # Task list & sections
    # ------------------------------------------------------------------

    def _on_quick_add_task(self, text: str) -> None:
        if not text:
            return
        final_title, is_rec, r_days, r_time, r_type = extract_recurrence(text)
        task_id = self._db.add_task(
            title=final_title,
            priority=2,
            category_id=self._active_category_id,
            is_recurring=is_rec,
            recurrence_days=r_days,
            recurrence_time=r_time,
            recurrence_type=r_type,
        )
        task = self._db.get_task(task_id)
        if task:
            self._notifier.schedule_reminder(task)
        self._refresh_tasks()
        self._refresh_categories_sidebar()
        self._refresh_gamification_hud()
        cat_name = task.get("category_name") if task else None
        cat_badge = f" [{cat_name}]" if cat_name else ""
        rec_badge = f" [🔁 {task.get('recurrence_time', '')}]" if is_rec else ""
        self._voice_status_lbl.setText(f'Tarea agregada{cat_badge}{rec_badge}: "{final_title}"')

    def _on_filter_bar_changed(self, filter_mode: str) -> None:
        self._refresh_tasks()

    def _on_show_completed_toggled(self, checked: bool) -> None:
        self._refresh_tasks()

    def _on_search_changed(self, text: str) -> None:
        self._refresh_tasks()

    def _refresh_tasks(self) -> None:
        search   = self._topbar.search_text() or None
        inc_done = self._filter_bar.is_showing_completed()
        filter_mode = self._filter_bar.current_filter()

        tasks = self._db.get_all_tasks(
            category_id=self._active_category_id,
            include_completed=inc_done,
            search=search,
        )

        if filter_mode == "high":
            tasks = [t for t in tasks if t["priority"] == 3]
        elif filter_mode == "today":
            from datetime import date
            today_str = date.today().isoformat()
            tasks = [
                t for t in tasks
                if (t.get("due_date") and t["due_date"].startswith(today_str))
                or (not t.get("due_date") and t.get("created_at", "").startswith(today_str))
            ]

        # Clear existing task widgets
        self._task_widgets.clear()
        while self._section_today_container.count() > 0:
            item = self._section_today_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        while self._section_upcoming_container.count() > 0:
            item = self._section_upcoming_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Classify into HOY and PRÓXIMAS
        from datetime import date
        today_str = date.today().isoformat()

        today_list = []
        upcoming_list = []

        for t in tasks:
            due = t.get("due_date")
            created = t.get("created_at", "")
            if (due and (due.startswith(today_str) or due < today_str)) or (not due and created.startswith(today_str)):
                today_list.append(t)
            else:
                upcoming_list.append(t)

        self._current_tasks = list(tasks)

        # Update headers
        self._update_section_header(self._section_today_header, "section_today", len(today_list))
        self._update_section_header(self._section_upcoming_header, "section_upcoming", len(upcoming_list))

        self._section_today_header.setVisible(len(today_list) > 0)
        self._section_upcoming_header.setVisible(len(upcoming_list) > 0)

        for task in today_list:
            widget = self._create_task_widget(task)
            self._section_today_container.addWidget(widget)

        for task in upcoming_list:
            widget = self._create_task_widget(task)
            self._section_upcoming_container.addWidget(widget)

        # Empty state
        if len(tasks) == 0:
            self._empty_state.show()
        else:
            self._empty_state.hide()

        # Update Daily Mission Banner with all tasks of today
        all_today_tasks = [
            t for t in self._db.get_all_tasks(include_completed=True)
            if (t.get("due_date") and t["due_date"].startswith(today_str))
            or (t.get("created_at", "").startswith(today_str))
        ]
        completed_today = len([t for t in all_today_tasks if t.get("completed")])
        self._mission_banner.update_progress(completed_today, len(all_today_tasks))

        self._refresh_status()
        if hasattr(self, "_dashboard_view"):
            self._dashboard_view.refresh_data()

    def _create_task_widget(self, task: Dict[str, Any]) -> TaskWidget:
        subtasks = self._db.get_subtasks(task["id"])
        widget = TaskWidget(task, subtasks)
        widget.task_completed.connect(self._on_task_completed)
        widget.task_uncompleted.connect(self._on_task_uncompleted)
        widget.task_deleted.connect(self._on_task_deleted)
        widget.task_edit_requested.connect(self._on_task_edit)
        widget.subtask_toggled.connect(self._on_subtask_toggled)
        widget.add_subtask_requested.connect(self._on_add_subtask)
        widget.move_category_requested.connect(self._on_move_category)
        self._task_widgets[task["id"]] = widget
        return widget

    def _refresh_status(self) -> None:
        stats = self._db.get_stats()
        self._status_counts.setText(
            tr("status_summary", total=stats['total'], active=stats['active'], completed=stats['completed_today'])
        )
        self._topbar.set_subtitle(
            tr("stats_subtitle", active=stats['active'], completed=stats['completed_today'])
        )

    def _start_status_refresh(self) -> None:
        timer = QTimer(self)
        timer.setInterval(60_000)
        timer.timeout.connect(self._refresh_status)
        timer.start()

    # ------------------------------------------------------------------
    # Task interactions
    # ------------------------------------------------------------------

    def _open_new_task(self, initial_title: Any = "") -> None:
        title_str = initial_title if isinstance(initial_title, str) else ""
        dlg = TaskEditDialog(
            self._db,
            task_id=None,
            initial_title=title_str,
            initial_category_id=self._active_category_id,
            parent=self,
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            if hasattr(dlg, "saved_task_id") and dlg.saved_task_id:
                task = self._db.get_task(dlg.saved_task_id)
                if task:
                    self._notifier.schedule_reminder(task)
            self._refresh_tasks()
            self._refresh_categories_sidebar()
            self._refresh_gamification_hud()

    @pyqtSlot(int)
    def _on_task_completed(self, task_id: int) -> None:
        task = self._db.get_task(task_id)
        prio = task.get("priority", 2) if task else 2
        self._db.complete_task(task_id)
        res = self._db.record_action(
            "task_completed",
            {"priority": prio, "task_id": task_id, "title": task.get("title", "") if task else ""}
        )
        self._refresh_tasks()
        self._refresh_categories_sidebar()
        self._refresh_gamification_hud()
        if hasattr(self, "_gamification_view"):
            self._gamification_view.refresh_data()

        # Reschedule reminder for next instance if task was recurring
        updated_task = self._db.get_task(task_id)
        if updated_task and updated_task.get("is_recurring"):
            self._notifier.cancel_reminder(task_id)
            self._notifier.schedule_reminder(updated_task)

        if res.get("leveled_up"):
            self._notifier.notify_event(
                f"🎖 ASCENSO: ¡Nivel {res['new_level']} alcanzado!",
                f"Rango: {res['rank']['title']}. ¡Honor y gloria comandante!",
                event_type="level_up",
            )
            dlg = LevelUpDialog(res["new_level"], res["rank"]["title"], res["rank"]["icon"], self)
            dlg.exec()
        elif res.get("newly_completed_quests"):
            q_titles = ", ".join(q["title"] for q in res["newly_completed_quests"])
            self._notifier.notify_event(
                "🎯 Misión de Combate Cumplida",
                f"Has completado: {q_titles}",
                event_type="quest_completed",
            )
            self._voice_status_lbl.setText(f"🎯 ¡Misión cumplida: {q_titles}!")

    @pyqtSlot(int)
    def _on_task_uncompleted(self, task_id: int) -> None:
        self._db.uncomplete_task(task_id)
        self._refresh_tasks()
        self._refresh_categories_sidebar()
        self._refresh_gamification_hud()

    @pyqtSlot(int)
    def _on_task_deleted(self, task_id: int) -> None:
        reply = QMessageBox.question(
            self, "Eliminar Tarea",
            "¿Eliminar esta tarea permanentemente?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._notifier.cancel_reminder(task_id)
            self._db.delete_task(task_id)
            self._refresh_tasks()
            self._refresh_categories_sidebar()
            self._refresh_gamification_hud()

    @pyqtSlot(int)
    def _on_task_edit(self, task_id: int) -> None:
        dlg = TaskEditDialog(self._db, task_id=task_id, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            task = self._db.get_task(task_id)
            if task:
                self._notifier.schedule_reminder(task)
            self._refresh_tasks()
            self._refresh_categories_sidebar()

    @pyqtSlot(int, bool)
    def _on_subtask_toggled(self, subtask_id: int, completed: bool) -> None:
        self._db.complete_subtask(subtask_id, completed)
        if completed:
            res = self._db.record_action("subtask_completed")
            self._refresh_gamification_hud()
            if hasattr(self, "_gamification_view"):
                self._gamification_view.refresh_data()
            if res.get("leveled_up"):
                dlg = LevelUpDialog(res["new_level"], res["rank"]["title"], res["rank"]["icon"], self)
                dlg.exec()
            elif res.get("newly_completed_quests"):
                q_titles = ", ".join(q["title"] for q in res["newly_completed_quests"])
                self._voice_status_lbl.setText(f"🎯 ¡Misión cumplida: {q_titles}!")

    @pyqtSlot(int)
    def _on_add_subtask(self, task_id: int) -> None:
        self._on_task_edit(task_id)

    @pyqtSlot(int)
    def _on_move_category(self, task_id: int) -> None:
        from PyQt6.QtWidgets import QInputDialog
        categories = self._db.get_categories()
        names = [c["name"] for c in categories]
        name, ok = QInputDialog.getItem(
            self, "Mover a Categoría", "Selecciona la categoría:", names, 0, False
        )
        if ok and name:
            cat = next((c for c in categories if c["name"] == name), None)
            if cat:
                self._db.update_task(task_id, category_id=cat["id"])
                self._refresh_tasks()
                self._refresh_categories_sidebar()

    # ------------------------------------------------------------------
    # Theme & Settings
    # ------------------------------------------------------------------

    def _toggle_theme(self) -> None:
        current = self._settings.get("theme", "dark")
        new_theme = "light" if current == "dark" else "dark"
        self._settings["theme"] = new_theme
        self._apply_theme(new_theme)

    def _apply_theme(self, theme: str) -> None:
        qss = TASKMASTER_QSS if theme == "dark" else LIGHT_QSS
        QApplication.instance().setStyleSheet(qss)

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self._db, self._settings, parent=self)
        dlg.settings_saved.connect(self._on_settings_saved)
        dlg.exec()

    @pyqtSlot(dict)
    def _on_settings_saved(self, new_settings: Dict[str, Any]) -> None:
        self._settings = new_settings
        _save_settings(new_settings)
        set_language(new_settings.get("language", "es"))
        self._apply_theme(new_settings.get("theme", "dark"))
        self._retranslate_ui()

        self._notifier.set_enabled(new_settings.get("notifications_enabled", True))
        self._notifier.update_settings(new_settings)
        self._notifier.update_schedule(
            daily_hour=new_settings.get("daily_summary_hour", 9),
            daily_minute=new_settings.get("daily_summary_minute", 0),
            reminder_minutes=new_settings.get("reminder_minutes", 30),
            evening_hour=new_settings.get("evening_summary_hour", 21),
            evening_minute=new_settings.get("evening_summary_minute", 0),
        )

        if self._voice_mgr:
            self._voice_mgr.cleanup()
            self._voice_mgr = None

        if new_settings.get("voice_enabled", True):
            self._init_voice()

        self._init_global_hotkey()

        self._refresh_categories_sidebar()
        self._refresh_tasks()

    def _retranslate_ui(self) -> None:
        """Dynamically retranslate all child widgets upon language change."""
        self.setWindowTitle(tr("app_title"))
        if hasattr(self, "_topbar") and self._topbar:
            self._topbar.retranslate_ui()
        if hasattr(self, "_sidebar") and self._sidebar:
            self._sidebar.retranslate_ui()
        if hasattr(self, "_quick_add") and self._quick_add:
            self._quick_add.retranslate_ui()
        if hasattr(self, "_filter_bar") and self._filter_bar:
            self._filter_bar.retranslate_ui()
        if hasattr(self, "_empty_state") and self._empty_state:
            self._empty_state.retranslate_ui()
        if hasattr(self, "_mission_banner") and self._mission_banner:
            self._mission_banner.retranslate_ui()
        if hasattr(self, "_dashboard_view") and self._dashboard_view:
            self._dashboard_view.retranslate_ui()
        if hasattr(self, "_gamification_view") and self._gamification_view:
            self._gamification_view.retranslate_ui()
        if hasattr(self, "_voice_status_lbl") and self._voice_status_lbl:
            self._voice_status_lbl.setText(tr("voice_status_ready"))

        if hasattr(self, "_stack") and hasattr(self, "_topbar"):
            if self._stack.currentIndex() == 1:
                self._topbar.set_title(tr("nav_dashboard"))
            elif self._stack.currentIndex() == 2:
                self._topbar.set_title(tr("missions_title"))
            else:
                self._update_topbar_title()

        self._refresh_status()

    # ------------------------------------------------------------------
    # Window close
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        """Minimise to tray instead of quitting."""
        event.ignore()
        self.hide()
        self._tray.showMessage(
            "BountyHunter",
            "La aplicación sigue ejecutándose en la bandeja del sistema.",
            QSystemTrayIcon.MessageIcon.Information,
            2000,
        )

    def quit_app(self) -> None:
        """Cleanly quit the application."""
        if hasattr(self, "_hotkey_listener") and self._hotkey_listener:
            try:
                self._hotkey_listener.stop()
            except Exception:
                pass
        if self._voice_mgr:
            self._voice_mgr.cleanup()
        self._notifier.shutdown()
        _save_settings(self._settings)
        QApplication.quit()


# ===========================================================================
# Settings persistence helpers
# ===========================================================================

def load_settings() -> Dict[str, Any]:
    """Load settings from JSON file; fall back to defaults."""
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH, encoding="utf-8") as f:
                data = json.load(f)
            # Merge with defaults to pick up any new keys
            return {**DEFAULT_SETTINGS, **data}
        except Exception:
            pass
    return dict(DEFAULT_SETTINGS)


def _save_settings(settings: Dict[str, Any]) -> None:
    """Persist settings to JSON file."""
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
    except Exception as exc:
        logger.error("Failed to save settings: %s", exc)
