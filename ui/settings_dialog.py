"""
ui/settings_dialog.py
=====================
Settings dialog with five tabs:
  General        – theme toggle, language placeholder
  Notificaciones – desktop notifications, reminder interval, daily summary time
  Bots           – Telegram Bot & WhatsApp (CallMeBot) notification channels
  Voz            – engine selection, Vosk model path, push-to-talk toggle
  Categorías     – list view with add/rename/delete and color picker
"""

from __future__ import annotations

from typing import List, Dict, Any, Optional

from PyQt6.QtCore import Qt, pyqtSignal, QThread, QTime
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QCheckBox, QComboBox, QSpinBox, QTimeEdit, QPushButton,
    QLineEdit, QListWidget, QListWidgetItem, QGroupBox, QFormLayout,
    QColorDialog, QFileDialog, QDialogButtonBox, QMessageBox, QFrame,
    QScrollArea,
)

from core.bot_notifier import test_telegram, test_twilio, test_whatsapp, fetch_telegram_chat_id
from core.i18n import tr, get_language


class BotTestWorker(QThread):
    """Worker thread to run Telegram / WhatsApp test calls without blocking UI."""
    finished_result = pyqtSignal(object, str)

    def __init__(self, test_fn, *args):
        super().__init__()
        self._fn = test_fn
        self._args = args

    def run(self):
        try:
            res = self._fn(*self._args)
            if isinstance(res, tuple) and len(res) == 2:
                self.finished_result.emit(res[0], res[1])
            else:
                self.finished_result.emit(res, "")
        except Exception as exc:
            self.finished_result.emit(None, str(exc))


class SettingsDialog(QDialog):
    """
    Application settings dialog for Taskmaster.

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
        self._active_worker: Optional[BotTestWorker] = None

        self.setWindowTitle(tr("settings_title"))
        self.setMinimumSize(640, 560)
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
            "QTabWidget::pane { border: none; background: #0D1015; }"
            "QTabBar::tab { background: #161B24; color: #9AA4B5; padding: 10px 18px; font-weight: 600; border-bottom: 2px solid transparent; }"
            "QTabBar::tab:selected { background: #1E2430; color: #2DD4BF; border-bottom: 2px solid #2DD4BF; }"
            "QTabBar::tab:hover { background: #1B212C; color: #E8ECF2; }"
        )

        self._general_tab    = self._build_general_tab()
        self._notif_tab      = self._build_notifications_tab()
        self._bots_tab       = self._build_bots_tab()
        self._voice_tab      = self._build_voice_tab()
        self._categories_tab = self._build_categories_tab()

        self._tabs.addTab(self._general_tab,    tr("tab_general"))
        self._tabs.addTab(self._notif_tab,      tr("tab_notifications"))
        self._tabs.addTab(self._bots_tab,       tr("tab_bots"))
        self._tabs.addTab(self._voice_tab,      tr("tab_voice"))
        self._tabs.addTab(self._categories_tab, tr("tab_categories"))

        layout.addWidget(self._tabs)

        # Dialog buttons
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.setStyleSheet(
            "QDialogButtonBox { background: #11151C; padding: 12px 20px; border-top: 1px solid #232A36; }"
            "QPushButton { background: #7C3AED; color: #fff; font-weight: 600; border-radius: 8px; padding: 8px 24px; min-height: 20px; }"
            "QPushButton:hover { background: #6D28D9; }"
            "QPushButton[text='Cancel'] { background: #1F2837; color: #9AA4B5; border: 1px solid #2D3748; }"
            "QPushButton[text='Cancel']:hover { background: #283344; color: #E8ECF2; }"
        )
        save_btn = btn_box.button(QDialogButtonBox.StandardButton.Save)
        if save_btn:
            save_btn.setText(tr("btn_save"))
        cancel_btn = btn_box.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_btn:
            cancel_btn.setText(tr("btn_cancel"))

        btn_box.accepted.connect(self._save)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    # ---- General tab ----

    def _build_general_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setContentsMargins(24, 24, 24, 24)
        form.setSpacing(16)

        self._theme_combo = QComboBox()
        self._theme_combo.addItems([tr("theme_dark"), tr("theme_light")])
        form.addRow(tr("lbl_theme"), self._theme_combo)

        self._lang_combo = QComboBox()
        self._lang_combo.addItems([tr("lang_es"), tr("lang_en")])
        form.addRow(tr("lbl_language"), self._lang_combo)

        return w

    # ---- Notifications tab ----

    def _build_notifications_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        self._notif_enabled_cb = QCheckBox("Habilitar notificaciones locales de escritorio")
        layout.addWidget(self._notif_enabled_cb)

        grp = QGroupBox("Recordatorios de tareas")
        grp_form = QFormLayout(grp)
        grp_form.setSpacing(12)

        self._reminder_spin = QSpinBox()
        self._reminder_spin.setRange(1, 120)
        self._reminder_spin.setSuffix(" min antes")
        grp_form.addRow("Avisar con anticipación:", self._reminder_spin)

        layout.addWidget(grp)

        grp2 = QGroupBox("Resumen diario")
        grp2_form = QFormLayout(grp2)
        grp2_form.setSpacing(12)

        self._summary_enabled_cb = QCheckBox("Enviar resumen diario de tareas matutino")
        grp2_form.addRow(self._summary_enabled_cb)

        self._summary_time_edit = QTimeEdit()
        self._summary_time_edit.setDisplayFormat("HH:mm")
        grp2_form.addRow("Hora del resumen:", self._summary_time_edit)

        layout.addWidget(grp2)
        layout.addStretch()
        return w

    # ---- Bots tab (Telegram & WhatsApp) ----

    def _build_bots_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: #0D1015; }")

        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(20)

        # -------------------------------------------------------------
        # 1. Telegram Section
        # -------------------------------------------------------------
        tg_box = QGroupBox("Telegram Bot")
        tg_layout = QVBoxLayout(tg_box)
        tg_layout.setSpacing(12)
        tg_layout.setContentsMargins(16, 16, 16, 16)

        self._tg_enabled_cb = QCheckBox("Activar alertas y recordatorios por Telegram")
        self._tg_enabled_cb.setStyleSheet("font-weight: 700; color: #5EEAD4;")
        tg_layout.addWidget(self._tg_enabled_cb)

        # Telegram Guide Banner
        tg_guide = QLabel(
            "<b>Pasos para configurar Telegram en 1 minuto:</b><br>"
            "1. Abre Telegram y escribe a <b>@BotFather</b>.<br>"
            "2. Envía <code>/newbot</code>, dale un nombre y copia el <b>Bot Token</b> abajo.<br>"
            "3. Abre tu bot recién creado en Telegram y envíale <code>/start</code>.<br>"
            "4. Haz clic en <b>🔍 Detectar ID</b> para obtener tu Chat ID automáticamente (o usa <b>@userinfobot</b>)."
        )
        tg_guide.setWordWrap(True)
        tg_guide.setStyleSheet(
            "background: #131822; color: #9AA4B5; border: 1px solid #1E2838; border-radius: 8px; padding: 10px; font-size: 11px;"
        )
        tg_layout.addWidget(tg_guide)

        tg_form = QFormLayout()
        tg_form.setSpacing(10)

        self._tg_token_edit = QLineEdit()
        self._tg_token_edit.setPlaceholderText("Ej: 7123456789:AAFlPzM8K4_...")
        tg_form.addRow("Bot Token:", self._tg_token_edit)

        chat_id_row = QHBoxLayout()
        chat_id_row.setSpacing(8)
        self._tg_chat_id_edit = QLineEdit()
        self._tg_chat_id_edit.setPlaceholderText("Ej: 123456789")
        chat_id_row.addWidget(self._tg_chat_id_edit, 1)

        self._tg_detect_btn = QPushButton("🔍 Detectar ID")
        self._tg_detect_btn.setToolTip("Detecta automáticamente tu Chat ID si ya le enviaste /start a tu bot")
        self._tg_detect_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._tg_detect_btn.setStyleSheet(
            "QPushButton { background: #132738; color: #38BDF8; border: 1px solid #0369A1; font-weight: 600; border-radius: 6px; padding: 5px 12px; }"
            "QPushButton:hover { background: #0284C7; color: #fff; }"
        )
        self._tg_detect_btn.clicked.connect(self._detect_telegram_chat_id)
        chat_id_row.addWidget(self._tg_detect_btn)

        tg_form.addRow("Chat ID:", chat_id_row)

        tg_layout.addLayout(tg_form)

        # Test Telegram Button & Status
        tg_action_row = QHBoxLayout()
        self._tg_test_btn = QPushButton("✈ Enviar prueba a Telegram")
        self._tg_test_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._tg_test_btn.setStyleSheet(
            "QPushButton { background: #1E293B; color: #38BDF8; border: 1px solid #0284C7; font-weight: 600; border-radius: 6px; padding: 6px 16px; }"
            "QPushButton:hover { background: #0369A1; color: #fff; }"
        )
        self._tg_test_btn.clicked.connect(self._test_telegram)
        tg_action_row.addWidget(self._tg_test_btn)

        self._tg_status_lbl = QLabel("")
        self._tg_status_lbl.setWordWrap(True)
        self._tg_status_lbl.setStyleSheet("font-size: 11px;")
        tg_action_row.addWidget(self._tg_status_lbl, 1)

        tg_layout.addLayout(tg_action_row)
        layout.addWidget(tg_box)

        # -------------------------------------------------------------
        # -------------------------------------------------------------
        # 2. Twilio Section (WhatsApp & SMS)
        # -------------------------------------------------------------
        tw_box = QGroupBox("Twilio (WhatsApp & SMS)")
        tw_layout = QVBoxLayout(tw_box)
        tw_layout.setSpacing(12)
        tw_layout.setContentsMargins(16, 16, 16, 16)

        self._tw_enabled_cb = QCheckBox("Activar alertas y recordatorios por Twilio (WhatsApp / SMS)")
        self._tw_enabled_cb.setStyleSheet("font-weight: 700; color: #FB7185;")
        tw_layout.addWidget(self._tw_enabled_cb)

        # Twilio Guide Banner
        tw_guide = QLabel(
            "<b>Configuración de Twilio (WhatsApp & SMS):</b><br>"
            "1. Obtén tu <b>Account SID</b> y <b>Auth Token</b> desde tu consola en <b>console.twilio.com</b>.<br>"
            "2. <b>WhatsApp Sandbox:</b> Ve a <i>Develop > Messaging > Try SMS / Try WhatsApp</i>, usa el número asignado (ej: <code>+14155238886</code>) y envía el mensaje de unión (ej: <i>join palabra</i>) desde tu WhatsApp.<br>"
            "3. <b>Plantillas WhatsApp (Trial / Fuera de ventana 24h):</b> Si WhatsApp rechaza texto libre, ingresa el <b>Content SID</b> preaprobado de Twilio (ej: <code>HXb5b62575e6e4ff6129ad7c8efe1f983e</code> de <i>Content Template Builder</i>).<br>"
            "4. <b>SMS:</b> Selecciona el canal SMS e ingresa tu número remitente de Twilio.<br>"
            "5. Ingresa tu número de teléfono con código de país (ej: <code>+54911...</code> o <code>+34...</code>)."
        )
        tw_guide.setWordWrap(True)
        tw_guide.setStyleSheet(
            "background: #131822; color: #9AA4B5; border: 1px solid #1E2838; border-radius: 8px; padding: 10px; font-size: 11px;"
        )
        tw_layout.addWidget(tw_guide)

        tw_form = QFormLayout()
        tw_form.setSpacing(10)

        self._tw_channel_combo = QComboBox()
        self._tw_channel_combo.addItems(["WhatsApp", "SMS"])
        tw_form.addRow("Canal:", self._tw_channel_combo)

        self._tw_sid_edit = QLineEdit()
        self._tw_sid_edit.setPlaceholderText("Tu Account SID (empieza con AC...)")
        tw_form.addRow("Account SID:", self._tw_sid_edit)

        self._tw_token_edit = QLineEdit()
        self._tw_token_edit.setPlaceholderText("Tu Auth Token de Twilio")
        self._tw_token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        tw_form.addRow("Auth Token:", self._tw_token_edit)

        self._tw_from_edit = QLineEdit()
        self._tw_from_edit.setPlaceholderText("Ej: +14155238886 (WhatsApp Sandbox) o tu número Twilio")
        tw_form.addRow("De (Twilio Number):", self._tw_from_edit)

        self._tw_to_edit = QLineEdit()
        self._tw_to_edit.setPlaceholderText("Ej: +34612345678 o +54911...")
        tw_form.addRow("Para (Tu Teléfono):", self._tw_to_edit)

        self._tw_contentsid_edit = QLineEdit()
        self._tw_contentsid_edit.setPlaceholderText("Dejar en blanco para texto libre (o plantilla HX...)")
        tw_form.addRow("Content SID:", self._tw_contentsid_edit)

        tw_csid_hint = QLabel("💡 Si ya enviaste «Hola» a Twilio por WhatsApp, deja Content SID en blanco para enviar texto plano libre directo.")
        tw_csid_hint.setWordWrap(True)
        tw_csid_hint.setStyleSheet("color: #64748B; font-size: 10px; padding-left: 2px;")
        tw_form.addRow("", tw_csid_hint)

        tw_layout.addLayout(tw_form)

        # Test Twilio Button & Status
        tw_action_row = QHBoxLayout()
        self._tw_test_btn = QPushButton("📱 Enviar prueba con Twilio")
        self._tw_test_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._tw_test_btn.setStyleSheet(
            "QPushButton { background: #3B1219; color: #FB7185; border: 1px solid #E11D48; font-weight: 600; border-radius: 6px; padding: 6px 16px; }"
            "QPushButton:hover { background: #E11D48; color: #fff; }"
        )
        self._tw_test_btn.clicked.connect(self._test_twilio)
        tw_action_row.addWidget(self._tw_test_btn)

        self._tw_status_lbl = QLabel("")
        self._tw_status_lbl.setWordWrap(True)
        self._tw_status_lbl.setStyleSheet("font-size: 11px;")
        tw_action_row.addWidget(self._tw_status_lbl, 1)

        tw_layout.addLayout(tw_action_row)
        layout.addWidget(tw_box)

        layout.addStretch()
        scroll.setWidget(w)
        return scroll

    def _detect_telegram_chat_id(self) -> None:
        token = self._tg_token_edit.text().strip()
        if not token:
            self._tg_status_lbl.setText("⚠ Pega primero el Bot Token que te dio @BotFather.")
            self._tg_status_lbl.setStyleSheet("color: #FBBF24; font-size: 11px;")
            return

        self._tg_detect_btn.setEnabled(False)
        self._tg_detect_btn.setText("Buscando...")
        self._tg_status_lbl.setText("Consultando mensajes en tu bot...")
        self._tg_status_lbl.setStyleSheet("color: #9AA4B5; font-size: 11px;")

        self._active_worker = BotTestWorker(fetch_telegram_chat_id, token)
        self._active_worker.finished_result.connect(self._on_telegram_detect_result)
        self._active_worker.start()

    def _on_telegram_detect_result(self, result: Any, msg: str) -> None:
        self._tg_detect_btn.setEnabled(True)
        self._tg_detect_btn.setText("🔍 Detectar ID")
        if result:
            self._tg_chat_id_edit.setText(str(result))
            self._tg_status_lbl.setText(f"✔ {msg}")
            self._tg_status_lbl.setStyleSheet("color: #34D399; font-weight: bold; font-size: 11px;")
        else:
            self._tg_status_lbl.setText(f"✕ {msg}")
            self._tg_status_lbl.setStyleSheet("color: #F87171; font-weight: bold; font-size: 11px;")

    def _test_telegram(self) -> None:
        token = self._tg_token_edit.text().strip()
        chat_id = self._tg_chat_id_edit.text().strip()

        if not token or not chat_id:
            self._tg_status_lbl.setText("⚠ Ingresa primero el Token y el Chat ID.")
            self._tg_status_lbl.setStyleSheet("color: #FBBF24; font-size: 11px;")
            return

        self._tg_test_btn.setEnabled(False)
        self._tg_test_btn.setText("Enviando...")
        self._tg_status_lbl.setText("Conectando con Telegram...")
        self._tg_status_lbl.setStyleSheet("color: #9AA4B5; font-size: 11px;")

        self._active_worker = BotTestWorker(test_telegram, token, chat_id)
        self._active_worker.finished_result.connect(self._on_telegram_test_result)
        self._active_worker.start()

    def _on_telegram_test_result(self, success: Any, msg: str) -> None:
        self._tg_test_btn.setEnabled(True)
        self._tg_test_btn.setText("✈ Enviar prueba a Telegram")
        if success:
            self._tg_status_lbl.setText(f"✔ {msg}")
            self._tg_status_lbl.setStyleSheet("color: #34D399; font-weight: bold; font-size: 11px;")
        else:
            self._tg_status_lbl.setText(f"✕ {msg}")
            self._tg_status_lbl.setStyleSheet("color: #F87171; font-weight: bold; font-size: 11px;")

    def _test_twilio(self) -> None:
        sid = self._tw_sid_edit.text().strip()
        token = self._tw_token_edit.text().strip()
        from_num = self._tw_from_edit.text().strip()
        to_num = self._tw_to_edit.text().strip()
        channel = self._tw_channel_combo.currentText().lower()
        contentsid = self._tw_contentsid_edit.text().strip() or None

        if not sid or not token or not from_num or not to_num:
            self._tw_status_lbl.setText("⚠ Completa Account SID, Auth Token, From y To de Twilio.")
            self._tw_status_lbl.setStyleSheet("color: #FBBF24; font-size: 11px;")
            return

        self._tw_test_btn.setEnabled(False)
        self._tw_test_btn.setText("Enviando...")
        template_tag = " [Plantilla HX]" if contentsid else ""
        self._tw_status_lbl.setText(f"Conectando con Twilio ({channel.upper()}{template_tag})...")
        self._tw_status_lbl.setStyleSheet("color: #9AA4B5; font-size: 11px;")

        self._active_worker = BotTestWorker(test_twilio, sid, token, from_num, to_num, channel, contentsid)
        self._active_worker.finished_result.connect(self._on_twilio_test_result)
        self._active_worker.start()

    def _on_twilio_test_result(self, success: Any, msg: str) -> None:
        self._tw_test_btn.setEnabled(True)
        self._tw_test_btn.setText("📱 Enviar prueba con Twilio")
        if success:
            self._tw_status_lbl.setText(f"✔ {msg}")
            self._tw_status_lbl.setStyleSheet("color: #34D399; font-weight: bold; font-size: 11px;")
        else:
            self._tw_status_lbl.setText(f"✕ {msg}")
            self._tw_status_lbl.setStyleSheet("color: #F87171; font-weight: bold; font-size: 11px;")

    # ---- Voice tab ----

    def _build_voice_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        self._voice_enabled_cb = QCheckBox("Habilitar reconocimiento de voz")
        layout.addWidget(self._voice_enabled_cb)

        form = QFormLayout()
        form.setSpacing(12)

        self._engine_combo = QComboBox()
        self._engine_combo.addItems(["Google (online)", "Vosk (offline)"])
        form.addRow("Motor de voz:", self._engine_combo)

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
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        self._cat_list = QListWidget()
        self._cat_list.setStyleSheet(
            "QListWidget { background: #161B24; border: 1px solid #232A36; border-radius: 8px; }"
            "QListWidget::item { padding: 8px 12px; border-radius: 6px; font-weight: 600; }"
            "QListWidget::item:selected { background: #1C1730; border: 1px solid #3B2F63; }"
        )
        layout.addWidget(self._cat_list)

        btn_row = QHBoxLayout()
        add_btn    = QPushButton("➕ Añadir")
        rename_btn = QPushButton("✏ Renombrar")
        color_btn  = QPushButton("🎨 Color")
        del_btn    = QPushButton("🗑 Eliminar")

        for b in [add_btn, rename_btn, color_btn, del_btn]:
            b.setStyleSheet(
                "QPushButton { background: #1F2837; color: #CBD5E1; border: 1px solid #2D3748; border-radius: 6px;"
                " padding: 6px 12px; font-weight: 600; } QPushButton:hover { background: #283344; color: #FFFFFF; }"
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
            item = QListWidgetItem(f"●  {cat['name']}")
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
        dlg.setFixedWidth(340)
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
        self._lang_combo.setCurrentIndex(1 if s.get("language", "es") == "en" else 0)

        # Notifications
        self._notif_enabled_cb.setChecked(s.get("notifications_enabled", True))
        self._reminder_spin.setValue(s.get("reminder_minutes", 30))
        self._summary_enabled_cb.setChecked(s.get("daily_summary_enabled", True))
        h = s.get("daily_summary_hour", 9)
        m = s.get("daily_summary_minute", 0)
        self._summary_time_edit.setTime(QTime(h, m))

        # Bots
        self._tg_enabled_cb.setChecked(s.get("telegram_enabled", False))
        self._tg_token_edit.setText(s.get("telegram_bot_token", ""))
        self._tg_chat_id_edit.setText(s.get("telegram_chat_id", ""))

        # Twilio
        self._tw_enabled_cb.setChecked(s.get("twilio_enabled", False))
        channel = s.get("twilio_channel", "whatsapp").lower()
        self._tw_channel_combo.setCurrentIndex(1 if channel == "sms" else 0)
        self._tw_sid_edit.setText(s.get("twilio_account_sid", ""))
        self._tw_token_edit.setText(s.get("twilio_auth_token", ""))
        self._tw_from_edit.setText(s.get("twilio_from_number", "+14155238886"))
        self._tw_to_edit.setText(s.get("twilio_to_number", ""))
        self._tw_contentsid_edit.setText(s.get("twilio_content_sid", ""))

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
            "language":              "en" if self._lang_combo.currentIndex() == 1 else "es",
            "notifications_enabled": self._notif_enabled_cb.isChecked(),
            "reminder_minutes":      self._reminder_spin.value(),
            "daily_summary_enabled": self._summary_enabled_cb.isChecked(),
            "daily_summary_hour":    t.hour(),
            "daily_summary_minute":  t.minute(),
            "telegram_enabled":      self._tg_enabled_cb.isChecked(),
            "telegram_bot_token":    self._tg_token_edit.text().strip(),
            "telegram_chat_id":      self._tg_chat_id_edit.text().strip(),
            "twilio_enabled":        self._tw_enabled_cb.isChecked(),
            "twilio_channel":        self._tw_channel_combo.currentText().lower(),
            "twilio_account_sid":    self._tw_sid_edit.text().strip(),
            "twilio_auth_token":     self._tw_token_edit.text().strip(),
            "twilio_from_number":    self._tw_from_edit.text().strip(),
            "twilio_to_number":      self._tw_to_edit.text().strip(),
            "twilio_content_sid":    self._tw_contentsid_edit.text().strip(),
            "voice_enabled":         self._voice_enabled_cb.isChecked(),
            "voice_engine":          "google" if self._engine_combo.currentIndex() == 0 else "vosk",
            "vosk_model_path":       self._vosk_path_edit.text().strip(),
            "push_to_talk":          self._ptt_cb.isChecked(),
        })
        self.settings_saved.emit(self._settings)
        self.accept()
