"""
ui/task_widget.py
=================
Custom QWidget that displays a single task card in the task list.

Features
--------
- Checkbox to complete the task
- Coloured category badge
- Priority dots
- Due-date label
- Progress bar (auto-updates from subtask changes)
- Expand/collapse subtask list
- Right-click context menu: Edit, Delete, Add Subtask, Move to Category
- Double-click → opens edit dialog
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List, Dict, Any

from PyQt6.QtCore import (
    Qt, pyqtSignal, QSize, QPropertyAnimation, QEasingCurve, QRect,
)
from PyQt6.QtGui import QColor, QPainter, QBrush, QFont, QCursor, QAction
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QCheckBox,
    QProgressBar, QPushButton, QFrame, QSizePolicy, QMenu,
    QLineEdit, QScrollArea,
)


# ---------------------------------------------------------------------------
# Priority colours
# ---------------------------------------------------------------------------
PRIORITY_COLORS = {
    1: "#6b7280",  # low  – grey
    2: "#d97706",  # mid  – amber
    3: "#dc2626",  # high – red
}
PRIORITY_LABELS = {1: "Baja", 2: "Media", 3: "Alta"}


class CategoryBadge(QLabel):
    """A small coloured pill label showing a category name."""

    def __init__(self, name: str, color: str, parent=None):
        super().__init__(name, parent)
        self.setFixedHeight(20)
        self._color = color
        self._update_style()

    def set_category(self, name: str, color: str) -> None:
        self.setText(name)
        self._color = color
        self._update_style()

    def _update_style(self) -> None:
        # Determine text colour (dark/light) based on bg luminance
        c = QColor(self._color)
        lum = 0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()
        fg = "#1e1e2e" if lum > 160 else "#ffffff"
        self.setStyleSheet(
            f"background-color: {self._color}; color: {fg}; "
            "border-radius: 9px; padding: 0 8px; font-size: 11px; font-weight: 600;"
        )


class PriorityDots(QWidget):
    """Draws 1–3 filled circles representing task priority."""

    def __init__(self, priority: int = 2, parent=None):
        super().__init__(parent)
        self.priority = priority
        self.setFixedSize(40, 14)

    def set_priority(self, priority: int) -> None:
        self.priority = max(1, min(3, priority))
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(PRIORITY_COLORS.get(self.priority, "#6b7280"))
        dim   = QColor(color)
        dim.setAlpha(40)
        r = 5
        spacing = 14
        for i in range(3):
            x = i * spacing + r
            y = 7
            painter.setBrush(QBrush(color if i < self.priority else dim))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(x - r, y - r, r * 2, r * 2)
        painter.end()


class SubtaskRow(QWidget):
    """A single subtask row with a checkbox."""

    toggled = pyqtSignal(int, bool)   # subtask_id, completed

    def __init__(self, subtask: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.subtask_id = subtask["id"]
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 0, 0, 0)
        layout.setSpacing(6)

        self._cb = QCheckBox(subtask["title"])
        self._cb.setChecked(bool(subtask["completed"]))
        self._cb.stateChanged.connect(self._on_toggle)
        layout.addWidget(self._cb)
        layout.addStretch()

        self.setStyleSheet("color: #a6adc8; font-size: 12px;")

    def _on_toggle(self, state: int) -> None:
        self.toggled.emit(self.subtask_id, bool(state))


# ===========================================================================
# TaskWidget
# ===========================================================================

class TaskWidget(QFrame):
    """
    A card widget representing one task.

    Signals
    -------
    task_completed(int)       task_id
    task_uncompleted(int)     task_id
    task_deleted(int)         task_id
    task_edit_requested(int)  task_id
    subtask_toggled(int, bool) subtask_id, completed
    add_subtask_requested(int) task_id
    move_category_requested(int) task_id
    """

    task_completed        = pyqtSignal(int)
    task_uncompleted      = pyqtSignal(int)
    task_deleted          = pyqtSignal(int)
    task_edit_requested   = pyqtSignal(int)
    subtask_toggled       = pyqtSignal(int, bool)
    add_subtask_requested = pyqtSignal(int)
    move_category_requested = pyqtSignal(int)

    def __init__(
        self,
        task: Dict[str, Any],
        subtasks: List[Dict[str, Any]],
        index_number: Optional[int] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.task_id       = task["id"]
        self._task         = task
        self._subtasks     = subtasks
        self._index_number = index_number
        self._expanded     = False

        self._build_ui()
        self._apply_task_data()
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName("TaskCard")
        self.setStyleSheet(
            "#TaskCard {"
            "  background: #313244;"
            "  border-radius: 10px;"
            "  border: 1px solid #45475a;"
            "  margin: 3px 0;"
            "}"
            "#TaskCard:hover { border: 1px solid #7c3aed; }"
        )
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(6)

        # --- Top row ---
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        self._cb = QCheckBox()
        self._cb.setFixedSize(20, 20)
        self._cb.stateChanged.connect(self._on_checkbox)
        top_row.addWidget(self._cb)

        self._num_badge = QLabel()
        self._num_badge.setFixedHeight(22)
        self._num_badge.setStyleSheet(
            "background-color: #181825; color: #89b4fa; font-weight: 700; "
            "border: 1px solid #45475a; border-radius: 6px; padding: 2px 7px; "
            "font-size: 11px;"
        )
        if self._index_number is not None:
            self._num_badge.setText(f"#{self._index_number}")
            self._num_badge.setToolTip(f"Comando de voz: 'completar tarea {self._index_number}'")
        else:
            self._num_badge.hide()
        top_row.addWidget(self._num_badge)

        self._title_label = QLabel()
        self._title_label.setStyleSheet("font-size: 14px; font-weight: 600; color: #cdd6f4;")
        self._title_label.setWordWrap(True)
        top_row.addWidget(self._title_label, 1)

        self._priority_dots = PriorityDots()
        top_row.addWidget(self._priority_dots)

        self._expand_btn = QPushButton("▸")
        self._expand_btn.setFixedSize(22, 22)
        self._expand_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #6c7086; border: none; font-size: 12px; }"
            "QPushButton:hover { color: #cdd6f4; }"
        )
        self._expand_btn.clicked.connect(self._toggle_expand)
        top_row.addWidget(self._expand_btn)

        root.addLayout(top_row)


        # --- Middle row: badge + due date ---
        mid_row = QHBoxLayout()
        mid_row.setContentsMargins(28, 0, 0, 0)
        mid_row.setSpacing(8)

        self._badge = CategoryBadge("", "#7c3aed")
        mid_row.addWidget(self._badge)

        self._due_label = QLabel()
        self._due_label.setStyleSheet("font-size: 11px; color: #6c7086;")
        mid_row.addWidget(self._due_label)
        mid_row.addStretch()

        root.addLayout(mid_row)

        # --- Progress bar ---
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setFixedHeight(6)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setStyleSheet(
            "QProgressBar { background: #45475a; border-radius: 3px; }"
            "QProgressBar::chunk { background: #7c3aed; border-radius: 3px; }"
        )
        root.addWidget(self._progress_bar)

        # --- Subtask container (hidden by default) ---
        self._subtask_container = QWidget()
        self._subtask_container.setVisible(False)
        self._subtask_layout = QVBoxLayout(self._subtask_container)
        self._subtask_layout.setContentsMargins(0, 4, 0, 0)
        self._subtask_layout.setSpacing(2)
        root.addWidget(self._subtask_container)

    # ------------------------------------------------------------------
    # Data binding
    # ------------------------------------------------------------------

    def _apply_task_data(self) -> None:
        task = self._task
        self._title_label.setText(task.get("title", ""))
        self._cb.setChecked(bool(task.get("completed", 0)))
        self._priority_dots.set_priority(task.get("priority", 2))
        self._progress_bar.setValue(task.get("progress", 0))

        # Category badge
        cat_name  = task.get("category_name") or "Sin categoría"
        cat_color = task.get("category_color") or "#6b7280"
        self._badge.set_category(cat_name, cat_color)
        self._badge.setVisible(bool(task.get("category_name")))

        # Due date
        due = task.get("due_date")
        if due:
            try:
                dt = datetime.fromisoformat(due)
                now = datetime.now()
                diff = dt - now
                if diff.total_seconds() < 0:
                    self._due_label.setText(f"⚠ Vencida: {dt.strftime('%d/%m %H:%M')}")
                    self._due_label.setStyleSheet("font-size: 11px; color: #f38ba8;")
                elif diff.total_seconds() < 3600:
                    self._due_label.setText(f"⏰ {dt.strftime('%d/%m %H:%M')}")
                    self._due_label.setStyleSheet("font-size: 11px; color: #fab387;")
                else:
                    self._due_label.setText(dt.strftime("📅 %d/%m/%Y %H:%M"))
                    self._due_label.setStyleSheet("font-size: 11px; color: #6c7086;")
            except ValueError:
                self._due_label.setText(due)
        else:
            self._due_label.setText("")

        # Completed appearance
        if task.get("completed"):
            self._title_label.setStyleSheet(
                "font-size: 14px; font-weight: 600; color: #6c7086; text-decoration: line-through;"
            )

        self._rebuild_subtasks()

    def _rebuild_subtasks(self) -> None:
        """Repopulate the subtask container from self._subtasks."""
        # Remove old rows
        while self._subtask_layout.count():
            item = self._subtask_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for st in self._subtasks:
            row = SubtaskRow(st)
            row.toggled.connect(lambda sid, done: self.subtask_toggled.emit(sid, done))
            self._subtask_layout.addWidget(row)

        # Show expand button only if there are subtasks
        self._expand_btn.setVisible(len(self._subtasks) > 0)

    def update_task(self, task: Dict[str, Any], subtasks: List[Dict[str, Any]]) -> None:
        """Refresh the widget with new task data."""
        self._task     = task
        self._subtasks = subtasks
        self._apply_task_data()

    def update_progress(self, progress: int) -> None:
        """Update only the progress bar value."""
        self._progress_bar.setValue(progress)

    # ------------------------------------------------------------------
    # Interactions
    # ------------------------------------------------------------------

    def _on_checkbox(self, state: int) -> None:
        completed = bool(state)
        if completed:
            self.task_completed.emit(self.task_id)
        else:
            self.task_uncompleted.emit(self.task_id)

    def _toggle_expand(self) -> None:
        self._expanded = not self._expanded
        self._subtask_container.setVisible(self._expanded)
        self._expand_btn.setText("▾" if self._expanded else "▸")

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        self.task_edit_requested.emit(self.task_id)

    def _show_context_menu(self, pos) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: #313244; color: #cdd6f4; border: 1px solid #45475a; }"
            "QMenu::item:selected { background: #7c3aed; }"
        )
        edit_action   = menu.addAction("✏ Editar")
        subtask_action = menu.addAction("➕ Añadir Subtarea")
        move_action   = menu.addAction("📁 Mover a Categoría")
        menu.addSeparator()
        delete_action = menu.addAction("🗑 Eliminar")

        action = menu.exec(self.mapToGlobal(pos))
        if action == edit_action:
            self.task_edit_requested.emit(self.task_id)
        elif action == subtask_action:
            self.add_subtask_requested.emit(self.task_id)
        elif action == move_action:
            self.move_category_requested.emit(self.task_id)
        elif action == delete_action:
            self.task_deleted.emit(self.task_id)
