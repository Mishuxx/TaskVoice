"""
ui/task_widget.py
=================
Task card widget redesigned with dark gamer/HUD aesthetic:
- Background #161B24, subtle border #232A36, border-radius 12px
- Stylized HUD corner accents on top-left and bottom-right in the category's color
- Rounded turquoise checkbox with smooth check
- Title (strikethrough & muted gray when completed)
- Metadata row: category dot + name, calendar icon + date, gold coin icon + "+100 XP"
- Priority badge with text (Alta naranja / Media azul / Baja gris)
- More menu button "⋯" with Edit, Add subtask, Move, Delete
- Expandable subtasks list
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List, Dict, Any

from PyQt6.QtCore import (
    Qt, pyqtSignal, QSize, QRectF, QPointF,
)
from PyQt6.QtGui import (
    QColor, QPainter, QPen, QBrush, QFont, QCursor, QPainterPath,
)
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QCheckBox,
    QPushButton, QFrame, QMenu, QSizePolicy,
)

from ui.tokens import (
    BG_SURFACE, BORDER_SUBTLE,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    ACCENT_TURQUOISE, ACCENT_GOLD,
    PRIORITY_HIGH_COLOR, PRIORITY_MED_COLOR, PRIORITY_LOW_COLOR,
    PRIORITY_HIGH_LABEL, PRIORITY_MED_LABEL, PRIORITY_LOW_LABEL,
    PRIORITY_XP, FONT_FAMILY, FONT_MONO,
)


class HudCheckbox(QWidget):
    """Custom rounded checkbox with turquoise HUD check styling."""

    toggled = pyqtSignal(bool)

    def __init__(self, checked: bool = False, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedSize(22, 22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._checked = checked

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool) -> None:
        if self._checked != checked:
            self._checked = checked
            self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._checked = not self._checked
            self.update()
            self.toggled.emit(self._checked)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(2, 2, 18, 18)

        if self._checked:
            # Filled turquoise background
            painter.setBrush(QColor(ACCENT_TURQUOISE))
            painter.setPen(QPen(QColor("#5EEAD4"), 1.2))
            painter.drawRoundedRect(rect, 5, 5)

            # White checkmark
            painter.setPen(QPen(QColor("#0D1015"), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            check_path = QPainterPath()
            check_path.moveTo(6.5, 11)
            check_path.lineTo(9.5, 14)
            check_path.lineTo(15.5, 7.5)
            painter.drawPath(check_path)
        else:
            # Empty HUD outline
            painter.setBrush(QColor("#11151C"))
            painter.setPen(QPen(QColor("#2A3345"), 1.5))
            painter.drawRoundedRect(rect, 5, 5)


class SubtaskRow(QWidget):
    """A single subtask row inside an expanded card."""

    toggled = pyqtSignal(int, bool)

    def __init__(self, subtask: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.subtask_id = subtask["id"]
        layout = QHBoxLayout(self)
        layout.setContentsMargins(36, 2, 8, 2)
        layout.setSpacing(8)

        self._cb = HudCheckbox(bool(subtask["completed"]))
        self._cb.toggled.connect(lambda done: self.toggled.emit(self.subtask_id, done))
        layout.addWidget(self._cb)

        self._label = QLabel(subtask["title"])
        if subtask["completed"]:
            self._label.setStyleSheet(f"color: {TEXT_MUTED}; text-decoration: line-through; font-size: 13px;")
        else:
            self._label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 13px;")
        layout.addWidget(self._label, stretch=1)


class TaskWidget(QFrame):
    """
    Task card with HUD corner brackets in category color,
    clean metadata, priority badge, and '⋯' menu.
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
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.task_id = task["id"]
        self._task = task
        self._subtasks = subtasks
        self._index_number = index_number
        self._expanded = False

        self._build_ui()
        self._apply_task_data()
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _build_ui(self) -> None:
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(6)

        # Top row: Checkbox, Title, Priority badge, Menu button, Subtask expander
        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        # 1. Checkbox
        self._cb = HudCheckbox()
        self._cb.toggled.connect(self._on_check_toggled)
        top_row.addWidget(self._cb)

        # 2. Title
        self._title_label = QLabel()
        self._title_label.setFont(QFont(FONT_FAMILY, 14, QFont.Weight.DemiBold))
        self._title_label.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 14px;")
        self._title_label.setWordWrap(True)
        top_row.addWidget(self._title_label, stretch=1)

        # 3. Priority badge
        self._priority_badge = QLabel("Media")
        self._priority_badge.setFixedHeight(24)
        self._priority_badge.setFont(QFont(FONT_FAMILY, 11, QFont.Weight.Bold))
        top_row.addWidget(self._priority_badge)

        # 4. Expand subtasks toggle (if subtasks exist)
        self._expand_btn = QPushButton("▸")
        self._expand_btn.setFixedSize(24, 24)
        self._expand_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._expand_btn.setStyleSheet(
            f"""
            QPushButton {{
                background: transparent;
                color: {TEXT_MUTED};
                border: none;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                color: {TEXT_PRIMARY};
            }}
            """
        )
        self._expand_btn.clicked.connect(self._toggle_expand)
        top_row.addWidget(self._expand_btn)

        # 5. Menu "⋯" button
        self._menu_btn = QPushButton("⋯")
        self._menu_btn.setFixedSize(26, 26)
        self._menu_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._menu_btn.setStyleSheet(
            f"""
            QPushButton {{
                background: transparent;
                color: {TEXT_MUTED};
                border: none;
                font-size: 16px;
                font-weight: bold;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background: #1F2837;
                color: {TEXT_PRIMARY};
            }}
            """
        )
        self._menu_btn.clicked.connect(self._open_menu_from_btn)
        top_row.addWidget(self._menu_btn)

        root.addLayout(top_row)

        # Metadata row: Category dot + name, calendar + date, gold coin + XP
        meta_row = QHBoxLayout()
        meta_row.setContentsMargins(34, 0, 0, 0)
        meta_row.setSpacing(16)

        # Category indicator
        self._cat_container = QWidget()
        cat_l = QHBoxLayout(self._cat_container)
        cat_l.setContentsMargins(0, 0, 0, 0)
        cat_l.setSpacing(6)

        self._cat_dot = QLabel("●")
        self._cat_dot.setStyleSheet("font-size: 11px;")
        cat_l.addWidget(self._cat_dot)

        self._cat_name = QLabel("")
        self._cat_name.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; font-weight: 500;")
        cat_l.addWidget(self._cat_name)
        meta_row.addWidget(self._cat_container)

        # Due date
        self._due_label = QLabel()
        self._due_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
        meta_row.addWidget(self._due_label)

        # XP reward
        self._xp_label = QLabel("🪙 +100 XP")
        self._xp_label.setFont(QFont(FONT_MONO, 11, QFont.Weight.Bold))
        self._xp_label.setStyleSheet(f"color: {ACCENT_GOLD}; font-size: 12px;")
        meta_row.addWidget(self._xp_label)

        meta_row.addStretch()
        root.addLayout(meta_row)

        # Subtasks container
        self._subtask_container = QWidget()
        self._subtask_container.setVisible(False)
        self._subtask_layout = QVBoxLayout(self._subtask_container)
        self._subtask_layout.setContentsMargins(0, 4, 0, 0)
        self._subtask_layout.setSpacing(3)
        root.addWidget(self._subtask_container)

    def _apply_task_data(self) -> None:
        task = self._task
        is_completed = bool(task.get("completed", 0))

        # Title
        title = task.get("title", "")
        self._title_label.setText(title)
        if is_completed:
            self._title_label.setStyleSheet(
                f"color: {TEXT_MUTED}; font-size: 14px; text-decoration: line-through;"
            )
        else:
            self._title_label.setStyleSheet(
                f"color: {TEXT_PRIMARY}; font-size: 14px;"
            )

        # Checkbox
        self._cb.setChecked(is_completed)

        # Priority badge
        prio = task.get("priority", 2)
        if prio == 3:
            self._priority_badge.setText(PRIORITY_HIGH_LABEL)
            self._priority_badge.setStyleSheet(
                f"""
                background-color: rgba(245, 158, 11, 0.16);
                color: {PRIORITY_HIGH_COLOR};
                border-radius: 6px;
                padding: 2px 10px;
                """
            )
            xp_amount = PRIORITY_XP.get(3, 100)
        elif prio == 1:
            self._priority_badge.setText(PRIORITY_LOW_LABEL)
            self._priority_badge.setStyleSheet(
                f"""
                background-color: rgba(100, 116, 139, 0.16);
                color: {PRIORITY_LOW_COLOR};
                border-radius: 6px;
                padding: 2px 10px;
                """
            )
            xp_amount = PRIORITY_XP.get(1, 30)
        else:
            self._priority_badge.setText(PRIORITY_MED_LABEL)
            self._priority_badge.setStyleSheet(
                f"""
                background-color: rgba(96, 165, 250, 0.16);
                color: {PRIORITY_MED_COLOR};
                border-radius: 6px;
                padding: 2px 10px;
                """
            )
            xp_amount = PRIORITY_XP.get(2, 60)

        # XP Label
        self._xp_label.setText(f"🪙 +{xp_amount} XP")

        # Category
        cat_name = task.get("category_name")
        cat_color = task.get("category_color") or "#60A5FA"
        if cat_name:
            self._cat_container.setVisible(True)
            self._cat_dot.setStyleSheet(f"color: {cat_color}; font-size: 11px;")
            self._cat_name.setText(cat_name)
        else:
            self._cat_container.setVisible(False)

        # Due date
        due = task.get("due_date")
        if due:
            try:
                dt = datetime.fromisoformat(due)
                now = datetime.now()
                diff = dt - now
                if diff.total_seconds() < 0 and not is_completed:
                    self._due_label.setText(f"⚠ Vencida: {dt.strftime('%d/%m %H:%M')}")
                    self._due_label.setStyleSheet("color: #F87171; font-size: 12px;")
                elif diff.total_seconds() < 3600 and not is_completed:
                    self._due_label.setText(f"⏰ {dt.strftime('%d/%m %H:%M')}")
                    self._due_label.setStyleSheet("color: #FBBF24; font-size: 12px;")
                else:
                    self._due_label.setText(f"📅 {dt.strftime('%d/%m/%Y')}")
                    self._due_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
            except Exception:
                self._due_label.setText(f"📅 {due}")
                self._due_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
        else:
            self._due_label.setText("")

        self._rebuild_subtasks()

    def _rebuild_subtasks(self) -> None:
        while self._subtask_layout.count():
            item = self._subtask_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for st in self._subtasks:
            row = SubtaskRow(st)
            row.toggled.connect(lambda sid, done: self.subtask_toggled.emit(sid, done))
            self._subtask_layout.addWidget(row)

        self._expand_btn.setVisible(len(self._subtasks) > 0)

    def paintEvent(self, event) -> None:
        """
        Draw the HUD Card background and category-colored corner brackets.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()
        rect = QRectF(0.5, 0.5, w - 1, h - 1)

        # 1. Background fill #161B24 with border #232A36
        is_completed = bool(self._task.get("completed", 0))
        bg_col = QColor("#131720" if is_completed else BG_SURFACE)
        border_col = QColor(BORDER_SUBTLE)

        painter.setBrush(bg_col)
        painter.setPen(QPen(border_col, 1))
        painter.drawRoundedRect(rect, 12, 12)

        # 2. Stylized HUD corners in Category color
        cat_color_str = self._task.get("category_color")
        if cat_color_str:
            corner_pen = QPen(QColor(cat_color_str), 2.2)
            corner_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(corner_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)

            arm = 14  # length of corner bracket arm

            # Top-left corner bracket
            tl_path = QPainterPath()
            tl_path.moveTo(0.5, arm + 4)
            tl_path.lineTo(0.5, 12)
            tl_path.quadTo(0.5, 0.5, 12, 0.5)
            tl_path.lineTo(arm + 4, 0.5)
            painter.drawPath(tl_path)

            # Bottom-right corner bracket
            br_path = QPainterPath()
            br_path.moveTo(w - arm - 4, h - 0.5)
            br_path.lineTo(w - 12, h - 0.5)
            br_path.quadTo(w - 0.5, h - 0.5, w - 0.5, h - 12)
            br_path.lineTo(w - 0.5, h - arm - 4)
            painter.drawPath(br_path)

    def update_task(self, task: Dict[str, Any], subtasks: List[Dict[str, Any]]) -> None:
        self._task = task
        self._subtasks = subtasks
        self._apply_task_data()
        self.update()

    def _on_check_toggled(self, checked: bool) -> None:
        if checked:
            self.task_completed.emit(self.task_id)
        else:
            self.task_uncompleted.emit(self.task_id)

    def _toggle_expand(self) -> None:
        self._expanded = not self._expanded
        self._subtask_container.setVisible(self._expanded)
        self._expand_btn.setText("▾" if self._expanded else "▸")

    def mouseDoubleClickEvent(self, event) -> None:
        self.task_edit_requested.emit(self.task_id)

    def _open_menu_from_btn(self) -> None:
        self._show_context_menu(self._menu_btn.pos() + QPointF(0, self._menu_btn.height()).toPoint())

    def _show_context_menu(self, pos) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(
            f"""
            QMenu {{
                background-color: {BG_SURFACE};
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER_SUBTLE};
                border-radius: 8px;
                padding: 4px 0;
            }}
            QMenu::item {{
                padding: 6px 20px;
            }}
            QMenu::item:selected {{
                background-color: #1F2837;
            }}
            """
        )
        edit_action = menu.addAction("✏ Editar")
        subtask_action = menu.addAction("➕ Añadir Subtarea")
        move_action = menu.addAction("📁 Mover a Categoría")
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
