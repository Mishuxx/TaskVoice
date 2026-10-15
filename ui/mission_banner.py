"""
ui/mission_banner.py
====================
Daily Mission Banner with custom QPainter pixel-art / vector illustration.

Features:
- Height ~170px, border-radius 14px
- Custom painted sky (#151233), twinkling stars, ringed purple planet, small spaceship,
  stepped pixel mountain silhouettes.
- Overlay:
  * "MISIÓN DEL DÍA" gold badge (#F5B544)
  * "X de Y objetivos completados"
  * Diamond checkpoint track leading to a treasure chest (turns gold when all complete)
  * "Completa todas para abrir el cofre: +150 XP"
"""

from __future__ import annotations

import math
from typing import Optional
from PyQt6.QtCore import Qt, QRect, QRectF, QPointF
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QPainterPath, QLinearGradient,
)
from PyQt6.QtWidgets import QWidget

from ui.tokens import (
    ACCENT_GOLD, ACCENT_TURQUOISE, ACCENT_VIOLET,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    FONT_FAMILY, FONT_MONO,
)
from core.i18n import tr, get_language


class MissionBannerWidget(QWidget):
    """Illustrated banner for the Daily Mission."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedHeight(170)
        self._completed_count = 0
        self._total_count = 0
        self._all_done = False

    def update_progress(self, completed: int, total: int) -> None:
        self._completed_count = max(0, completed)
        self._total_count = max(0, total)
        self._all_done = (self._total_count > 0 and self._completed_count >= self._total_count)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()

        # Rounded clipping path
        clip_path = QPainterPath()
        clip_path.addRoundedRect(QRectF(0, 0, w, h), 14, 14)
        painter.setClipPath(clip_path)

        # 1. Sky background
        sky_grad = QLinearGradient(0, 0, 0, h)
        sky_grad.setColorAt(0.0, QColor("#181438"))
        sky_grad.setColorAt(0.6, QColor("#151233"))
        sky_grad.setColorAt(1.0, QColor("#0e0b24"))
        painter.fillRect(0, 0, w, h, sky_grad)

        # 2. Stars
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        star_coords = [
            (25, 20), (70, 45), (140, 22), (210, 50), (280, 18), (340, 35),
            (420, 25), (490, 55), (560, 20), (620, 42), (700, 15), (780, 48),
            (850, 22), (920, 52), (1000, 28), (1080, 40), (1150, 18),
            (95, 75), (180, 85), (320, 80), (450, 95), (650, 82), (820, 90),
            (980, 75), (1120, 88),
        ]
        painter.setPen(QColor(230, 235, 255, 180))
        for sx, sy in star_coords:
            if sx < w:
                painter.drawPoint(sx, sy)
        # Larger sparkling stars
        sparkles = [(160, 38), (510, 30), (880, 35)]
        painter.setPen(QColor("#5EEAD4"))
        for sx, sy in sparkles:
            if sx < w:
                painter.drawPoint(sx, sy)
                painter.drawPoint(sx + 1, sy)
                painter.drawPoint(sx - 1, sy)
                painter.drawPoint(sx, sy + 1)
                painter.drawPoint(sx, sy - 1)

        # 3. Violet ringed planet (near right side: w - 160, y: 40)
        planet_cx = max(300, w - 160)
        planet_cy = 44
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        
        # Planet body
        p_grad = QLinearGradient(planet_cx - 24, planet_cy - 24, planet_cx + 24, planet_cy + 24)
        p_grad.setColorAt(0.0, QColor("#9333EA"))
        p_grad.setColorAt(0.5, QColor("#6B21A8"))
        p_grad.setColorAt(1.0, QColor("#3B0764"))
        painter.setBrush(p_grad)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(planet_cx, planet_cy), 22, 22)

        # Ring
        painter.save()
        painter.translate(planet_cx, planet_cy)
        painter.rotate(-18)
        ring_pen = QPen(QColor(192, 132, 252, 190), 2.5)
        painter.setPen(ring_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QRectF(-36, -9, 72, 18))
        painter.restore()

        # 4. Small pixel spaceship
        ship_x = max(240, w - 260)
        ship_y = 32
        self._draw_spaceship(painter, ship_x, ship_y)

        # 5. Layered stepped pixel mountains (silhouette)
        self._draw_stepped_mountains(painter, w, h)

        # 6. Content overlay
        self._draw_content(painter, w, h)

        # Border outline
        painter.setPen(QPen(QColor(255, 255, 255, 18), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 14, 14)

    def _draw_spaceship(self, painter: QPainter, x: int, y: int) -> None:
        """Draw a small cute retro-futuristic spaceship with cyan engine glow."""
        painter.save()
        # Engine exhaust glow
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(45, 212, 191, 140))
        painter.drawRect(x - 6, y + 2, 4, 3)
        painter.setBrush(QColor(94, 234, 212, 220))
        painter.drawRect(x - 3, y + 2, 3, 3)

        # Hull
        painter.setBrush(QColor("#E2E8F0"))
        hull = [
            QRect(x, y + 2, 10, 3),
            QRect(x + 2, y + 1, 6, 5),
            QRect(x + 10, y + 3, 3, 1),
        ]
        for r in hull:
            painter.drawRect(r)

        # Cockpit visor
        painter.setBrush(QColor("#2DD4BF"))
        painter.drawRect(x + 4, y + 1, 3, 2)

        # Wings
        painter.setBrush(QColor("#A855F7"))
        painter.drawRect(x + 1, y, 3, 1)
        painter.drawRect(x + 1, y + 6, 3, 1)
        painter.restore()

    def _draw_stepped_mountains(self, painter: QPainter, w: int, h: int) -> None:
        """Draw layered pixel-style stepped mountains in purple/indigo silhouettes."""
        painter.save()
        # Back mountain layer (medium purple)
        c_back = QColor("#1D183B")
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(c_back)
        
        step_w = 14
        num_steps = (w // step_w) + 2
        
        # Mountain ridge 1 (Back)
        path1 = QPainterPath()
        path1.moveTo(0, h)
        for i in range(num_steps):
            x = i * step_w
            # Stepped waveform
            s = math.sin(i * 0.22) * 22 + math.cos(i * 0.45) * 12
            y = h - 55 - int(s)
            path1.lineTo(x, y)
            path1.lineTo(x + step_w, y)
        path1.lineTo(w, h)
        path1.closeSubpath()
        painter.drawPath(path1)

        # Front mountain ridge (Darker purple/indigo)
        c_front = QColor("#120F26")
        painter.setBrush(c_front)
        path2 = QPainterPath()
        path2.moveTo(0, h)
        for i in range(num_steps):
            x = i * step_w
            s = math.cos(i * 0.28) * 16 + math.sin(i * 0.6) * 10
            y = h - 35 - int(s)
            path2.lineTo(x, y)
            path2.lineTo(x + step_w, y)
        path2.lineTo(w, h)
        path2.closeSubpath()
        painter.drawPath(path2)

        painter.restore()

    def _draw_content(self, painter: QPainter, w: int, h: int) -> None:
        """Render text labels, checkpoints, and chest."""
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # 1. Badge: "MISIÓN DEL DÍA"
        badge_text = f"★ {tr('daily_mission')}"
        badge_w = 145 if get_language() == "es" else 130
        badge_rect = QRectF(24, 20, badge_w, 24)
        painter.setPen(QPen(QColor("#785217"), 1))
        painter.setBrush(QColor(245, 181, 68, 30))
        painter.drawRoundedRect(badge_rect, 6, 6)

        painter.setFont(QFont(FONT_FAMILY, 9, QFont.Weight.Bold))
        painter.setPen(QColor(ACCENT_GOLD))
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, badge_text)

        # 2. Main title / subtitle
        painter.setFont(QFont(FONT_FAMILY, 15, QFont.Weight.Bold))
        painter.setPen(QColor(TEXT_PRIMARY))
        
        if self._total_count == 0:
            status_text = "No tasks scheduled for today" if get_language() == "en" else "Sin tareas asignadas para hoy"
        else:
            status_text = tr("mission_progress", done=self._completed_count, total=self._total_count)
        painter.drawText(24, 72, status_text)

        # 3. Checkpoints path (diamonds leading to a chest)
        # Position diamonds around y = 100
        start_x = 24
        spacing = 30
        effective_total = max(3, min(self._total_count, 10))
        if self._total_count == 0:
            effective_total = 3

        for i in range(effective_total):
            cx = start_x + i * spacing + 10
            cy = 102
            is_done = (i < self._completed_count) and (self._total_count > 0)
            self._draw_diamond_checkpoint(painter, cx, cy, is_done)

            # Connecting line between checkpoints
            if i < effective_total - 1:
                next_cx = start_x + (i + 1) * spacing + 10
                painter.setPen(QPen(QColor("#2DD4BF" if is_done else "#2A2F3D"), 2))
                painter.drawLine(cx + 8, cy, next_cx - 8, cy)

        # Line leading to chest
        last_cx = start_x + (effective_total - 1) * spacing + 10
        chest_x = last_cx + 34
        painter.setPen(QPen(QColor("#2DD4BF" if self._all_done else "#2A2F3D"), 2))
        painter.drawLine(last_cx + 8, 102, chest_x - 6, 102)

        # Treasure chest at chest_x, 102
        self._draw_chest(painter, chest_x, 92, self._all_done)

        # 4. Reward text
        painter.setFont(QFont(FONT_FAMILY, 10, QFont.Weight.Medium))
        if self._all_done:
            painter.setPen(QColor(ACCENT_GOLD))
            reward_str = tr("chest_ready")
        else:
            painter.setPen(QColor(TEXT_SECONDARY))
            reward_str = tr("mission_reward")
        painter.drawText(24, 142, reward_str)

        painter.restore()

    def retranslate_ui(self) -> None:
        self.update()

    def _draw_diamond_checkpoint(self, painter: QPainter, cx: int, cy: int, is_done: bool) -> None:
        """Draw a diamond checkpoint."""
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        d_path = QPainterPath()
        d_path.moveTo(cx, cy - 7)
        d_path.lineTo(cx + 7, cy)
        d_path.lineTo(cx, cy + 7)
        d_path.lineTo(cx - 7, cy)
        d_path.closeSubpath()

        if is_done:
            painter.setBrush(QColor("#2DD4BF"))
            painter.setPen(QPen(QColor("#5EEAD4"), 1.5))
            painter.drawPath(d_path)
            # Center bright dot
            painter.setBrush(QColor("#FFFFFF"))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(cx, cy), 2, 2)
        else:
            painter.setBrush(QColor("#161B24"))
            painter.setPen(QPen(QColor("#2A2F3D"), 1.5))
            painter.drawPath(d_path)

        painter.restore()

    def _draw_chest(self, painter: QPainter, x: int, y: int, is_open: bool) -> None:
        """Draw a retro pixel/vector treasure chest. Turns radiant gold when is_open is True."""
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if is_open:
            # Radiant aura
            glow = QColor(245, 181, 68, 60)
            painter.setBrush(glow)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(x - 4, y - 4, 30, 28)

            # Golden chest body
            body_color = QColor("#F5B544")
            trim_color = QColor("#FFFBEB")
            lock_color = QColor("#D97706")
        else:
            # Wooden chest with bronze/steel trim
            body_color = QColor("#78350F")
            trim_color = QColor("#475569")
            lock_color = QColor("#94A3B8")

        # Lower chest box (22x12)
        painter.setBrush(body_color)
        painter.setPen(QPen(trim_color, 1.2))
        painter.drawRoundedRect(QRectF(x, y + 6, 22, 13), 3, 3)

        # Lid (arched)
        lid_path = QPainterPath()
        lid_path.moveTo(x - 1, y + 6)
        lid_path.quadTo(x + 11, y - 1, x + 23, y + 6)
        lid_path.closeSubpath()
        painter.drawPath(lid_path)

        # Center lock / keyhole
        painter.setBrush(lock_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(x + 9, y + 7, 4, 4)

        # Metal bands
        painter.setPen(QPen(trim_color, 1))
        painter.drawLine(x + 4, y + 6, x + 4, y + 18)
        painter.drawLine(x + 18, y + 6, x + 18, y + 18)

        painter.restore()
