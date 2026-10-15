"""
ui/dashboard_widget.py
======================
Modern, high-performance graphical dashboard for TaskVoice.
Renders visual statistics, donut progress chart, weekly productivity histogram,
KPI summary cards, category distributions, and priority breakdown.
Uses native PyQt6 QPainter vector graphics for crisp, high-DPI rendering.
"""

from __future__ import annotations

import math
from typing import Dict, Any, List, Optional

from PyQt6.QtCore import Qt, QRectF, QSize, pyqtSignal, QPointF
from PyQt6.QtGui import (
    QPainter, QColor, QFont, QPen, QBrush, QLinearGradient, QPainterPath,
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QSizePolicy, QProgressBar,
)

from core.tasks import DatabaseManager


# ---------------------------------------------------------------------------
# Visual Palette (Catppuccin / Modern Dark)
# ---------------------------------------------------------------------------
COLOR_BG_CARD   = "#1e1e2e"
COLOR_BORDER    = "#313244"
COLOR_TEXT_MAIN = "#cdd6f4"
COLOR_TEXT_MUTED= "#a6adc8"
COLOR_TEXT_SUB  = "#6c7086"

COLOR_COMPLETED = "#a6e3a1"  # Mint green
COLOR_ACTIVE    = "#89b4fa"  # Soft sky blue
COLOR_OVERDUE   = "#f38ba8"  # Coral red
COLOR_ACCENT    = "#cba6f7"  # Soft lavender / purple
COLOR_AMBER     = "#f9e2af"  # Warm gold


# ===========================================================================
# KPI Stat Card
# ===========================================================================
class KpiCard(QFrame):
    """Sleek KPI summary card with icon, large number and subtitle."""

    def __init__(
        self,
        icon: str,
        title: str,
        value: str,
        subtitle: str,
        accent_color: str,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._accent = accent_color
        self.setObjectName("KpiCard")
        self.setStyleSheet(f"""
            #KpiCard {{
                background-color: {COLOR_BG_CARD};
                border: 1px solid {COLOR_BORDER};
                border-radius: 12px;
                padding: 12px;
            }}
            #KpiCard:hover {{
                border: 1px solid {accent_color};
            }}
        """)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        # Top row: icon + title
        top_row = QHBoxLayout()
        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet(f"font-size: 18px; color: {accent_color};")
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {COLOR_TEXT_MUTED};")
        top_row.addWidget(icon_lbl)
        top_row.addWidget(title_lbl)
        top_row.addStretch()
        layout.addLayout(top_row)

        # Value
        self._val_label = QLabel(value)
        self._val_label.setStyleSheet(f"font-size: 28px; font-weight: 800; color: {accent_color};")
        layout.addWidget(self._val_label)

        # Subtitle / note
        self._sub_label = QLabel(subtitle)
        self._sub_label.setStyleSheet(f"font-size: 11px; color: {COLOR_TEXT_SUB};")
        layout.addWidget(self._sub_label)

    def update_value(self, value: str, subtitle: Optional[str] = None) -> None:
        self._val_label.setText(value)
        if subtitle is not None:
            self._sub_label.setText(subtitle)


# ===========================================================================
# Vector Donut Chart Widget
# ===========================================================================
class DonutChartWidget(QWidget):
    """
    Renders an antialiased circular donut/ring chart with center percentage readout
    and colored segments for Completed, Active, and Overdue tasks.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumSize(220, 220)
        self._completed = 0
        self._active    = 0
        self._overdue   = 0

    def set_data(self, completed: int, active: int, overdue: int) -> None:
        self._completed = max(0, completed)
        self._active    = max(0, active)
        self._overdue   = max(0, overdue)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()
        size = min(width, height) - 24
        if size <= 10:
            return

        cx = width / 2.0
        cy = height / 2.0
        r_outer = size / 2.0
        r_inner = r_outer * 0.68  # donut hole

        rect = QRectF(cx - r_outer, cy - r_outer, r_outer * 2, r_outer * 2)

        total = self._completed + self._active + self._overdue
        start_angle = 90.0 * 16.0  # 12 o'clock in 1/16th degrees

        if total == 0:
            # Draw empty subtle ring
            pen = QPen(QColor(COLOR_BORDER), r_outer - r_inner)
            pen.setCapStyle(Qt.PenCapStyle.FlatCap)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            mid_r = (r_outer + r_inner) / 2.0
            painter.drawEllipse(QPointF(cx, cy), mid_r, mid_r)
        else:
            slices = [
                (self._completed, QColor(COLOR_COMPLETED)),
                (self._active,    QColor(COLOR_ACTIVE)),
                (self._overdue,   QColor(COLOR_OVERDUE)),
            ]
            current_angle = start_angle
            for count, color in slices:
                if count <= 0:
                    continue
                span_angle = - (count / total) * 360.0 * 16.0

                path = QPainterPath()
                path.arcMoveTo(rect, current_angle / 16.0)
                path.arcTo(rect, current_angle / 16.0, span_angle / 16.0)

                # Inner arc (reverse)
                inner_rect = QRectF(cx - r_inner, cy - r_inner, r_inner * 2, r_inner * 2)
                path.arcTo(inner_rect, (current_angle + span_angle) / 16.0, -span_angle / 16.0)
                path.closeSubpath()

                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(color))
                painter.drawPath(path)

                current_angle += span_angle

        # Draw Center Hole Background
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(COLOR_BG_CARD)))
        painter.drawEllipse(QPointF(cx, cy), r_inner - 1, r_inner - 1)

        # Center Text (Percentage + Label)
        rate = round((self._completed / total * 100)) if total > 0 else 0
        painter.setPen(QColor(COLOR_TEXT_MAIN))
        f_val = QFont("Segoe UI", 18, QFont.Weight.Bold)
        painter.setFont(f_val)
        val_text = f"{rate}%"
        painter.drawText(
            QRectF(cx - r_inner, cy - 20, r_inner * 2, 26),
            Qt.AlignmentFlag.AlignCenter,
            val_text,
        )

        f_sub = QFont("Segoe UI", 9, QFont.Weight.Normal)
        painter.setFont(f_sub)
        painter.setPen(QColor(COLOR_TEXT_MUTED))
        painter.drawText(
            QRectF(cx - r_inner, cy + 6, r_inner * 2, 18),
            Qt.AlignmentFlag.AlignCenter,
            "Completado",
        )

        painter.end()


# ===========================================================================
# Vector Weekly Activity Bar Chart
# ===========================================================================
class WeeklyBarChartWidget(QWidget):
    """
    Renders an interactive vertical bar chart showing completed tasks
    over the last 7 days with custom vector styling.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumSize(320, 220)
        self._data: List[Dict[str, Any]] = []

    def set_data(self, weekly_data: List[Dict[str, Any]]) -> None:
        self._data = list(weekly_data)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()

        padding_left = 30
        padding_right = 20
        padding_top = 26
        padding_bottom = 34

        chart_w = width - padding_left - padding_right
        chart_h = height - padding_top - padding_bottom

        if chart_w <= 20 or chart_h <= 20 or not self._data:
            painter.end()
            return

        max_val = max([d.get("completed", 0) for d in self._data] + [4])

        # Draw horizontal grid lines
        grid_lines = 4
        painter.setPen(QPen(QColor(COLOR_BORDER), 1, Qt.PenStyle.DashLine))
        f_grid = QFont("Segoe UI", 8)
        painter.setFont(f_grid)

        for i in range(grid_lines + 1):
            y_val = int(max_val * i / grid_lines)
            y = padding_top + chart_h - (chart_h * (i / grid_lines))
            painter.drawLine(int(padding_left), int(y), int(width - padding_right), int(y))
            painter.setPen(QColor(COLOR_TEXT_SUB))
            painter.drawText(0, int(y + 4), padding_left - 6, 12, Qt.AlignmentFlag.AlignRight, str(y_val))
            painter.setPen(QPen(QColor(COLOR_BORDER), 1, Qt.PenStyle.DashLine))

        # Draw bars
        n = len(self._data)
        slot_w = chart_w / n
        bar_w = min(36.0, slot_w * 0.6)

        f_label = QFont("Segoe UI", 9, QFont.Weight.DemiBold)
        f_val = QFont("Segoe UI", 9, QFont.Weight.Bold)

        for idx, item in enumerate(self._data):
            val = item.get("completed", 0)
            is_today = item.get("is_today", False)
            bar_h = (val / max_val) * chart_h if max_val > 0 else 0

            cx = padding_left + (idx * slot_w) + (slot_w / 2.0)
            bx = cx - (bar_w / 2.0)
            by = padding_top + chart_h - bar_h

            # Bar path with rounded top corners
            bar_rect = QRectF(bx, by, bar_w, max(bar_h, 3.0))
            path = QPainterPath()
            path.addRoundedRect(bar_rect, 5.0, 5.0)

            # Gradient fill
            grad = QLinearGradient(bx, by, bx, by + bar_h)
            if is_today:
                grad.setColorAt(0.0, QColor("#d0b4fa"))
                grad.setColorAt(1.0, QColor("#7c3aed"))
            else:
                grad.setColorAt(0.0, QColor("#99c6f9"))
                grad.setColorAt(1.0, QColor("#3b82f6"))

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(grad))
            painter.drawPath(path)

            # Value above bar
            painter.setFont(f_val)
            painter.setPen(QColor(COLOR_ACCENT if is_today else COLOR_TEXT_MAIN))
            painter.drawText(
                QRectF(cx - 20, by - 18, 40, 16),
                Qt.AlignmentFlag.AlignCenter,
                str(val),
            )

            # Day label below bar
            painter.setFont(f_label)
            painter.setPen(QColor(COLOR_ACCENT if is_today else COLOR_TEXT_MUTED))
            day_text = item.get("day_name", item.get("label", ""))
            if is_today:
                day_text += " •"
            painter.drawText(
                QRectF(cx - 25, padding_top + chart_h + 8, 50, 18),
                Qt.AlignmentFlag.AlignCenter,
                day_text,
            )

        painter.end()


# ===========================================================================
# Category Progress Bar Row
# ===========================================================================
class CategoryBarRow(QWidget):
    """Row displaying category name, color dot, count and sleek progress bar."""

    def __init__(self, cat_data: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(4)

        # Header: Dot + Name + (done/total)
        hdr = QHBoxLayout()
        hdr.setSpacing(8)

        dot = QLabel("●")
        dot.setStyleSheet(f"font-size: 13px; color: {cat_data.get('color', '#7c3aed')};")
        name_lbl = QLabel(cat_data.get("name", "Sin categoría"))
        name_lbl.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {COLOR_TEXT_MAIN};")

        done = cat_data.get("completed", 0)
        tot = cat_data.get("total", 0)
        rate = cat_data.get("rate", 0.0)

        stat_lbl = QLabel(f"{done}/{tot} ({rate}%)")
        stat_lbl.setStyleSheet(f"font-size: 11px; color: {COLOR_TEXT_SUB};")

        hdr.addWidget(dot)
        hdr.addWidget(name_lbl)
        hdr.addStretch()
        hdr.addWidget(stat_lbl)
        layout.addLayout(hdr)

        # Progress bar
        pbar = QProgressBar()
        pbar.setFixedHeight(8)
        pbar.setTextVisible(False)
        pbar.setRange(0, 100)
        pbar.setValue(int(rate))
        color = cat_data.get("color", "#7c3aed")
        pbar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {COLOR_BORDER};
                border: none;
                border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 4px;
            }}
        """)
        layout.addWidget(pbar)


# ===========================================================================
# Main Dashboard Widget
# ===========================================================================
class DashboardWidget(QWidget):
    """
    Main statistical and analytical dashboard widget.
    Integrates KPI cards, vector charts, categories, and priority metrics.
    """

    refresh_requested = pyqtSignal()

    def __init__(self, db: DatabaseManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._db = db
        self._build_ui()
        self.refresh_data()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Scroll Area for responsive display
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"QScrollArea {{ background-color: #11111b; border: none; }}")

        container = QWidget()
        container.setObjectName("DashboardContainer")
        container.setStyleSheet(f"#DashboardContainer {{ background-color: #11111b; }}")
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(20, 16, 20, 24)
        main_layout.setSpacing(16)

        # --------------------------------------------------------------
        # 1. Header Bar: Title, subtitle and Refresh button
        # --------------------------------------------------------------
        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        titles_box = QVBoxLayout()
        titles_box.setSpacing(2)
        title_lbl = QLabel("📊 Panel de Rendimiento y Estadísticas")
        title_lbl.setStyleSheet(f"font-size: 20px; font-weight: 800; color: {COLOR_TEXT_MAIN};")
        sub_lbl = QLabel("Métricas en tiempo real, análisis de productividad y distribución de tareas.")
        sub_lbl.setStyleSheet(f"font-size: 12px; color: {COLOR_TEXT_SUB};")
        titles_box.addWidget(title_lbl)
        titles_box.addWidget(sub_lbl)
        header_row.addLayout(titles_box)
        header_row.addStretch()

        self._refresh_btn = QPushButton("🔄 Actualizar")
        self._refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_BG_CARD};
                color: {COLOR_TEXT_MAIN};
                border: 1px solid {COLOR_BORDER};
                border-radius: 8px;
                padding: 6px 16px;
                font-weight: 600;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {COLOR_BORDER};
                border-color: {COLOR_ACCENT};
            }}
        """)
        self._refresh_btn.clicked.connect(self.refresh_data)
        header_row.addWidget(self._refresh_btn)
        main_layout.addLayout(header_row)

        # --------------------------------------------------------------
        # 2. KPI Cards Grid (4 metrics)
        # --------------------------------------------------------------
        kpi_grid = QGridLayout()
        kpi_grid.setSpacing(12)

        self._card_total = KpiCard(
            icon="📋",
            title="TOTAL DE TAREAS",
            value="0",
            subtitle="Registradas en el sistema",
            accent_color=COLOR_ACTIVE,
        )
        self._card_active = KpiCard(
            icon="⏳",
            title="TAREAS ACTIVAS",
            value="0",
            subtitle="Pendientes por realizar",
            accent_color=COLOR_AMBER,
        )
        self._card_completed = KpiCard(
            icon="✅",
            title="COMPLETADAS",
            value="0",
            subtitle="0% tasa de cumplimiento",
            accent_color=COLOR_COMPLETED,
        )
        self._card_overdue = KpiCard(
            icon="⚠️",
            title="VENCIDAS",
            value="0",
            subtitle="Requieren atención inmediata",
            accent_color=COLOR_OVERDUE,
        )

        kpi_grid.addWidget(self._card_total, 0, 0)
        kpi_grid.addWidget(self._card_active, 0, 1)
        kpi_grid.addWidget(self._card_completed, 0, 2)
        kpi_grid.addWidget(self._card_overdue, 0, 3)
        main_layout.addLayout(kpi_grid)

        # --------------------------------------------------------------
        # 3. Middle Section: Donut Chart + Weekly Activity Chart
        # --------------------------------------------------------------
        charts_row = QHBoxLayout()
        charts_row.setSpacing(14)

        # Donut Chart Box
        donut_frame = QFrame()
        donut_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLOR_BG_CARD};
                border: 1px solid {COLOR_BORDER};
                border-radius: 12px;
            }}
        """)
        donut_layout = QVBoxLayout(donut_frame)
        donut_layout.setContentsMargins(16, 14, 16, 14)
        donut_layout.setSpacing(8)

        donut_title = QLabel("🎯 Estado Global de Cumplimiento")
        donut_title.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {COLOR_TEXT_MAIN};")
        donut_layout.addWidget(donut_title)

        self._donut_chart = DonutChartWidget()
        donut_layout.addWidget(self._donut_chart, 1)

        # Legend under donut
        legend_layout = QHBoxLayout()
        legend_layout.setSpacing(12)

        self._leg_comp = QLabel("● Completadas: 0")
        self._leg_comp.setStyleSheet(f"font-size: 11px; color: {COLOR_COMPLETED}; font-weight: 600;")
        self._leg_act = QLabel("● Activas: 0")
        self._leg_act.setStyleSheet(f"font-size: 11px; color: {COLOR_ACTIVE}; font-weight: 600;")
        self._leg_over = QLabel("● Vencidas: 0")
        self._leg_over.setStyleSheet(f"font-size: 11px; color: {COLOR_OVERDUE}; font-weight: 600;")

        legend_layout.addStretch()
        legend_layout.addWidget(self._leg_comp)
        legend_layout.addWidget(self._leg_act)
        legend_layout.addWidget(self._leg_over)
        legend_layout.addStretch()
        donut_layout.addLayout(legend_layout)

        charts_row.addWidget(donut_frame, 4)

        # Weekly Activity Chart Box
        bar_frame = QFrame()
        bar_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLOR_BG_CARD};
                border: 1px solid {COLOR_BORDER};
                border-radius: 12px;
            }}
        """)
        bar_layout = QVBoxLayout(bar_frame)
        bar_layout.setContentsMargins(16, 14, 16, 14)
        bar_layout.setSpacing(8)

        bar_title = QLabel("📈 Productividad Últimos 7 Días (Completadas)")
        bar_title.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {COLOR_TEXT_MAIN};")
        bar_layout.addWidget(bar_title)

        self._bar_chart = WeeklyBarChartWidget()
        bar_layout.addWidget(self._bar_chart, 1)

        charts_row.addWidget(bar_frame, 6)
        main_layout.addLayout(charts_row)

        # --------------------------------------------------------------
        # 4. Bottom Section: Categories Breakdown & Priority Gauges
        # --------------------------------------------------------------
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(14)

        # Categories Breakdown Panel
        cat_frame = QFrame()
        cat_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLOR_BG_CARD};
                border: 1px solid {COLOR_BORDER};
                border-radius: 12px;
            }}
        """)
        self._cat_container_layout = QVBoxLayout(cat_frame)
        self._cat_container_layout.setContentsMargins(16, 14, 16, 14)
        self._cat_container_layout.setSpacing(8)

        cat_hdr = QLabel("🏷 Progreso por Categorías")
        cat_hdr.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {COLOR_TEXT_MAIN};")
        self._cat_container_layout.addWidget(cat_hdr)

        self._cat_rows_layout = QVBoxLayout()
        self._cat_rows_layout.setSpacing(6)
        self._cat_container_layout.addLayout(self._cat_rows_layout)
        self._cat_container_layout.addStretch()

        bottom_row.addWidget(cat_frame, 6)

        # Priority Breakdown Panel
        prio_frame = QFrame()
        prio_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLOR_BG_CARD};
                border: 1px solid {COLOR_BORDER};
                border-radius: 12px;
            }}
        """)
        prio_layout = QVBoxLayout(prio_frame)
        prio_layout.setContentsMargins(16, 14, 16, 14)
        prio_layout.setSpacing(12)

        prio_hdr = QLabel("⚡ Tareas por Prioridad")
        prio_hdr.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {COLOR_TEXT_MAIN};")
        prio_layout.addWidget(prio_hdr)

        self._prio_high_lbl = QLabel("Alta (0)")
        self._prio_high_bar = QProgressBar()
        self._setup_prio_bar(self._prio_high_bar, "#dc2626")
        prio_layout.addWidget(self._prio_high_lbl)
        prio_layout.addWidget(self._prio_high_bar)

        self._prio_med_lbl = QLabel("Media (0)")
        self._prio_med_bar = QProgressBar()
        self._setup_prio_bar(self._prio_med_bar, "#d97706")
        prio_layout.addWidget(self._prio_med_lbl)
        prio_layout.addWidget(self._prio_med_bar)

        self._prio_low_lbl = QLabel("Baja (0)")
        self._prio_low_bar = QProgressBar()
        self._setup_prio_bar(self._prio_low_bar, "#6b7280")
        prio_layout.addWidget(self._prio_low_lbl)
        prio_layout.addWidget(self._prio_low_bar)

        prio_layout.addStretch()
        bottom_row.addWidget(prio_frame, 4)

        main_layout.addLayout(bottom_row)

        scroll.setWidget(container)
        root.addWidget(scroll)

    def _setup_prio_bar(self, bar: QProgressBar, color: str) -> None:
        bar.setFixedHeight(8)
        bar.setTextVisible(False)
        bar.setRange(0, 100)
        bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {COLOR_BORDER};
                border: none;
                border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 4px;
            }}
        """)

    # ------------------------------------------------------------------
    # Data Refresh
    # ------------------------------------------------------------------
    def refresh_data(self) -> None:
        """Fetch latest database stats and refresh all visual components."""
        data = self._db.get_dashboard_data()
        summary = data.get("summary", {})
        categories = data.get("categories", [])
        priorities = data.get("priorities", [])
        weekly = data.get("weekly_activity", [])

        # 1. Update KPI Cards
        total = summary.get("total", 0)
        active = summary.get("active", 0)
        completed = summary.get("completed", 0)
        overdue = summary.get("overdue", 0)
        rate = summary.get("completion_rate", 0.0)

        self._card_total.update_value(str(total), f"{active} activas, {completed} hechas")
        self._card_active.update_value(str(active), f"{summary.get('due_today', 0)} para hoy")
        self._card_completed.update_value(str(completed), f"{rate}% tasa de éxito")
        self._card_overdue.update_value(str(overdue), "Al día" if overdue == 0 else "Requieren revisión")

        # 2. Update Donut Chart & Legend
        self._donut_chart.set_data(completed, active, overdue)
        self._leg_comp.setText(f"● Hechas: {completed}")
        self._leg_act.setText(f"● Activas: {active}")
        self._leg_over.setText(f"● Vencidas: {overdue}")

        # 3. Update Weekly Bar Chart
        self._bar_chart.set_data(weekly)

        # 4. Update Categories
        while self._cat_rows_layout.count():
            item = self._cat_rows_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not categories:
            no_cat = QLabel("No hay categorías configuradas.")
            no_cat.setStyleSheet(f"color: {COLOR_TEXT_SUB}; font-size: 11px;")
            self._cat_rows_layout.addWidget(no_cat)
        else:
            for cat in categories:
                row = CategoryBarRow(cat)
                self._cat_rows_layout.addWidget(row)

        # 5. Update Priorities
        prio_totals = {p["priority"]: p["total"] for p in priorities}
        p_tot = sum(prio_totals.values()) or 1

        high = prio_totals.get(3, 0)
        med = prio_totals.get(2, 0)
        low = prio_totals.get(1, 0)

        self._prio_high_lbl.setText(f"Alta ({high} tareas)")
        self._prio_high_bar.setValue(int(high / p_tot * 100))

        self._prio_med_lbl.setText(f"Media ({med} tareas)")
        self._prio_med_bar.setValue(int(med / p_tot * 100))

        self._prio_low_lbl.setText(f"Baja ({low} tareas)")
        self._prio_low_bar.setValue(int(low / p_tot * 100))
