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
    QSizePolicy,
)
from PyQt6.QtCore import QDateTime

from core.tasks import DatabaseManager
from core.voice import VoiceManager
from core.notifier import NotificationManager
from ui.task_widget import TaskWidget
from ui.settings_dialog import SettingsDialog

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Settings persistence
# ---------------------------------------------------------------------------
SETTINGS_PATH = Path.home() / ".taskvoice" / "settings.json"

DEFAULT_SETTINGS: Dict[str, Any] = {
    "theme": "dark",
    "notifications_enabled": True,
    "reminder_minutes": 30,
    "daily_summary_enabled": True,
    "daily_summary_hour": 9,
    "daily_summary_minute": 0,
    "voice_enabled": True,
    "voice_engine": "google",
    "vosk_model_path": "",
    "push_to_talk": False,
}

# ---------------------------------------------------------------------------
# Dark / Light QSS themes
# ---------------------------------------------------------------------------
DARK_QSS = """
QMainWindow, QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: 'Segoe UI', Arial, sans-serif;
}
QToolBar {
    background: #181825;
    border-bottom: 1px solid #313244;
    padding: 4px;
    spacing: 6px;
}
QToolBar QToolButton {
    background: #313244;
    color: #cdd6f4;
    border-radius: 6px;
    padding: 4px 10px;
}
QToolBar QToolButton:hover { background: #45475a; }
QLineEdit {
    background: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 5px 10px;
}
QLineEdit:focus { border: 1px solid #7c3aed; }
QComboBox {
    background: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 4px 8px;
}
QComboBox::drop-down { border: none; }
QComboBox QAbstractItemView {
    background: #313244;
    color: #cdd6f4;
    selection-background-color: #7c3aed;
}
QScrollBar:vertical {
    background: #1e1e2e;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #45475a;
    border-radius: 4px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QStatusBar {
    background: #181825;
    color: #6c7086;
    font-size: 12px;
    border-top: 1px solid #313244;
}
QSplitter::handle { background: #313244; width: 1px; }
QLabel { color: #cdd6f4; }
QGroupBox { color: #cdd6f4; border: 1px solid #45475a; border-radius: 6px; margin-top: 10px; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
QSpinBox, QDateTimeEdit {
    background: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 4px 8px;
}
QCheckBox { color: #cdd6f4; }
QCheckBox::indicator { border: 2px solid #45475a; border-radius: 4px; width: 14px; height: 14px; }
QCheckBox::indicator:checked { background: #7c3aed; border-color: #7c3aed; }
QTextEdit {
    background: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 6px;
}
QDialog { background: #1e1e2e; }
QTabWidget::pane { border: none; }
QTabBar::tab { background: #313244; color: #cdd6f4; padding: 8px 18px; }
QTabBar::tab:selected { background: #7c3aed; color: #fff; }
QMessageBox { background: #1e1e2e; }
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

    def __init__(self, db: DatabaseManager, task_id: Optional[int] = None, parent=None):
        super().__init__(parent)
        self._db = db
        self._task_id = task_id
        self._task: Optional[Dict[str, Any]] = None
        self._subtasks: List[Dict[str, Any]] = []
        self._new_subtask_edits: List[QLineEdit] = []

        if task_id:
            self._task = db.get_task(task_id)
            self._subtasks = db.get_subtasks(task_id)
            self.setWindowTitle("Editar Tarea")
        else:
            self.setWindowTitle("Nueva Tarea")

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

    def _load_data(self) -> None:
        if self._task is None:
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
        if self._due_cb.isChecked():
            due_date = self._due_edit.dateTime().toString("yyyy-MM-dd HH:mm:ss")

        if self._task_id is None:
            # New task
            task_id = self._db.add_task(
                title=title,
                description=desc,
                category_id=cat_id,
                due_date=due_date,
                priority=priority,
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

        self.accept()


# ===========================================================================
# Sidebar category button
# ===========================================================================

class CategoryButton(QPushButton):
    """A sidebar button for filtering by category."""

    def __init__(self, name: str, color: str, cat_id: Optional[int] = None, parent=None):
        super().__init__(parent)
        self.cat_id = cat_id
        self.setText(name)
        self._color = color
        self.setCheckable(True)
        self.setFlat(True)
        self._apply_style(False)

    def _apply_style(self, active: bool) -> None:
        bg = self._color if active else "transparent"
        fg = "#1e1e2e" if active else "#cdd6f4"
        self.setStyleSheet(
            f"QPushButton {{ background: {bg}; color: {fg}; border-radius: 8px; "
            f"  text-align: left; padding: 8px 14px; font-size: 13px; border: none; }}"
            f"QPushButton:hover {{ background: {'#45475a' if not active else self._color}; }}"
        )

    def setChecked(self, checked: bool) -> None:  # noqa: N802
        super().setChecked(checked)
        self._apply_style(checked)


# ===========================================================================
# MainWindow
# ===========================================================================

class MainWindow(QMainWindow):
    """Primary application window."""

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
        self._active_category_id: Optional[int] = None
        self._task_widgets: Dict[int, TaskWidget] = {}

        # Voice button animation timer
        self._voice_anim_timer = QTimer(self)
        self._voice_anim_timer.setInterval(600)
        self._voice_anim_timer.timeout.connect(self._pulse_voice_button)
        self._voice_pulse_state = False

        self.setWindowTitle("TaskVoice")
        self.setMinimumSize(900, 620)

        self._build_ui()
        self._setup_tray()
        self._setup_shortcuts()
        self._apply_theme(settings.get("theme", "dark"))

        if settings.get("voice_enabled", True):
            self._init_voice()

        self._refresh_categories_sidebar()
        self._refresh_tasks()
        self._start_status_refresh()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        # Central widget + root layout
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Toolbar
        self._build_toolbar()

        # Splitter: sidebar | task list
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)

        # --- Sidebar ---
        sidebar = QWidget()
        sidebar.setFixedWidth(200)
        sidebar.setObjectName("Sidebar")
        sidebar.setStyleSheet("#Sidebar { background: #181825; }")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(8, 12, 8, 12)
        sidebar_layout.setSpacing(4)

        sidebar_title = QLabel("📋 Categorías")
        sidebar_title.setStyleSheet("font-size: 12px; color: #6c7086; font-weight: 600; padding: 0 6px 6px 6px;")
        sidebar_layout.addWidget(sidebar_title)

        self._sidebar_layout = QVBoxLayout()
        self._sidebar_layout.setSpacing(2)
        sidebar_layout.addLayout(self._sidebar_layout)
        sidebar_layout.addStretch()

        splitter.addWidget(sidebar)

        # --- Task list area ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(8)

        # Header row inside task panel
        header_row = QHBoxLayout()
        self._panel_title = QLabel("Todas las tareas")
        self._panel_title.setStyleSheet("font-size: 18px; font-weight: 700; color: #cdd6f4;")
        header_row.addWidget(self._panel_title)
        header_row.addStretch()

        self._show_completed_cb = QCheckBox("Mostrar completadas")
        self._show_completed_cb.stateChanged.connect(self._refresh_tasks)
        header_row.addWidget(self._show_completed_cb)

        right_layout.addLayout(header_row)

        # Scroll area for task cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._tasks_container = QWidget()
        self._tasks_layout = QVBoxLayout(self._tasks_container)
        self._tasks_layout.setContentsMargins(0, 0, 0, 0)
        self._tasks_layout.setSpacing(4)
        self._tasks_layout.addStretch()

        scroll.setWidget(self._tasks_container)
        right_layout.addWidget(scroll)

        # Empty state label
        self._empty_label = QLabel("No hay tareas. ¡Crea una con Ctrl+N!")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet("font-size: 16px; color: #45475a; margin: 40px;")
        right_layout.addWidget(self._empty_label)
        self._empty_label.hide()

        splitter.addWidget(right_panel)
        splitter.setSizes([200, 700])

        root_layout.addWidget(splitter)

        # Status bar
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_total   = QLabel()
        self._status_done    = QLabel()
        self._status_voice   = QLabel("🎙 Voz: inactiva")
        self._status_bar.addPermanentWidget(self._status_total)
        self._status_bar.addPermanentWidget(self._status_done)
        self._status_bar.addPermanentWidget(self._status_voice)

    def _build_toolbar(self) -> None:
        tb = QToolBar("Principal")
        tb.setMovable(False)
        tb.setIconSize(QSize(18, 18))
        tb.setStyleSheet(
            "QToolBar { background: #181825; border-bottom: 1px solid #313244; padding: 6px 10px; spacing: 6px; }"
        )
        self.addToolBar(tb)

        # New task button
        self._new_task_btn = QPushButton("＋ Nueva Tarea")
        self._new_task_btn.setStyleSheet(
            "QPushButton { background: #7c3aed; color: #fff; border-radius: 8px; padding: 6px 16px; font-weight: 600; }"
            "QPushButton:hover { background: #6d28d9; }"
        )
        self._new_task_btn.clicked.connect(self._open_new_task)
        tb.addWidget(self._new_task_btn)

        tb.addSeparator()

        # Voice button
        self._voice_btn = QPushButton("🎙 Voz")
        self._voice_btn.setCheckable(True)
        self._voice_btn.setStyleSheet(
            "QPushButton { background: #313244; color: #cdd6f4; border-radius: 8px; padding: 6px 14px; }"
            "QPushButton:checked { background: #dc2626; color: #fff; }"
            "QPushButton:hover { background: #45475a; }"
        )
        self._voice_btn.toggled.connect(self._toggle_voice)
        tb.addWidget(self._voice_btn)

        tb.addSeparator()

        # Search bar
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("🔍 Buscar tarea…")
        self._search_edit.setFixedWidth(220)
        self._search_edit.textChanged.connect(self._on_search_changed)
        tb.addWidget(self._search_edit)

        # Filter dropdown
        self._filter_combo = QComboBox()
        self._filter_combo.addItems(["Todas", "Alta prioridad", "Vencidas", "Hoy"])
        self._filter_combo.currentIndexChanged.connect(self._refresh_tasks)
        tb.addWidget(self._filter_combo)

        # Spacer
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)

        # Theme toggle
        self._theme_btn = QPushButton("☀")
        self._theme_btn.setFixedSize(34, 34)
        self._theme_btn.setStyleSheet(
            "QPushButton { background: #313244; color: #cdd6f4; border-radius: 8px; font-size: 16px; }"
            "QPushButton:hover { background: #45475a; }"
        )
        self._theme_btn.clicked.connect(self._toggle_theme)
        tb.addWidget(self._theme_btn)

        # Settings
        settings_btn = QPushButton("⚙")
        settings_btn.setFixedSize(34, 34)
        settings_btn.setStyleSheet(
            "QPushButton { background: #313244; color: #cdd6f4; border-radius: 8px; font-size: 16px; }"
            "QPushButton:hover { background: #45475a; }"
        )
        settings_btn.clicked.connect(self._open_settings)
        tb.addWidget(settings_btn)

    # ------------------------------------------------------------------
    # System tray
    # ------------------------------------------------------------------

    def _setup_tray(self) -> None:
        self._tray = QSystemTrayIcon(self)
        # Use a default icon if icon.ico is missing
        icon_path = Path(__file__).parent.parent / "assets" / "icon.ico"
        if icon_path.exists():
            self._tray.setIcon(QIcon(str(icon_path)))
        else:
            self._tray.setIcon(self.style().standardIcon(
                self.style().StandardPixmap.SP_ComputerIcon
            ))

        tray_menu = QMenu()
        tray_menu.setStyleSheet(
            "QMenu { background: #313244; color: #cdd6f4; }"
            "QMenu::item:selected { background: #7c3aed; }"
        )
        show_action    = tray_menu.addAction("Mostrar TaskVoice")
        new_task_action = tray_menu.addAction("➕ Nueva Tarea")
        tray_menu.addSeparator()
        quit_action    = tray_menu.addAction("Salir")

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

    # ------------------------------------------------------------------
    # Shortcuts
    # ------------------------------------------------------------------

    def _setup_shortcuts(self) -> None:
        new_task = QAction("Nueva Tarea", self)
        new_task.setShortcut(QKeySequence("Ctrl+N"))
        new_task.triggered.connect(self._open_new_task)
        self.addAction(new_task)

        toggle_voice = QAction("Toggle Voz", self)
        toggle_voice.setShortcut(QKeySequence("Ctrl+M"))
        toggle_voice.triggered.connect(lambda: self._voice_btn.toggle())
        self.addAction(toggle_voice)

    # ------------------------------------------------------------------
    # Voice manager
    # ------------------------------------------------------------------

    def _init_voice(self) -> None:
        engine      = self._settings.get("voice_engine", "google")
        model_path  = self._settings.get("vosk_model_path", "")
        self._voice_mgr = VoiceManager(engine=engine, vosk_model_path=model_path, parent=self)
        self._voice_mgr.command_recognized.connect(self._on_voice_command)
        self._voice_mgr.listening_state_changed.connect(self._on_listening_changed)
        self._voice_mgr.error_occurred.connect(self._on_voice_error)
        self._voice_mgr.raw_text_recognised.connect(
            lambda t: self.statusBar().showMessage(f'Escuchado: "{t}"', 4000)
        )

    def _toggle_voice(self, checked: bool) -> None:
        if self._voice_mgr is None:
            self._init_voice()
        if checked:
            self._voice_mgr.start_listening()
        else:
            self._voice_mgr.stop_listening()

    @pyqtSlot(bool)
    def _on_listening_changed(self, listening: bool) -> None:
        self._voice_btn.setChecked(listening)
        self._status_voice.setText("🎙 Voz: escuchando" if listening else "🎙 Voz: inactiva")
        if listening:
            self._voice_anim_timer.start()
        else:
            self._voice_anim_timer.stop()
            self._voice_btn.setText("🎙 Voz")

    def _pulse_voice_button(self) -> None:
        self._voice_pulse_state = not self._voice_pulse_state
        self._voice_btn.setText("🔴 Escuchando…" if self._voice_pulse_state else "🎙 Escuchando…")

    @pyqtSlot(str)
    def _on_voice_error(self, message: str) -> None:
        self.statusBar().showMessage(f"⚠ Voz: {message}", 6000)
        self._voice_btn.setChecked(False)

    @pyqtSlot(str, dict)
    def _on_voice_command(self, cmd_type: str, params: dict) -> None:
        title = params.get("title", "")
        if cmd_type == "add_task":
            if title:
                task_id = self._db.add_task(title=title)
                self._refresh_tasks()
                self.statusBar().showMessage(f'✅ Tarea añadida: "{title}"', 4000)
        elif cmd_type == "complete_task":
            tasks = self._db.get_all_tasks(search=title)
            if tasks:
                self._db.complete_task(tasks[0]["id"])
                self._refresh_tasks()
                self.statusBar().showMessage(f'✅ Completada: "{tasks[0]["title"]}"', 4000)
        elif cmd_type == "delete_task":
            tasks = self._db.get_all_tasks(search=title)
            if tasks:
                self._db.delete_task(tasks[0]["id"])
                self._refresh_tasks()
                self.statusBar().showMessage(f'🗑 Eliminada: "{tasks[0]["title"]}"', 4000)
        elif cmd_type == "show_progress":
            stats = self._db.get_stats()
            self.statusBar().showMessage(
                f"Activas: {stats['active']} | Completadas hoy: {stats['completed_today']} | Vencidas: {stats['overdue']}",
                8000,
            )
        else:
            self.statusBar().showMessage(f'❓ Comando no reconocido: "{params.get("raw", "")}"', 4000)

    # ------------------------------------------------------------------
    # Category sidebar
    # ------------------------------------------------------------------

    def _refresh_categories_sidebar(self) -> None:
        # Remove old buttons
        while self._sidebar_layout.count():
            item = self._sidebar_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # "All" button
        all_btn = CategoryButton("📋 Todas", "#7c3aed", cat_id=None)
        all_btn.setChecked(self._active_category_id is None)
        all_btn.clicked.connect(lambda: self._set_category_filter(None, all_btn))
        self._sidebar_layout.addWidget(all_btn)
        self._all_cat_btn = all_btn

        # Per-category buttons
        self._cat_buttons: List[CategoryButton] = [all_btn]
        for cat in self._db.get_categories():
            btn = CategoryButton(f"● {cat['name']}", cat["color"], cat_id=cat["id"])
            btn.setChecked(self._active_category_id == cat["id"])
            btn.clicked.connect(
                lambda checked, c=cat["id"], b=btn: self._set_category_filter(c, b)
            )
            self._sidebar_layout.addWidget(btn)
            self._cat_buttons.append(btn)

    def _set_category_filter(self, cat_id: Optional[int], clicked_btn: CategoryButton) -> None:
        self._active_category_id = cat_id
        for btn in self._cat_buttons:
            btn.setChecked(btn is clicked_btn)
        cat_label = "Todas las tareas" if cat_id is None else clicked_btn.text().lstrip("● ")
        self._panel_title.setText(cat_label)
        self._refresh_tasks()

    # ------------------------------------------------------------------
    # Task list
    # ------------------------------------------------------------------

    def _refresh_tasks(self) -> None:
        search   = self._search_edit.text().strip() or None
        inc_done = self._show_completed_cb.isChecked()
        filter_idx = self._filter_combo.currentIndex()

        tasks = self._db.get_all_tasks(
            category_id=self._active_category_id,
            include_completed=inc_done,
            search=search,
        )

        # Apply extra filter
        if filter_idx == 1:   # high priority
            tasks = [t for t in tasks if t["priority"] == 3]
        elif filter_idx == 2: # overdue
            from datetime import datetime
            now = datetime.now().isoformat(sep=" ", timespec="seconds")
            tasks = [t for t in tasks if t.get("due_date") and t["due_date"] < now and not t["completed"]]
        elif filter_idx == 3: # due today
            from datetime import date
            today = date.today().isoformat()
            tasks = [t for t in tasks if t.get("due_date") and t["due_date"].startswith(today)]

        # Clear existing widgets
        self._task_widgets.clear()
        while self._tasks_layout.count() > 1:  # keep the trailing stretch
            item = self._tasks_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not tasks:
            self._empty_label.show()
        else:
            self._empty_label.hide()

        for task in tasks:
            subtasks = self._db.get_subtasks(task["id"])
            widget = TaskWidget(task, subtasks)
            widget.task_completed.connect(self._on_task_completed)
            widget.task_uncompleted.connect(self._on_task_uncompleted)
            widget.task_deleted.connect(self._on_task_deleted)
            widget.task_edit_requested.connect(self._on_task_edit)
            widget.subtask_toggled.connect(self._on_subtask_toggled)
            widget.add_subtask_requested.connect(self._on_add_subtask)
            widget.move_category_requested.connect(self._on_move_category)
            self._tasks_layout.insertWidget(self._tasks_layout.count() - 1, widget)
            self._task_widgets[task["id"]] = widget

        self._refresh_status()

    def _refresh_status(self) -> None:
        stats = self._db.get_stats()
        self._status_total.setText(f"Total: {stats['total']}  |  Activas: {stats['active']}")
        self._status_done.setText(f"Completadas hoy: {stats['completed_today']}")

    def _start_status_refresh(self) -> None:
        timer = QTimer(self)
        timer.setInterval(60_000)  # every minute
        timer.timeout.connect(self._refresh_status)
        timer.start()

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def _on_search_changed(self, text: str) -> None:
        self._refresh_tasks()

    # ------------------------------------------------------------------
    # Task interactions
    # ------------------------------------------------------------------

    def _open_new_task(self) -> None:
        dlg = TaskEditDialog(self._db, task_id=None, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._refresh_tasks()
            self._refresh_categories_sidebar()

    @pyqtSlot(int)
    def _on_task_completed(self, task_id: int) -> None:
        self._db.complete_task(task_id)
        self._refresh_tasks()

    @pyqtSlot(int)
    def _on_task_uncompleted(self, task_id: int) -> None:
        self._db.uncomplete_task(task_id)
        self._refresh_tasks()

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

    @pyqtSlot(int)
    def _on_task_edit(self, task_id: int) -> None:
        dlg = TaskEditDialog(self._db, task_id=task_id, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            task = self._db.get_task(task_id)
            if task:
                self._notifier.schedule_reminder(task)
            self._refresh_tasks()

    @pyqtSlot(int, bool)
    def _on_subtask_toggled(self, subtask_id: int, completed: bool) -> None:
        self._db.complete_subtask(subtask_id, completed)
        # Update progress bar in the widget
        cur = self._db._cursor()
        cur.execute("SELECT task_id FROM subtasks WHERE id=?", (subtask_id,))
        row = cur.fetchone()
        if row:
            task = self._db.get_task(row["task_id"])
            if task and row["task_id"] in self._task_widgets:
                self._task_widgets[row["task_id"]].update_progress(task["progress"])

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

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    def _toggle_theme(self) -> None:
        current = self._settings.get("theme", "dark")
        new_theme = "light" if current == "dark" else "dark"
        self._settings["theme"] = new_theme
        self._apply_theme(new_theme)
        self._theme_btn.setText("🌙" if new_theme == "dark" else "☀")

    def _apply_theme(self, theme: str) -> None:
        qss = DARK_QSS if theme == "dark" else LIGHT_QSS
        QApplication.instance().setStyleSheet(qss)
        self._theme_btn.setText("☀" if theme == "dark" else "🌙")

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self._db, self._settings, parent=self)
        dlg.settings_saved.connect(self._on_settings_saved)
        dlg.exec()

    @pyqtSlot(dict)
    def _on_settings_saved(self, new_settings: Dict[str, Any]) -> None:
        self._settings = new_settings
        _save_settings(new_settings)
        self._apply_theme(new_settings.get("theme", "dark"))

        # Update notifier
        self._notifier.set_enabled(new_settings.get("notifications_enabled", True))
        self._notifier.update_schedule(
            daily_hour=new_settings.get("daily_summary_hour", 9),
            daily_minute=new_settings.get("daily_summary_minute", 0),
            reminder_minutes=new_settings.get("reminder_minutes", 30),
        )

        # Restart voice manager if needed
        if self._voice_mgr:
            was_listening = self._voice_mgr.is_listening
            self._voice_mgr.cleanup()
            self._voice_mgr = None

        if new_settings.get("voice_enabled", True):
            self._init_voice()
            if was_listening if 'was_listening' in dir() else False:
                self._voice_mgr.start_listening()

        self._refresh_categories_sidebar()
        self._refresh_tasks()

    # ------------------------------------------------------------------
    # Window close
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:  # noqa: N802
        """Minimise to tray instead of quitting."""
        event.ignore()
        self.hide()
        self._tray.showMessage(
            "TaskVoice",
            "La aplicación sigue ejecutándose en la bandeja del sistema.",
            QSystemTrayIcon.MessageIcon.Information,
            2000,
        )

    def quit_app(self) -> None:
        """Cleanly quit the application."""
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
