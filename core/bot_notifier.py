"""
core/bot_notifier.py
====================
Asynchronous notification dispatcher for Telegram and WhatsApp (via CallMeBot).

Features:
- Telegram Bot API integration (pure standard library urllib, zero dependencies).
- WhatsApp CallMeBot integration (direct messaging to personal number).
- Non-blocking asynchronous delivery via background worker threads.
- Comprehensive connection testing methods with friendly error diagnosis.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import urllib.parse
import urllib.request
from typing import Dict, Any, Tuple, Optional

logger = logging.getLogger(__name__)

USER_AGENT = "Taskmaster-Desktop/2.0"


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------

def send_telegram_message(
    bot_token: str,
    chat_id: str,
    text: str,
    parse_mode: str = "HTML",
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
        "🤖 <b>¡Conexión exitosa con Taskmaster!</b>\n\n"
        "Tus notificaciones y recordatorios de tareas llegarán por este canal. 🎯✨"
    )
    return send_telegram_message(bot_token, chat_id, msg, parse_mode="HTML")


# ---------------------------------------------------------------------------
# WhatsApp (CallMeBot)
# ---------------------------------------------------------------------------

def clean_phone_number(phone: str) -> str:
    """Strip all non-digit characters (+, spaces, dashes, parentheses)."""
    return re.sub(r"\D", "", phone.strip())


def send_whatsapp_message(
    phone: str,
    apikey: str,
    text: str,
    timeout: int = 12,
) -> Tuple[bool, str]:
    """
    Send a WhatsApp message using CallMeBot API.
    Returns (success: bool, info_or_error_message: str).
    """
    cleaned_phone = clean_phone_number(phone)
    key = apikey.strip()

    if not cleaned_phone:
        return False, "El número de teléfono está vacío o no contiene dígitos."
    if not key:
        return False, "La API Key de CallMeBot está vacía."

    params = urllib.parse.urlencode({
        "phone": cleaned_phone,
        "text": text,
        "apikey": key,
    })
    url = f"https://api.callmebot.com/whatsapp.php?{params}"

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": USER_AGENT},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            # CallMeBot returns HTML or plain text with status
            if "Message queued" in body or "Message sent" in body or "success" in body.lower() or resp.status == 200:
                # Some error messages still return 200 with text like "API Key not valid"
                if "invalid" in body.lower() or "error" in body.lower() or "not authorized" in body.lower():
                    return False, f"CallMeBot respondió: {body[:150]}"
                return True, "Mensaje enviado exitosamente a WhatsApp."
            return False, f"Respuesta de CallMeBot: {body[:150]}"
    except urllib.error.HTTPError as err:
        err_body = err.read().decode("utf-8", errors="replace")
        logger.warning("CallMeBot HTTP error %d: %s", err.code, err_body)
        return False, f"Error HTTP {err.code} de CallMeBot: {err_body[:120]}"
    except urllib.error.URLError as err:
        logger.warning("CallMeBot network error: %s", err)
        return False, f"Error de red al conectar con CallMeBot: {err.reason}"
    except Exception as exc:
        logger.error("Unexpected error sending WhatsApp message: %s", exc)
        return False, f"Error inesperado: {exc}"


def test_whatsapp(phone: str, apikey: str) -> Tuple[bool, str]:
    """Send a friendly test message via WhatsApp to verify credentials."""
    msg = (
        "🤖 *¡Conexión exitosa con Taskmaster!*\n\n"
        "Tus notificaciones y recordatorios de tareas llegarán a este WhatsApp. 🎯✨"
    )
    return send_whatsapp_message(phone, apikey, msg)


# ---------------------------------------------------------------------------
# Background Dispatcher
# ---------------------------------------------------------------------------

def send_bot_notification_async(
    title: str,
    message: str,
    settings: Dict[str, Any],
) -> None:
    """
    Fire-and-forget worker that sends the notification to Telegram and/or WhatsApp
    in a background thread if enabled in settings.
    """
    def _worker():
        # 1. Telegram
        if settings.get("telegram_enabled"):
            token = settings.get("telegram_bot_token", "")
            cid = settings.get("telegram_chat_id", "")
            if token and cid:
                tg_text = f"<b>{title}</b>\n\n{message}"
                ok, err = send_telegram_message(token, cid, tg_text, parse_mode="HTML")
                if not ok:
                    logger.warning("Background Telegram notification failed: %s", err)

        # 2. WhatsApp
        if settings.get("whatsapp_enabled"):
            phone = settings.get("whatsapp_phone", "")
            key = settings.get("whatsapp_apikey", "")
            if phone and key:
                wa_text = f"*{title}*\n\n{message}"
                ok, err = send_whatsapp_message(phone, key, wa_text)
                if not ok:
                    logger.warning("Background WhatsApp notification failed: %s", err)

    t = threading.Thread(target=_worker, name="BotNotificationWorker", daemon=True)
    t.start()
