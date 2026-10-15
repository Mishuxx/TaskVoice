"""
core/bot_notifier.py
====================
Asynchronous notification dispatcher for Telegram and Twilio (WhatsApp & SMS).

Features:
- Telegram Bot API integration (pure standard library urllib, zero dependencies).
- Twilio integration for WhatsApp and SMS delivery (HTTP Basic Auth, zero dependencies).
- WhatsApp CallMeBot integration (legacy fallback).
- Non-blocking asynchronous delivery via background worker threads.
- Comprehensive connection testing methods with friendly error diagnosis.
"""

from __future__ import annotations

import base64
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
# Twilio (WhatsApp & SMS)
# ---------------------------------------------------------------------------

def clean_phone_number(phone: str) -> str:
    """Strip spaces, dashes, parentheses, keeping leading '+' if present."""
    s = phone.strip()
    has_plus = s.startswith("+")
    digits = re.sub(r"\D", "", s)
    return f"+{digits}" if has_plus or digits else digits


def format_twilio_phone(phone: str, channel: str = "whatsapp") -> str:
    """Format phone number with proper country code and optional whatsapp: prefix."""
    raw = phone.strip()
    is_wa = channel.lower() == "whatsapp"
    if is_wa and raw.startswith("whatsapp:"):
        return raw

    # Ensure leading '+'
    cleaned = clean_phone_number(raw)
    if cleaned and not cleaned.startswith("+"):
        cleaned = f"+{cleaned}"

    return f"whatsapp:{cleaned}" if is_wa else cleaned


def send_twilio_message(
    account_sid: str,
    auth_token: str,
    from_number: str,
    to_number: str,
    body: str,
    channel: str = "whatsapp",
    timeout: int = 15,
) -> Tuple[bool, str]:
    """
    Send a message via Twilio REST API for WhatsApp or SMS.
    Uses HTTP Basic Authentication with zero external dependencies.
    """
    sid = account_sid.strip()
    token = auth_token.strip()

    if not sid:
        return False, "El Account SID de Twilio está vacío."
    if not token:
        return False, "El Auth Token de Twilio está vacío."
    if not from_number.strip():
        return False, "El número de origen Twilio (From) está vacío."
    if not to_number.strip():
        return False, "Tu número de destino (To) está vacío."

    from_val = format_twilio_phone(from_number, channel)
    to_val = format_twilio_phone(to_number, channel)

    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    payload = urllib.parse.urlencode({
        "From": from_val,
        "To": to_val,
        "Body": body,
    }).encode("utf-8")

    auth_str = f"{sid}:{token}"
    b64_auth = base64.b64encode(auth_str.encode("utf-8")).decode("ascii")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Basic {b64_auth}",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp_body = resp.read().decode("utf-8", errors="replace")
            res_json = json.loads(resp_body)
            msg_sid = res_json.get("sid", "")
            status = res_json.get("status", "queued")
            return True, f"Mensaje enviado con éxito vía Twilio ({channel.upper()}). Estado: {status} (SID: {msg_sid[:10]}...)"
    except urllib.error.HTTPError as err:
        err_body = err.read().decode("utf-8", errors="replace")
        logger.warning("Twilio HTTP error %d: %s", err.code, err_body)
        try:
            err_json = json.loads(err_body)
            msg = err_json.get("message", err_body)
            code = err_json.get("code", err.code)
            return False, f"Twilio Error [{code}]: {msg}"
        except Exception:
            if err.code == 401:
                return False, "Credenciales inválidas: Verifica tu Account SID y Auth Token de Twilio."
            return False, f"Error HTTP {err.code} de Twilio: {err_body[:150]}"
    except urllib.error.URLError as err:
        logger.warning("Twilio network error: %s", err)
        return False, f"Error de red al conectar con Twilio: {err.reason}"
    except Exception as exc:
        logger.error("Unexpected error sending Twilio message: %s", exc)
        return False, f"Error inesperado: {exc}"


def test_twilio(
    account_sid: str,
    auth_token: str,
    from_number: str,
    to_number: str,
    channel: str = "whatsapp",
) -> Tuple[bool, str]:
    """Send a friendly test message via Twilio (WhatsApp or SMS) to verify credentials."""
    channel_name = "WhatsApp" if channel.lower() == "whatsapp" else "SMS"
    msg = (
        "🤖 *¡Conexión exitosa con Taskmaster!*\n\n"
        f"Tus notificaciones y recordatorios de tareas llegarán por Twilio ({channel_name}). 🎯✨"
    )
    return send_twilio_message(account_sid, auth_token, from_number, to_number, msg, channel=channel)


# ---------------------------------------------------------------------------
# WhatsApp (CallMeBot) - Legacy
# ---------------------------------------------------------------------------

def send_whatsapp_message(
    phone: str,
    apikey: str,
    text: str,
    timeout: int = 12,
) -> Tuple[bool, str]:
    """
    Send a WhatsApp message using CallMeBot API (legacy fallback).
    """
    cleaned_phone = re.sub(r"\D", "", phone.strip())
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
            if "Message queued" in body or "Message sent" in body or "success" in body.lower() or resp.status == 200:
                if "invalid" in body.lower() or "error" in body.lower() or "not authorized" in body.lower():
                    return False, f"CallMeBot respondió: {body[:150]}"
                return True, "Mensaje enviado exitosamente a WhatsApp."
            return False, f"Respuesta de CallMeBot: {body[:150]}"
    except Exception as exc:
        return False, f"Error CallMeBot: {exc}"


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
    Fire-and-forget worker that sends notifications to Telegram, Twilio (WhatsApp/SMS),
    or CallMeBot in a background thread if enabled in settings.
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

        # 2. Twilio (WhatsApp / SMS)
        if settings.get("twilio_enabled"):
            sid = settings.get("twilio_account_sid", "")
            token = settings.get("twilio_auth_token", "")
            from_num = settings.get("twilio_from_number", "")
            to_num = settings.get("twilio_to_number", "")
            channel = settings.get("twilio_channel", "whatsapp")
            if sid and token and from_num and to_num:
                tw_text = f"*{title}*\n\n{message}"
                ok, err = send_twilio_message(sid, token, from_num, to_num, tw_text, channel=channel)
                if not ok:
                    logger.warning("Background Twilio notification failed: %s", err)

        # 3. CallMeBot (Legacy fallback if enabled)
        elif settings.get("whatsapp_enabled"):
            phone = settings.get("whatsapp_phone", "")
            key = settings.get("whatsapp_apikey", "")
            if phone and key:
                wa_text = f"*{title}*\n\n{message}"
                ok, err = send_whatsapp_message(phone, key, wa_text)
                if not ok:
                    logger.warning("Background WhatsApp notification failed: %s", err)

    t = threading.Thread(target=_worker, name="BotNotificationWorker", daemon=True)
    t.start()
