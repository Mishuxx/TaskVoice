"""
ui/settings_dialog.py
=====================
Settings dialog with four tabs:
  General   – theme toggle, language placeholder
  Notificaciones – enable/disable, reminder time, daily summary time
  Voz       – engine selection, Vosk model path, push-to-talk toggle
  Categorías – list view with add/rename/delete and color picker
"""

from __future__ import annotations

from typing import List, Dict, Any, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QCheckBox, QComboBox, QSpinBox, QTimeEdit, QPushButton,
    QLineEdit, QListWidget, QListWidgetItem, QGroupBox, QFormLayout,
    QColorDialog, QFileDialog, QDialogButtonBox, QMessageBox, QFrame,
)
from PyQt6.QtCore import QTime


class SettingsDialog(QDialog):
    """
    Application settings dialog.

    Signals
    -------
    settings_saved(dict)
        Emitted with the full settings dict when the user clicks Save.
    """

    settings_saved = pyqtSignal(dict)

    def __init__(self, db, current_settings: Dict[str, Any], parent=None):
        super().__init__(parent)
        self._db = db
        self._settings = dict(current_settings)

        self.setWindowTitle("Ajustes – TaskVoice")
        self.setMinimumSize(560, 480)
        self.setModal(True)

        self._build_ui()
        self._load_values()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(
            "QTabWidget::pane { border: none; background: #1e1e2e; }"
            "QTabBar::tab { background: #313244; color: #cdd6f4; padding: 8px 18px; }"
            "QTabBar::tab:selected { background: #7c3aed; color: #fff; }"
        )

        self._general_tab       = self._build_general_tab()
        self._notif_tab         = self._build_notifications_tab()
        self._voice_tab         = self._build_voice_tab()
        self._categories_tab    = self._build_categories_tab()

        self._tabs.addTab(self._general_tab,    "⚙ General")
        self._tabs.addTab(self._notif_tab,      "🔔 Notificaciones")
        self._tabs.addTab(self._voice_tab,      "🎙 Voz")
        self._tabs.addTab(self._categories_tab, "🏷 Categorías")

        layout.addWidget(self._tabs)

        # Dialog buttons
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.setStyleSheet(
            "QDialogButtonBox { background: #1e1e2e; }"
            "QPushButton { background: #7c3aed; color: #fff; border-radius: 6px; padding: 6px 20px; }"
            "QPushButton:hover { background: #6d28d9; }"
            "QPushButton[text='Cancel'] { background: #45475a; }"
        )
        btn_box.accepted.connect(self._save)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    # ---- General tab ----

    def _build_general_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setContentsMargins(20, 20, 20, 20)
        form.setSpacing(14)

        self._theme_combo = QComboBox()
        self._theme_combo.addItems(["Oscuro", "Claro"])
        form.addRow("Tema:", self._theme_combo)

        self._lang_combo = QComboBox()
        self._lang_combo.addItems(["Español", "English"])
        form.addRow("Idioma:", self._lang_combo)

        return w

    # ---- Notifications tab ----

    def _build_notifications_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        self._notif_enabled_cb = QCheckBox("Habilitar notificaciones de escritorio")
        layout.addWidget(self._notif_enabled_cb)

        grp = QGroupBox("Recordatorios de tareas")
        grp.setStyleSheet("QGroupBox { color: #cdd6f4; }")
        grp_form = QFormLayout(grp)
        grp_form.setSpacing(10)

        self._reminder_spin = QSpinBox()
        self._reminder_spin.setRange(1, 120)
        self._reminder_spin.setSuffix(" min antes")
        grp_form.addRow("Avisar:", self._reminder_spin)

        layout.addWidget(grp)

        grp2 = QGroupBox("Resumen diario")
        grp2.setStyleSheet("QGroupBox { color: #cdd6f4; }")
        grp2_form = QFormLayout(grp2)
        grp2_form.setSpacing(10)

        self._summary_enabled_cb = QCheckBox("Enviar resumen diario")
        grp2_form.addRow(self._summary_enabled_cb)

        self._summary_time_edit = QTimeEdit()
        self._summary_time_edit.setDisplayFormat("HH:mm")
        grp2_form.addRow("Hora del resumen:", self._summary_time_edit)

        layout.addWidget(grp2)
        layout.addStretch()
        return w

    # ---- Voice tab ----

    def _build_voice_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        self._voice_enabled_cb = QCheckBox("Habilitar reconocimiento de voz")
        layout.addWidget(self._voice_enabled_cb)

        form = QFormLayout()
        form.setSpacing(10)

        self._engine_combo = QComboBox()
        self._engine_combo.addItems(["Google (online)", "Vosk (offline)"])
        form.addRow("Motor:", self._engine_combo)

        vosk_row = QHBoxLayout()
        self._vosk_path_edit = QLineEdit()
        self._vosk_path_edit.setPlaceholderText("Ruta al modelo Vosk…")
        vosk_row.addWidget(self._vosk_path_edit)
        browse_btn = QPushButton("…")
        browse_btn.setFixedWidth(32)
        browse_btn.clicked.connect(self._browse_vosk)
        vosk_row.addWidget(browse_btn)
        form.addRow("Modelo Vosk:", vosk_row)

        self._ptt_cb = QCheckBox("Push-to-talk (mantener botón pulsado)")
        form.addRow(self._ptt_cb)

        layout.addLayout(form)
        layout.addStretch()
        return w

    def _browse_vosk(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta del modelo Vosk")
        if path:
            self._vosk_path_edit.setText(path)

    # ---- Categories tab ----

    def _build_categories_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        self._cat_list = QListWidget()
        self._cat_list.setStyleSheet(
            "QListWidget { background: #313244; border-radius: 8px; }"
            "QListWidget::item { padding: 6px; border-radius: 4px; }"
            "QListWidget::item:selected { background: #7c3aed; }"
        )
        layout.addWidget(self._cat_list)

        btn_row = QHBoxLayout()
        add_btn    = QPushButton("➕ Añadir")
        rename_btn = QPushButton("✏ Renombrar")
        color_btn  = QPushButton("🎨 Color")
        del_btn    = QPushButton("🗑 Eliminar")

        for b in [add_btn, rename_btn, color_btn, del_btn]:
            b.setStyleSheet(
                "QPushButton { background: #313244; color: #cdd6f4; border-radius: 6px;"
                " padding: 5px 10px; } QPushButton:hover { background: #45475a; }"
            )
            btn_row.addWidget(b)

        add_btn.clicked.connect(self._add_category)
        rename_btn.clicked.connect(self._rename_category)
        color_btn.clicked.connect(self._change_color)
        del_btn.clicked.connect(self._delete_category)
        layout.addLayout(btn_row)

        self._refresh_categories()
        return w

    def _refresh_categories(self) -> None:
        self._cat_list.clear()
        for cat in self._db.get_categories():
            item = QListWidgetItem(cat["name"])
            item.setData(Qt.ItemDataRole.UserRole, cat)
            c = QColor(cat["color"])
            item.setForeground(c)
            self._cat_list.addItem(item)

    def _add_category(self) -> None:
        name, ok = self._input_dialog("Nueva Categoría", "Nombre:")
        if ok and name:
            self._db.add_category(name)
            self._refresh_categories()

    def _rename_category(self) -> None:
        item = self._cat_list.currentItem()
        if not item:
            return
        cat = item.data(Qt.ItemDataRole.UserRole)
        name, ok = self._input_dialog("Renombrar", "Nuevo nombre:", cat["name"])
        if ok and name:
            self._db.update_category(cat["id"], name, cat["color"])
            self._refresh_categories()

    def _change_color(self) -> None:
        item = self._cat_list.currentItem()
        if not item:
            return
        cat = item.data(Qt.ItemDataRole.UserRole)
        color = QColorDialog.getColor(QColor(cat["color"]), self, "Elegir Color")
        if color.isValid():
            self._db.update_category(cat["id"], cat["name"], color.name())
            self._refresh_categories()

    def _delete_category(self) -> None:
        item = self._cat_list.currentItem()
        if not item:
            return
        cat = item.data(Qt.ItemDataRole.UserRole)
        reply = QMessageBox.question(
            self, "Eliminar Categoría",
            f"¿Eliminar la categoría '{cat['name']}'?\n"
            "Las tareas asociadas quedarán sin categoría.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._db.delete_category(cat["id"])
            self._refresh_categories()

    # ------------------------------------------------------------------
    # Helper: lightweight input dialog
    # ------------------------------------------------------------------

    def _input_dialog(self, title: str, label: str, default: str = "") -> tuple[str, bool]:
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.setFixedWidth(320)
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel(label))
        edit = QLineEdit(default)
        layout.addWidget(edit)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        layout.addWidget(btns)
        ok = dlg.exec() == QDialog.DialogCode.Accepted
        return edit.text().strip(), ok

    # ------------------------------------------------------------------
    # Load / save values
    # ------------------------------------------------------------------

    def _load_values(self) -> None:
        s = self._settings

        # General
        self._theme_combo.setCurrentIndex(0 if s.get("theme", "dark") == "dark" else 1)

        # Notifications
        self._notif_enabled_cb.setChecked(s.get("notifications_enabled", True))
        self._reminder_spin.setValue(s.get("reminder_minutes", 30))
        self._summary_enabled_cb.setChecked(s.get("daily_summary_enabled", True))
        h = s.get("daily_summary_hour", 9)
        m = s.get("daily_summary_minute", 0)
        self._summary_time_edit.setTime(QTime(h, m))

        # Voice
        self._voice_enabled_cb.setChecked(s.get("voice_enabled", True))
        engine = s.get("voice_engine", "google")
        self._engine_combo.setCurrentIndex(0 if engine == "google" else 1)
        self._vosk_path_edit.setText(s.get("vosk_model_path", ""))
        self._ptt_cb.setChecked(s.get("push_to_talk", False))

    def _save(self) -> None:
        t = self._summary_time_edit.time()
        self._settings.update({
            "theme":                 "dark" if self._theme_combo.currentIndex() == 0 else "light",
            "notifications_enabled": self._notif_enabled_cb.isChecked(),
            "reminder_minutes":      self._reminder_spin.value(),
            "daily_summary_enabled": self._summary_enabled_cb.isChecked(),
            "daily_summary_hour":    t.hour(),
            "daily_summary_minute":  t.minute(),
            "voice_enabled":         self._voice_enabled_cb.isChecked(),
            "voice_engine":          "google" if self._engine_combo.currentIndex() == 0 else "vosk",
            "vosk_model_path":       self._vosk_path_edit.text().strip(),
            "push_to_talk":          self._ptt_cb.isChecked(),
        })
        self.settings_saved.emit(self._settings)
        self.accept()
