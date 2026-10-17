"""
core/bot_notifier.py
====================
Asynchronous notification dispatcher exclusively for Telegram Bot.

Features:
- Telegram Bot API integration (pure standard library urllib, zero dependencies).
- Deep notification event filtering (reminders, due now, morning/evening summaries, level-ups, quests).
- Silent notification delivery mode (disable_notification).
- Automatic Chat ID detection via getUpdates.
- Non-blocking asynchronous delivery via background worker threads.
- Comprehensive connection testing with friendly diagnostic feedback.
"""

from __future__ import annotations

import json
import logging
import threading
import urllib.parse
import urllib.request
from typing import Dict, Any, Tuple, Optional

logger = logging.getLogger(__name__)

USER_AGENT = "Taskmaster-Desktop/2.0"


# ---------------------------------------------------------------------------
# Telegram API
# ---------------------------------------------------------------------------

def send_telegram_message(
    bot_token: str,
    chat_id: str,
    text: str,
    parse_mode: str = "HTML",
    disable_notification: bool = False,
    timeout: int = 10,
) -> Tuple[bool, str]:
    """
    Send a message via Telegram Bot API.
    Returns (success: bool, info_or_error_message: str).
    """
    token = bot_token.strip()
    cid = chat_id.strip()

    if not token:
        return False, "El Token del bot de Telegram está vacío."
    if not cid:
        return False, "El Chat ID de Telegram está vacío."

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": cid,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
        "disable_notification": bool(disable_notification),
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            res_json = json.loads(body)
            if res_json.get("ok"):
                return True, "Mensaje enviado exitosamente por Telegram."
            return False, f"Telegram API devolvió error: {res_json.get('description', body)}"
    except urllib.error.HTTPError as err:
        err_body = err.read().decode("utf-8", errors="replace")
        logger.warning("Telegram HTTP error %d: %s", err.code, err_body)
        if err.code == 401 or err.code == 404:
            return False, "Token de Bot inválido o no encontrado. Verifícalo en @BotFather."
        if err.code == 400:
            return False, "Chat ID inválido o no has iniciado el bot. ¡Abre tu bot en Telegram y dale a /start!"
        return False, f"Error HTTP {err.code} de Telegram: {err_body}"
    except urllib.error.URLError as err:
        logger.warning("Telegram network error: %s", err)
        return False, f"Error de red o sin conexión a internet: {err.reason}"
    except Exception as exc:
        logger.error("Unexpected error sending Telegram message: %s", exc)
        return False, f"Error inesperado: {exc}"


def test_telegram(bot_token: str, chat_id: str) -> Tuple[bool, str]:
    """Send a friendly test message via Telegram to verify credentials."""
    msg = (
        "🤖 <b>¡Conexión exitosa con BountyHunter!</b>\n\n"
        "Tus notificaciones, resúmenes y recordatorios tácticos llegarán por este canal. 🎯✨"
    )
    return send_telegram_message(bot_token, chat_id, msg, parse_mode="HTML")


def fetch_telegram_chat_id(bot_token: str, timeout: int = 10) -> Tuple[Optional[str], str]:
    """
    Query getUpdates from Telegram Bot API to automatically retrieve the chat_id
    of the user who sent /start or any message to the bot.
    """
    token = bot_token.strip()
    if not token:
        return None, "Ingresa primero el Bot Token."
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
            if not data.get("ok"):
                desc = data.get("description", "Error desconocido de Telegram.")
                return None, f"Telegram API error: {desc}"
            results = data.get("result", [])
            for item in reversed(results):
                msg = item.get("message") or item.get("my_chat_member")
                if msg:
                    chat = msg.get("chat")
                    if chat and "id" in chat:
                        first_name = chat.get("first_name", "Usuario")
                        return str(chat["id"]), f"¡Chat ID detectado para {first_name} ({chat['id']})!"
            return None, "No se encontraron mensajes recientes en tu bot. ¡Abre tu bot en Telegram y dale a /start primero!"
    except urllib.error.HTTPError as err:
        if err.code == 401 or err.code == 404:
            return None, "Bot Token inválido. Verifica que lo hayas copiado bien de @BotFather."
        return None, f"Error HTTP {err.code} al consultar Telegram."
    except Exception as exc:
        return None, f"Error al consultar Telegram: {exc}"


# ---------------------------------------------------------------------------
# Background Dispatcher with Event Filtering
# ---------------------------------------------------------------------------

def send_bot_notification_async(
    title: str,
    message: str,
    settings: Dict[str, Any],
    event_type: str = "general",
) -> None:
    """
    Fire-and-forget worker that delivers notifications to Telegram in a background
    thread according to user's granular event preferences.
    """
    def _worker():
        if not settings.get("telegram_enabled"):
            return

        token = settings.get("telegram_bot_token", "")
        cid = settings.get("telegram_chat_id", "")
        if not token or not cid:
            return

        # Check granular event filters
        if event_type == "reminder" and not settings.get("tg_notify_tasks", True):
            return
        if event_type == "due_now" and not settings.get("tg_notify_due_now", True):
            return
        if event_type == "morning_summary" and not settings.get("tg_notify_morning_summary", True):
            return
        if event_type == "evening_summary" and not settings.get("tg_notify_evening_summary", True):
            return
        if event_type == "level_up" and not settings.get("tg_notify_level_up", True):
            return
        if event_type == "quest_completed" and not settings.get("tg_notify_quests", True):
            return
        if event_type == "high_prio_done" and not settings.get("tg_notify_high_prio", True):
            return

        silent = bool(settings.get("tg_silent_notifications", False))
        tg_text = f"<b>{title}</b>\n\n{message}"
        ok, err = send_telegram_message(
            token, cid, tg_text, parse_mode="HTML", disable_notification=silent
        )
        if not ok:
            logger.warning("Background Telegram notification failed for event '%s': %s", event_type, err)

    t = threading.Thread(target=_worker, name="TelegramNotificationWorker", daemon=True)
    t.start()
