"""
ui/sidebar_widget.py
====================
Fixed left sidebar (~260px) for Taskmaster.
Includes:
- Logo (violet icon + "Taskmaster")
- Vertical Navigation (Tareas, Dashboard, Misiones)
- Categorías with active highlight (#1C1730), colored dots, and counter badges
- Player Card at the bottom with avatar, level badge, 10-segment XP bar, and medals
"""

from __future__ import annotations

from typing import Optional, List, Dict, Any

from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush, QPolygonF
from PyQt6.QtCore import QPointF
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QSizePolicy,
)

from ui.tokens import (
    BG_SIDEBAR, BG_SURFACE, BG_NAV_ACTIVE, BG_CAT_ACTIVE,
    BORDER_CAT_ACTIVE, BORDER_SUBTLE, TEXT_PRIMARY, TEXT_SECONDARY,
    TEXT_MUTED, ACCENT_VIOLET, ACCENT_VIOLET_SOFT, ACCENT_TURQUOISE,
    ACCENT_TURQUOISE_BRIGHT, XP_EMPTY_BLOCK, ACCENT_GOLD,
    ACCENT_GOLD_BG, CATEGORY_COLORS,
)
from core.i18n import tr


# ---------------------------------------------------------------------------
# Navigation Button
# ---------------------------------------------------------------------------
class NavButton(QPushButton):
    """Vertical navigation button (44px height) with active state."""

    def __init__(self, text: str, icon_str: str, parent=None):
        super().__init__(parent)
        self._icon_str = icon_str
        self.setText(f"  {icon_str}  {text}")
        self.setFixedHeight(44)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_style(False)

    def set_nav_text(self, text: str) -> None:
        self.setText(f"  {self._icon_str}  {text}")

    def _apply_style(self, active: bool) -> None:
        if active:
            self.setStyleSheet(
                f"QPushButton {{ background-color: {BG_NAV_ACTIVE}; color: {TEXT_PRIMARY}; "
                f"border-radius: 8px; text-align: left; padding-left: 14px; font-weight: 700; font-size: 13px; border: none; }}"
            )
        else:
            self.setStyleSheet(
                f"QPushButton {{ background-color: transparent; color: {TEXT_SECONDARY}; "
                f"border-radius: 8px; text-align: left; padding-left: 14px; font-weight: 500; font-size: 13px; border: none; }}"
                f"QPushButton:hover {{ background-color: {BG_SURFACE}; color: {TEXT_PRIMARY}; }}"
            )

    def setChecked(self, checked: bool) -> None:
        super().setChecked(checked)
        self._apply_style(checked)


# ---------------------------------------------------------------------------
# Category Item Button
# ---------------------------------------------------------------------------
class CategoryItemButton(QFrame):
    """
    Category button with colored dot, label, and counter badge on the right.
    Active state: background #1C1730 and border #3B2F63.
    """
    clicked = pyqtSignal()

    def __init__(self, name: str, color: str, cat_id: Optional[int] = None, count: int = 0, parent=None):
        super().__init__(parent)
        self.cat_id = cat_id
        self._color = color
        self._is_active = False
        self.setFixedHeight(36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(10)

        # Dot
        self._dot = QLabel("●")
        self._dot.setStyleSheet(f"color: {color}; font-size: 12px;")
        layout.addWidget(self._dot)

        # Label
        self._label = QLabel(name)
        self._label.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 13px; font-weight: 500;")
        layout.addWidget(self._label, 1)

        # Badge counter
        self._badge = QLabel(str(count))
        self._badge.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 11px; font-family: 'JetBrains Mono', monospace; font-weight: 600;"
        )
        layout.addWidget(self._badge)

        self._update_style()

    def set_active(self, active: bool) -> None:
        self._is_active = active
        self._update_style()

    def set_count(self, count: int) -> None:
        self._badge.setText(str(count))

    def _update_style(self) -> None:
        if self._is_active:
            self.setStyleSheet(
                f"QFrame {{ background-color: {BG_CAT_ACTIVE}; border: 1px solid {BORDER_CAT_ACTIVE}; border-radius: 8px; }}"
            )
            self._label.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 13px; font-weight: 700;")
            self._badge.setStyleSheet(
                f"color: {TEXT_PRIMARY}; font-size: 11px; font-family: 'JetBrains Mono', monospace; font-weight: 700;"
            )
        else:
            self.setStyleSheet(
                f"QFrame {{ background-color: transparent; border: 1px solid transparent; border-radius: 8px; }}"
                f"QFrame:hover {{ background-color: {BG_SURFACE}; }}"
            )
            self._label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 13px; font-weight: 500;")
            self._badge.setStyleSheet(
                f"color: {TEXT_MUTED}; font-size: 11px; font-family: 'JetBrains Mono', monospace; font-weight: 600;"
            )

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)


# ---------------------------------------------------------------------------
# Pixel Art Avatar (Vector QPainter)
# ---------------------------------------------------------------------------
class PixelAvatar(QWidget):
    """
    Draws a pixel-art helmet (violet helmet with turquoise visor)
    inside a 60px frame with violet border and a golden badge with level number.
    """
    def __init__(self, level: int = 1, parent=None):
        super().__init__(parent)
        self.setFixedSize(60, 60)
        self._level = level

    def set_level(self, level: int) -> None:
        self._level = level
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        # Base Frame (rounded container with violet border)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setBrush(QColor("#161426"))
        painter.setPen(QPen(QColor(ACCENT_VIOLET), 1.5))
        painter.drawRoundedRect(2, 2, 56, 56, 10, 10)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        # Draw Pixel Helmet (12x12 grid inside 40x40 area centered)
        # Colors:
        # P = Purple (#7C3AED), D = Dark Purple (#4C1D95), T = Turquoise (#2DD4BF), B = Dark (#0F0D1B)
        grid = [
            "....PPPP....",
            "...PPPPPP...",
            "..PPPPPPPP..",
            "..PDDDDDDP..",
            ".PDTTTTTTDP.",
            ".PDTTTTTTDP.",
            ".PDDDDDDDDP.",
            "..PPPPPPPP..",
            "..PPPPPPPP..",
            "...PP..PP...",
        ]

        px_size = 3
        offset_x = 12
        offset_y = 12

        color_map = {
            'P': QColor("#8B5CF6"),
            'D': QColor("#4C1D95"),
            'T': QColor(ACCENT_TURQUOISE_BRIGHT),
            'B': QColor("#1E1B4B"),
        }

        for row_idx, row in enumerate(grid):
            for col_idx, ch in enumerate(row):
                if ch in color_map:
                    painter.fillRect(
                        offset_x + col_idx * px_size,
                        offset_y + row_idx * px_size,
                        px_size, px_size,
                        color_map[ch]
                    )

        # Level Badge (bottom right corner)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        badge_rect_x = 42
        badge_rect_y = 42
        painter.setBrush(QColor(ACCENT_GOLD))
        painter.setPen(QPen(QColor("#B45309"), 1))
        painter.drawRoundedRect(badge_rect_x, badge_rect_y, 16, 16, 4, 4)

        # Level number inside badge
        painter.setPen(QColor("#000000"))
        font = QFont("JetBrains Mono", 8, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(badge_rect_x, badge_rect_y, 16, 16, Qt.AlignmentFlag.AlignCenter, str(self._level))


# ---------------------------------------------------------------------------
# 10-Segment XP Bar Widget
# ---------------------------------------------------------------------------
class SegmentedXPBar(QWidget):
    """
    Renders 10 discrete health/energy style blocks:
    filled #2DD4BF, empty #2A2F3D.
    """
    def __init__(self, current_xp: int = 0, max_xp: int = 500, parent=None):
        super().__init__(parent)
        self.setFixedHeight(10)
        self._current_xp = current_xp
        self._max_xp = max(1, max_xp)

    def set_xp(self, current: int, max_val: int) -> None:
        self._current_xp = current
        self._max_xp = max(1, max_val)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        total_segments = 10
        ratio = min(1.0, max(0.0, self._current_xp / self._max_xp))
        filled_segments = int(round(ratio * total_segments))

        spacing = 3
        w = self.width()
        seg_w = max(2, (w - (total_segments - 1) * spacing) // total_segments)

        for i in range(total_segments):
            x = i * (seg_w + spacing)
            color = QColor(ACCENT_TURQUOISE) if i < filled_segments else QColor(XP_EMPTY_BLOCK)
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(x, 1, seg_w, 8, 2, 2)


# ---------------------------------------------------------------------------
# Hexagonal Achievement Medal (Vector QPainter)
# ---------------------------------------------------------------------------
class HexMedal(QWidget):
    """A small hexagonal achievement medal (gold if unlocked, grey if locked)."""

    def __init__(self, icon: str, unlocked: bool = False, tooltip_text: str = "", parent=None):
        super().__init__(parent)
        self.setFixedSize(24, 24)
        self._icon = icon
        self._unlocked = unlocked
        if tooltip_text:
            self.setToolTip(tooltip_text)

    def set_unlocked(self, unlocked: bool) -> None:
        self._unlocked = unlocked
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Hexagon points
        r = 11
        cx, cy = 12, 12
        import math
        points = []
        for i in range(6):
            angle = math.radians(60 * i - 30)
            x = cx + r * math.cos(angle)
            y = cy + r * math.sin(angle)
            points.append(QPointF(x, y))

        poly = QPolygonF(points)

        if self._unlocked:
            painter.setBrush(QColor(ACCENT_GOLD))
            painter.setPen(QPen(QColor("#FDE68A"), 1))
        else:
            painter.setBrush(QColor("#222836"))
            painter.setPen(QPen(QColor("#334155"), 1))

        painter.drawPolygon(poly)

        # Icon / symbol inside
        painter.setPen(QColor("#000000" if self._unlocked else "#64748B"))
        font = QFont("Segoe UI Emoji", 7)
        painter.setFont(font)
        painter.drawText(0, 0, 24, 24, Qt.AlignmentFlag.AlignCenter, self._icon)


# ---------------------------------------------------------------------------
# Player Card Widget (Bottom of Sidebar)
# ---------------------------------------------------------------------------
class PlayerCard(QFrame):
    """
    Displays avatar, rank title in turquoise #5EEAD4, 10-block XP bar,
    monospace XP metrics, and 3 hexagonal achievement medals.
    """
    card_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("PlayerCard")
        self.setStyleSheet(
            f"#PlayerCard {{ background-color: {BG_SURFACE}; border: 1px solid {BORDER_SUBTLE}; border-radius: 12px; }}"
            f"#PlayerCard:hover {{ border-color: {ACCENT_VIOLET_SOFT}; }}"
        )
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Top row: Avatar + Rank / Level
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        self._avatar = PixelAvatar(level=1)
        top_row.addWidget(self._avatar)

        rank_col = QVBoxLayout()
        rank_col.setSpacing(2)

        self._lvl_lbl = QLabel("NIVEL 1")
        self._lvl_lbl.setStyleSheet(f"font-size: 10px; font-weight: 800; color: {TEXT_MUTED}; letter-spacing: 0.5px;")
        rank_col.addWidget(self._lvl_lbl)

        self._rank_title = QLabel("Recluta\nTerran")
        self._rank_title.setStyleSheet(
            f"font-size: 13px; font-weight: 800; color: {ACCENT_TURQUOISE_BRIGHT}; line-height: 1.1;"
        )
        self._rank_title.setWordWrap(True)
        rank_col.addWidget(self._rank_title)

        top_row.addLayout(rank_col, 1)
        layout.addLayout(top_row)

        # 10-segment XP Bar
        self._xp_bar = SegmentedXPBar(current_xp=0, max_xp=500)
        layout.addWidget(self._xp_bar)

        # XP Labels (Monospace)
        xp_row = QHBoxLayout()
        self._xp_current_lbl = QLabel("0 / 500 XP")
        self._xp_current_lbl.setStyleSheet(
            f"font-family: 'JetBrains Mono', Consolas, monospace; font-size: 10px; color: {TEXT_SECONDARY};"
        )
        xp_row.addWidget(self._xp_current_lbl)
        xp_row.addStretch()

        self._xp_remaining_lbl = QLabel("500 para N2")
        self._xp_remaining_lbl.setStyleSheet(
            f"font-family: 'JetBrains Mono', Consolas, monospace; font-size: 10px; color: {TEXT_MUTED};"
        )
        xp_row.addWidget(self._xp_remaining_lbl)
        layout.addLayout(xp_row)

        # 3 Hexagonal Achievement Medals
        medals_row = QHBoxLayout()
        medals_row.setSpacing(8)

        self._medal_first_task = HexMedal("⚔", unlocked=False, tooltip_text="Logro: Primera tarea completada")
        self._medal_100_xp = HexMedal("★", unlocked=False, tooltip_text="Logro: 100 XP acumulados")
        self._medal_daily_mission = HexMedal("🎯", unlocked=False, tooltip_text="Logro: Misión del día completada")

        medals_row.addWidget(self._medal_first_task)
        medals_row.addWidget(self._medal_100_xp)
        medals_row.addWidget(self._medal_daily_mission)
        medals_row.addStretch()

        layout.addLayout(medals_row)

    def mousePressEvent(self, event):
        self.card_clicked.emit()
        super().mousePressEvent(event)

    def update_profile(self, profile: Dict[str, Any]) -> None:
        level = profile.get("level", 1)
        rank = profile.get("rank", {})
        xp = profile.get("xp", 0)
        xp_needed = profile.get("xp_needed", 500)
        total_xp = profile.get("total_xp", 0)
        tasks_done = profile.get("tasks_completed_count", 0)
        quests_done = profile.get("quests_completed_count", 0)

        self._avatar.set_level(level)
        self._lvl_lbl.setText(tr("level_label", level=level))
        self._rank_title.setText(rank.get("title", "Recluta Terran"))

        self._xp_bar.set_xp(xp, xp_needed)
        self._xp_current_lbl.setText(f"{xp} / {xp_needed} XP")

        remaining = max(0, xp_needed - xp)
        self._xp_remaining_lbl.setText(tr("xp_to_next", remaining=remaining, next_lvl=level + 1))

        # Update medals
        self._medal_first_task.set_unlocked(tasks_done > 0)
        self._medal_100_xp.set_unlocked(total_xp >= 100)
        self._medal_daily_mission.set_unlocked(quests_done > 0)


# ---------------------------------------------------------------------------
# Sidebar Main Widget
# ---------------------------------------------------------------------------
class SidebarWidget(QWidget):
    """
    Complete left sidebar container (~260px fixed width).
    """
    view_changed = pyqtSignal(int)          # 0: Tareas, 1: Dashboard, 2: Misiones
    category_selected = pyqtSignal(object)  # None for All, or category_id int
    add_category_requested = pyqtSignal()
    player_card_clicked = pyqtSignal()
    settings_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(260)
        self.setObjectName("Sidebar")
        self.setStyleSheet(f"#Sidebar {{ background-color: {BG_SIDEBAR}; border-right: 1px solid {BORDER_SUBTLE}; }}")

        self._cat_items: List[CategoryItemButton] = []
        self._active_cat_id: Optional[int] = None

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 18, 16, 16)
        layout.setSpacing(14)

        # ------------------------------------------------------------------
        # 1. Logo
        # ------------------------------------------------------------------
        logo_row = QHBoxLayout()
        logo_row.setSpacing(12)

        logo_box = QLabel("🎙")
        logo_box.setFixedSize(36, 36)
        logo_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_box.setStyleSheet(
            f"background-color: {ACCENT_VIOLET}; border-radius: 9px; color: #FFFFFF; font-size: 18px;"
        )
        logo_row.addWidget(logo_box)

        logo_title = QLabel("Taskmaster")
        logo_title.setStyleSheet(f"font-size: 19px; font-weight: 800; color: {TEXT_PRIMARY}; letter-spacing: 0.3px;")
        logo_row.addWidget(logo_title, 1)

        layout.addLayout(logo_row)
        layout.addSpacing(6)

        # ------------------------------------------------------------------
        # 2. Vertical Navigation Buttons
        # ------------------------------------------------------------------
        # 2. Vertical Navigation Buttons
        # ------------------------------------------------------------------
        self._nav_tasks = NavButton(tr("nav_tasks"), "📋")
        self._nav_dashboard = NavButton(tr("nav_dashboard"), "📈")
        self._nav_missions = NavButton(tr("nav_missions"), "⚔️")
        self._nav_settings = NavButton(tr("nav_settings"), "⚙️")

        self._nav_tasks.setChecked(True)

        self._nav_tasks.clicked.connect(lambda: self._select_nav(0))
        self._nav_dashboard.clicked.connect(lambda: self._select_nav(1))
        self._nav_missions.clicked.connect(lambda: self._select_nav(2))
        self._nav_settings.clicked.connect(self.settings_requested.emit)

        layout.addWidget(self._nav_tasks)
        layout.addWidget(self._nav_dashboard)
        layout.addWidget(self._nav_missions)
        layout.addWidget(self._nav_settings)

        layout.addSpacing(10)

        # ------------------------------------------------------------------
        # 3. Categorías Section
        # ------------------------------------------------------------------
        self._cat_header = QLabel(tr("categories_header"))
        self._cat_header.setStyleSheet(
            f"font-size: 11px; font-weight: 700; color: {TEXT_MUTED}; letter-spacing: 1px; padding-left: 6px;"
        )
        layout.addWidget(self._cat_header)

        self._cat_container = QVBoxLayout()
        self._cat_container.setSpacing(4)
        layout.addLayout(self._cat_container)

        # "+ Nueva categoría" button
        self._add_cat_btn = QPushButton(tr("new_category"))
        self._add_cat_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add_cat_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {TEXT_SECONDARY}; text-align: left; padding: 6px 10px; "
            f"font-size: 12px; font-weight: 500; border: none; border-radius: 6px; }}"
            f"QPushButton:hover {{ color: {ACCENT_VIOLET_SOFT}; background-color: {BG_SURFACE}; }}"
        )
        self._add_cat_btn.clicked.connect(self.add_category_requested.emit)
        layout.addWidget(self._add_cat_btn)

        layout.addStretch()

        # ------------------------------------------------------------------
        # 4. Player Card at the bottom
        # ------------------------------------------------------------------
        self._player_card = PlayerCard()
        self._player_card.card_clicked.connect(self.player_card_clicked.emit)
        layout.addWidget(self._player_card)

    def retranslate_ui(self) -> None:
        self._nav_tasks.set_nav_text(tr("nav_tasks"))
        self._nav_dashboard.set_nav_text(tr("nav_dashboard"))
        self._nav_missions.set_nav_text(tr("nav_missions"))
        self._nav_settings.set_nav_text(tr("nav_settings"))
        self._cat_header.setText(tr("categories_header"))
        self._add_cat_btn.setText(tr("new_category"))
        if self._cat_items:
            self._cat_items[0]._label.setText(tr("cat_all"))

    def _select_nav(self, index: int) -> None:
        self._nav_tasks.setChecked(index == 0)
        self._nav_dashboard.setChecked(index == 1)
        self._nav_missions.setChecked(index == 2)
        self.view_changed.emit(index)

    def set_nav_index(self, index: int) -> None:
        self._nav_tasks.setChecked(index == 0)
        self._nav_dashboard.setChecked(index == 1)
        self._nav_missions.setChecked(index == 2)

    def update_categories(self, categories: List[Dict[str, Any]], counts: Dict[Optional[int], int]) -> None:
        """Populate category items with colors and task count badges."""
        while self._cat_container.count() > 0:
            item = self._cat_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._cat_items.clear()

        # "Todas" item
        total_count = counts.get(None, 0)
        all_item = CategoryItemButton(
            name=tr("cat_all"),
            color=ACCENT_VIOLET_SOFT,
            cat_id=None,
            count=total_count,
        )
        all_item.set_active(self._active_cat_id is None)
        all_item.clicked.connect(lambda: self._on_cat_clicked(None, all_item))
        self._cat_container.addWidget(all_item)
        self._cat_items.append(all_item)

        for cat in categories:
            cid = cat["id"]
            name = cat["name"]
            color = cat.get("color") or CATEGORY_COLORS.get(name, "#60A5FA")
            c_count = counts.get(cid, 0)

            item_btn = CategoryItemButton(
                name=name,
                color=color,
                cat_id=cid,
                count=c_count,
            )
            item_btn.set_active(self._active_cat_id == cid)
            item_btn.clicked.connect(lambda c=cid, b=item_btn: self._on_cat_clicked(c, b))
            self._cat_container.addWidget(item_btn)
            self._cat_items.append(item_btn)

    def _on_cat_clicked(self, cat_id: Optional[int], clicked_item: CategoryItemButton) -> None:
        self._active_cat_id = cat_id
        for item in self._cat_items:
            item.set_active(item is clicked_item)
        self.category_selected.emit(cat_id)

    def update_player_card(self, profile: Dict[str, Any]) -> None:
        self._player_card.update_profile(profile)
