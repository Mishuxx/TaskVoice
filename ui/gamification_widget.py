"""
ui/gamification_widget.py
=========================
Gamification and Mission Hub for TaskVoice.
Styling and theme inspired by StarCraft II Terran/Protoss Command Console
and Path of Exile dark fantasy / exalted mechanics.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal, QSize, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter, QLinearGradient, QBrush, QPen
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QScrollArea, QFrame, QGridLayout, QMessageBox,
    QSizePolicy,
)

from core.tasks import DatabaseManager, RANKS, get_rank_info, get_xp_needed_for_level

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Level Up Dialog
# ---------------------------------------------------------------------------

class LevelUpDialog(QMessageBox):
    """Celebratory modal dialog shown when the user advances in rank."""

    def __init__(self, level: int, rank_title: str, rank_icon: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚡ ASCENSIÓN DE RANGO – LEVEL UP ⚡")
        self.setIcon(QMessageBox.Icon.Information)
        self.setText(
            f"<h2 style='color:#00f0ff; margin-bottom:4px;'>¡NIVEL {level} ALCANZADO!</h2>"
            f"<h3 style='color:#ffd166; margin-top:0px;'>{rank_icon} {rank_title}</h3>"
            f"<p style='color:#cdd6f4; font-size:13px;'>"
            f"Tus capacidades estratégicas han sido reconocidas por el alto mando.<br>"
            f"¡Continúa neutralizando tareas y misiones para ascender en la jerarquía!"
            f"</p>"
        )
        self.setStandardButtons(QMessageBox.StandardButton.Ok)
        ok_btn = self.button(QMessageBox.StandardButton.Ok)
        if ok_btn:
            ok_btn.setText("⚔️ ¡A la carga!")
            ok_btn.setStyleSheet(
                "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d97706, stop:1 #f59e0b); "
                "color: #090b10; font-weight: bold; border-radius: 6px; padding: 6px 20px; font-size: 13px;"
            )
        self.setStyleSheet(
            "QMessageBox { background: #0c1017; border: 2px solid #00f0ff; } "
            "QLabel { color: #cdd6f4; font-size: 13px; }"
        )


# ---------------------------------------------------------------------------
# Mission / Quest Card
# ---------------------------------------------------------------------------

class QuestCard(QFrame):
    """Card representing a single tactical daily operation/quest."""

    claim_clicked = pyqtSignal(int)

    def __init__(self, quest: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.quest = quest
        self._build_ui()

    def _build_ui(self) -> None:
        self.setObjectName("QuestCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)

        is_completed = bool(self.quest["completed"])
        is_claimed = bool(self.quest["claimed"])

        # Border color depending on state
        if is_claimed:
            border_color = "#10b981"  # Emerald
            bg_color = "#0e1814"
        elif is_completed:
            border_color = "#f59e0b"  # Glowing Amber
            bg_color = "#18140c"
        else:
            border_color = "#1f2d42"  # Metallic dark blue
            bg_color = "#101520"

        self.setStyleSheet(
            f"#QuestCard {{"
            f"  background: {bg_color};"
            f"  border: 1px solid {border_color};"
            f"  border-radius: 8px;"
            f"  margin: 3px 0;"
            f"}}"
            f"#QuestCard:hover {{ border-color: #00f0ff; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        # Top line: Faction tag + Reward badge
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        faction_lbl = QLabel(f"[{self.quest.get('faction', 'Comando Terran').upper()}]")
        faction_lbl.setStyleSheet(
            "font-size: 10px; font-weight: 700; color: #00e5ff; letter-spacing: 1px;"
        )
        top_row.addWidget(faction_lbl)
        top_row.addStretch()

        reward_badge = QLabel(f"⭐ +{self.quest['xp_reward']} XP")
        reward_badge.setStyleSheet(
            "background: #231908; color: #ffd166; font-size: 11px; font-weight: 700; "
            "border: 1px solid #d97706; border-radius: 4px; padding: 2px 8px;"
        )
        top_row.addWidget(reward_badge)
        layout.addLayout(top_row)

        # Title & Lore
        title_row = QHBoxLayout()
        title_row.setSpacing(6)

        icon_lbl = QLabel(self.quest.get("icon", "🎯"))
        icon_lbl.setStyleSheet("font-size: 16px;")
        title_row.addWidget(icon_lbl)

        title_lbl = QLabel(self.quest["title"])
        title_lbl.setStyleSheet("font-size: 14px; font-weight: 700; color: #e2e8f0;")
        title_row.addWidget(title_lbl, 1)
        layout.addLayout(title_row)

        desc_lbl = QLabel(self.quest["description"])
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("font-size: 12px; color: #94a3b8; font-style: italic;")
        layout.addWidget(desc_lbl)

        # Progress bar
        cur_count = min(self.quest["current_count"], self.quest["target_count"])
        target_count = self.quest["target_count"]
        pct = int((cur_count / target_count) * 100) if target_count > 0 else 100

        prog_row = QHBoxLayout()
        prog_bar = QProgressBar()
        prog_bar.setRange(0, 100)
        prog_bar.setValue(pct)
        prog_bar.setFixedHeight(8)
        prog_bar.setTextVisible(False)
        prog_bar.setStyleSheet(
            "QProgressBar { background: #1a2233; border: 1px solid #2a3b5c; border-radius: 4px; }"
            "QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0077b6, stop:1 #00f0ff); border-radius: 3px; }"
        )
        prog_row.addWidget(prog_bar, 1)

        prog_txt = QLabel(f"{cur_count} / {target_count}")
        prog_txt.setStyleSheet("font-size: 11px; font-weight: 700; color: #cbd5e1; min-width: 45px;")
        prog_txt.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        prog_row.addWidget(prog_txt)
        layout.addLayout(prog_row)

        # Action button or status badge
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        if is_claimed:
            done_lbl = QLabel("✔ Recompensa Reclamada")
            done_lbl.setStyleSheet("color: #10b981; font-weight: 600; font-size: 12px;")
            btn_row.addWidget(done_lbl)
        elif is_completed:
            claim_btn = QPushButton("⚡ RECLAMAR RECOMPENSA")
            claim_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            claim_btn.setStyleSheet(
                "QPushButton { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d97706, stop:1 #f59e0b); "
                "  color: #090b10; font-weight: 800; border-radius: 6px; padding: 6px 16px; font-size: 11px; "
                "  border: 1px solid #fef08a; }"
                "QPushButton:hover { background: #fef08a; color: #000; }"
            )
            claim_btn.clicked.connect(lambda: self.claim_clicked.emit(self.quest["id"]))
            btn_row.addWidget(claim_btn)
        else:
            in_prog = QLabel("En progreso…")
            in_prog.setStyleSheet("color: #64748b; font-size: 11px; font-weight: 500;")
            btn_row.addWidget(in_prog)

        layout.addLayout(btn_row)


# ---------------------------------------------------------------------------
# Main Gamification Hub Widget
# ---------------------------------------------------------------------------

class GamificationWidget(QWidget):
    """
    Full-featured RPG / Gamification Hub dashboard view.
    """

    profile_updated = pyqtSignal()

    def __init__(self, db: DatabaseManager, parent=None):
        super().__init__(parent)
        self._db = db
        self._build_ui()
        self.refresh_data()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 16, 18, 16)
        main_layout.setSpacing(14)

        # ------------------------------------------------------------------
        # Header: Title & Refresh button
        # ------------------------------------------------------------------
        header_row = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        title_lbl = QLabel("⚔️ CENTRO DE COMANDO & OPERACIONES")
        title_lbl.setStyleSheet(
            "font-size: 20px; font-weight: 800; color: #00f0ff; letter-spacing: 1px;"
        )
        title_box.addWidget(title_lbl)

        sub_lbl = QLabel("Gamificación táctica • Experiencia • Rangos de Honor • Misiones Diarias")
        sub_lbl.setStyleSheet("font-size: 12px; color: #64748b;")
        title_box.addWidget(sub_lbl)
        header_row.addLayout(title_box)

        header_row.addStretch()

        self._refresh_btn = QPushButton("🔄 Actualizar")
        self._refresh_btn.setStyleSheet(
            "QPushButton { background: #1a2233; color: #00f0ff; border: 1px solid #2a3b5c; border-radius: 6px; padding: 6px 14px; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background: #223147; border-color: #00f0ff; }"
        )
        self._refresh_btn.clicked.connect(self.refresh_data)
        header_row.addWidget(self._refresh_btn)
        main_layout.addLayout(header_row)

        # Scroll area for the rest
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(14)

        # ------------------------------------------------------------------
        # 1. Commander HUD Hero Card
        # ------------------------------------------------------------------
        self._hero_card = QFrame()
        self._hero_card.setObjectName("HeroCard")
        self._hero_card.setStyleSheet(
            "#HeroCard {"
            "  background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #101524, stop:1 #0c0e17);"
            "  border: 1px solid #1f2d42;"
            "  border-radius: 10px;"
            "  padding: 16px;"
            "}"
            "#HeroCard:hover { border-color: #00f0ff; }"
        )
        hero_layout = QVBoxLayout(self._hero_card)
        hero_layout.setSpacing(12)

        top_hero = QHBoxLayout()
        top_hero.setSpacing(14)

        # Avatar / Crest Frame
        self._crest_lbl = QLabel("⚔️")
        self._crest_lbl.setFixedSize(54, 54)
        self._crest_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._crest_lbl.setStyleSheet(
            "background: #141b2b; border: 2px solid #00f0ff; border-radius: 10px; font-size: 26px;"
        )
        top_hero.addWidget(self._crest_lbl)

        # Name and Title
        name_col = QVBoxLayout()
        name_col.setSpacing(2)

        self._lvl_badge = QLabel("NIVEL 1")
        self._lvl_badge.setStyleSheet(
            "font-size: 11px; font-weight: 800; color: #ffd166; background: #261a08; "
            "border: 1px solid #d97706; border-radius: 4px; padding: 1px 6px; max-width: 75px;"
        )
        name_col.addWidget(self._lvl_badge)

        self._rank_title_lbl = QLabel("Recluta Terran")
        self._rank_title_lbl.setStyleSheet("font-size: 18px; font-weight: 800; color: #f8fafc;")
        name_col.addWidget(self._rank_title_lbl)

        self._rank_desc_lbl = QLabel("Primeros pasos en la línea de frente.")
        self._rank_desc_lbl.setStyleSheet("font-size: 12px; color: #94a3b8;")
        name_col.addWidget(self._rank_desc_lbl)

        top_hero.addLayout(name_col, 1)

        # Streak pill
        self._streak_pill = QLabel("🔥 Racha: 1 Día")
        self._streak_pill.setStyleSheet(
            "background: #2a1114; color: #ff6b6b; font-size: 12px; font-weight: 700; "
            "border: 1px solid #ff3344; border-radius: 6px; padding: 6px 12px;"
        )
        top_hero.addWidget(self._streak_pill)

        hero_layout.addLayout(top_hero)

        # XP Progress Bar with cybernetic styling
        xp_box = QVBoxLayout()
        xp_box.setSpacing(4)

        xp_header = QHBoxLayout()
        xp_title = QLabel("EXPERIENCIA MILITAR (XP)")
        xp_title.setStyleSheet("font-size: 11px; font-weight: 700; color: #00f0ff; letter-spacing: 1px;")
        xp_header.addWidget(xp_title)
        xp_header.addStretch()

        self._xp_numbers_lbl = QLabel("0 / 150 XP (0%)")
        self._xp_numbers_lbl.setStyleSheet("font-size: 12px; font-weight: 700; color: #ffd166;")
        xp_header.addWidget(self._xp_numbers_lbl)
        xp_box.addLayout(xp_header)

        self._xp_bar = QProgressBar()
        self._xp_bar.setRange(0, 100)
        self._xp_bar.setValue(0)
        self._xp_bar.setFixedHeight(12)
        self._xp_bar.setTextVisible(False)
        self._xp_bar.setStyleSheet(
            "QProgressBar {"
            "  background: #141b29;"
            "  border: 1px solid #1f2d42;"
            "  border-radius: 6px;"
            "}"
            "QProgressBar::chunk {"
            "  background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:0.7 #00f0ff, stop:1 #ffd166);"
            "  border-radius: 5px;"
            "}"
        )
        xp_box.addWidget(self._xp_bar)

        self._next_rank_hint = QLabel("Próximo ascenso a Soldado Marine al subir de nivel.")
        self._next_rank_hint.setStyleSheet("font-size: 11px; color: #64748b; font-style: italic;")
        xp_box.addWidget(self._next_rank_hint)

        hero_layout.addLayout(xp_box)

        # Stats grid
        stats_grid = QGridLayout()
        stats_grid.setSpacing(8)

        self._stat_tasks = self._create_stat_badge("⚔️ Tareas Completadas", "0")
        self._stat_subtasks = self._create_stat_badge("🧩 Subtareas", "0")
        self._stat_voice = self._create_stat_badge("🎙️ Órdenes de Voz", "0")
        self._stat_total_xp = self._create_stat_badge("🏆 XP Total Acumulado", "0 XP")

        stats_grid.addWidget(self._stat_tasks[0], 0, 0)
        stats_grid.addWidget(self._stat_subtasks[0], 0, 1)
        stats_grid.addWidget(self._stat_voice[0], 0, 2)
        stats_grid.addWidget(self._stat_total_xp[0], 0, 3)

        hero_layout.addLayout(stats_grid)
        self._content_layout.addWidget(self._hero_card)

        # ------------------------------------------------------------------
        # 2. Daily Operations & Quests Section
        # ------------------------------------------------------------------
        quests_header = QHBoxLayout()
        q_title = QLabel("🎯 OPERACIONES TÁCTICAS DEL DÍA")
        q_title.setStyleSheet("font-size: 15px; font-weight: 800; color: #ffd166; letter-spacing: 1px;")
        quests_header.addWidget(q_title)
        quests_header.addStretch()

        self._quests_counter_lbl = QLabel("0/5 Completadas")
        self._quests_counter_lbl.setStyleSheet("font-size: 12px; color: #94a3b8; font-weight: 600;")
        quests_header.addWidget(self._quests_counter_lbl)
        self._content_layout.addLayout(quests_header)

        self._quests_container = QVBoxLayout()
        self._quests_container.setSpacing(6)
        self._content_layout.addLayout(self._quests_container)

        # ------------------------------------------------------------------
        # 3. Ranks Overview Section (Escalafón Militar)
        # ------------------------------------------------------------------
        ranks_header = QLabel("🌟 ESCALAFÓN DE HONOR & ASCENSIÓN")
        ranks_header.setStyleSheet("font-size: 15px; font-weight: 800; color: #00f0ff; letter-spacing: 1px; margin-top: 10px;")
        self._content_layout.addWidget(ranks_header)

        self._ranks_container = QVBoxLayout()
        self._ranks_container.setSpacing(4)
        self._content_layout.addLayout(self._ranks_container)

        self._content_layout.addStretch()

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    def _create_stat_badge(self, label: str, val: str) -> tuple[QFrame, QLabel]:
        card = QFrame()
        card.setStyleSheet(
            "background: #141b29; border: 1px solid #1f2d42; border-radius: 6px; padding: 6px 10px;"
        )
        l = QVBoxLayout(card)
        l.setContentsMargins(6, 4, 6, 4)
        l.setSpacing(2)

        lbl = QLabel(label)
        lbl.setStyleSheet("font-size: 10px; color: #64748b; font-weight: 600;")
        l.addWidget(lbl)

        v_lbl = QLabel(val)
        v_lbl.setStyleSheet("font-size: 13px; font-weight: 800; color: #e2e8f0;")
        l.addWidget(v_lbl)
        return card, v_lbl

    # ------------------------------------------------------------------
    # Data Population
    # ------------------------------------------------------------------

    def refresh_data(self) -> None:
        """Fetch latest gamification data from database and render."""
        profile = self._db.get_gamification_profile()
        quests = self._db.get_daily_quests()

        # Update Hero Card
        rank = profile["rank"]
        self._crest_lbl.setText(rank["icon"])
        self._lvl_badge.setText(f"NIVEL {profile['level']}")
        self._rank_title_lbl.setText(f"{rank['icon']} {rank['title']}")
        self._rank_desc_lbl.setText(rank["desc"])
        self._streak_pill.setText(f"🔥 Racha: {profile['streak_days']} Días")

        self._xp_bar.setValue(int(profile["xp_progress_pct"]))
        self._xp_numbers_lbl.setText(
            f"{profile['xp']} / {profile['xp_needed']} XP ({profile['xp_progress_pct']}%)"
        )
        if rank.get("next_level"):
            xp_remaining = max(0, profile["xp_needed"] - profile["xp"])
            self._next_rank_hint.setText(
                f"Faltan {xp_remaining} XP para ascender al rango de {rank['next_title']} (Nivel {rank['next_level']})."
            )
        else:
            self._next_rank_hint.setText("¡Has alcanzado el rango máximo supremo del universo!")

        # Update Stats
        self._stat_tasks[1].setText(str(profile["tasks_completed_count"]))
        self._stat_subtasks[1].setText(str(profile["subtasks_completed_count"]))
        self._stat_voice[1].setText(str(profile["voice_commands_count"]))
        self._stat_total_xp[1].setText(f"{profile['total_xp']} XP")

        # Update Quests
        while self._quests_container.count() > 0:
            item = self._quests_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        completed_count = sum(1 for q in quests if q["completed"])
        self._quests_counter_lbl.setText(f"{completed_count}/{len(quests)} Completadas")

        for q in quests:
            card = QuestCard(q)
            card.claim_clicked.connect(self._on_claim_quest)
            self._quests_container.addWidget(card)

        # Update Ranks list
        while self._ranks_container.count() > 0:
            item = self._ranks_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for lvl, title, icon, desc in RANKS:
            r_frame = QFrame()
            is_current = (lvl == profile["level"])
            is_unlocked = (lvl <= profile["level"])

            if is_current:
                bg = "#1b2538"
                border = "#00f0ff"
                status_txt = "★ RANGO ACTIVO"
                status_color = "#00f0ff"
            elif is_unlocked:
                bg = "#101622"
                border = "#1f2d42"
                status_txt = "✔ ALCANZADO"
                status_color = "#10b981"
            else:
                bg = "#0b0e14"
                border = "#161b26"
                status_txt = f"🔒 Nivel {lvl}"
                status_color = "#64748b"

            r_frame.setStyleSheet(
                f"background: {bg}; border: 1px solid {border}; border-radius: 6px; padding: 6px 12px;"
            )
            rl = QHBoxLayout(r_frame)
            rl.setContentsMargins(8, 4, 8, 4)
            rl.setSpacing(10)

            rl_icon = QLabel(icon)
            rl_icon.setStyleSheet("font-size: 16px;")
            rl.addWidget(rl_icon)

            rl_info = QVBoxLayout()
            rl_info.setSpacing(1)
            t_lbl = QLabel(f"Nivel {lvl}: {title}")
            t_lbl.setStyleSheet(
                f"font-size: 12px; font-weight: 700; color: {'#f8fafc' if is_unlocked else '#64748b'};"
            )
            rl_info.addWidget(t_lbl)

            d_lbl = QLabel(desc)
            d_lbl.setStyleSheet("font-size: 10px; color: #64748b;")
            rl_info.addWidget(d_lbl)
            rl.addLayout(rl_info, 1)

            st_lbl = QLabel(status_txt)
            st_lbl.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {status_color};")
            rl.addWidget(st_lbl)

            self._ranks_container.addWidget(r_frame)

    def _on_claim_quest(self, quest_id: int) -> None:
        """Handle claiming quest reward."""
        res = self._db.claim_quest(quest_id)
        if res.get("success"):
            xp_res = res.get("xp_res", {})
            self.refresh_data()
            self.profile_updated.emit()

            if xp_res.get("leveled_up"):
                dlg = LevelUpDialog(
                    level=xp_res["new_level"],
                    rank_title=xp_res["rank"]["title"],
                    rank_icon=xp_res["rank"]["icon"],
                    parent=self
                )
                dlg.exec()
            else:
                QMessageBox.information(
                    self,
                    "¡Recompensa Reclamada!",
                    f"⭐ Has reclamado +{res['quest']['xp_reward']} XP por completar: {res['quest']['title']}",
                )
        else:
            QMessageBox.warning(self, "Aviso", res.get("error", "No se pudo reclamar la misión."))
