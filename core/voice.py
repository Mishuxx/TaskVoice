"""
core/voice.py
=============
Voice recognition manager for TaskVoice.

Tries Vosk (offline) first, then falls back to Google Speech Recognition (online).
Runs in a QThread to avoid blocking the UI.

Signals
-------
command_recognized(str, dict)
    Emitted when a voice command is parsed.
    First arg: command type string (e.g. "add_task").
    Second arg: dict with extracted parameters.

listening_state_changed(bool)
    Emitted when recording starts or stops.

error_occurred(str)
    Emitted on non-fatal errors.
"""

import re
import json
import logging
from typing import Optional, Dict, Any

from PyQt6.QtCore import QObject, QThread, pyqtSignal, QMutex, QMutexLocker

from core.recurrence import extract_recurrence

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Spanish word-to-number dictionary
# ---------------------------------------------------------------------------
SPANISH_WORD_TO_NUMBER: Dict[str, int] = {
    "cero": 0, "uno": 1, "un": 1, "una": 1, "primero": 1, "primera": 1, "1º": 1, "1°": 1,
    "dos": 2, "segundo": 2, "segunda": 2, "2º": 2, "2°": 2,
    "tres": 3, "tercero": 3, "tercera": 3, "3º": 3, "3°": 3,
    "cuatro": 4, "cuarto": 4, "cuarta": 4,
    "cinco": 5, "quinto": 5, "quinta": 5,
    "seis": 6, "sexto": 6, "sexta": 6,
    "siete": 7, "séptimo": 7, "septimo": 7, "séptima": 7,
    "ocho": 8, "octavo": 8, "octava": 8,
    "nueve": 9, "noveno": 9, "novena": 9,
    "diez": 10, "décimo": 10, "decimo": 10,
    "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15,
    "dieciséis": 16, "dieciseis": 16, "diecisiete": 17, "dieciocho": 18, "diecinueve": 19,
    "veinte": 20, "veintiuno": 21, "veintidós": 22, "veintidos": 22, "veintitrés": 23, "veintitres": 23,
    "veinticuatro": 24, "veinticinco": 25, "veintiséis": 26, "veintiseis": 26, "veintisiete": 27,
    "veintiocho": 28, "veintinueve": 29, "treinta": 30, "cuarenta": 40, "cincuenta": 50,
}

ENGLISH_WORD_TO_NUMBER: Dict[str, int] = {
    "zero": 0, "one": 1, "first": 1, "1st": 1,
    "two": 2, "second": 2, "2nd": 2,
    "three": 3, "third": 3, "3rd": 3,
    "four": 4, "fourth": 4, "4th": 4,
    "five": 5, "fifth": 5, "5th": 5,
    "six": 6, "sixth": 6, "6th": 6,
    "seven": 7, "seventh": 7, "7th": 7,
    "eight": 8, "eighth": 8, "8th": 8,
    "nine": 9, "ninth": 9, "9th": 9,
    "ten": 10, "tenth": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
}


def extract_task_number(text: str) -> Optional[int]:
    """
    Extract a task index number from text (e.g. 'uno', '1', 'número 3', 'task 2', 'number 1').
    Returns an int >= 1, or None if no number is identified.
    """
    if not text:
        return None
    cleaned = text.strip().lower()
    cleaned = re.sub(r"^(?:la\s+|the\s+)?(?:tarea\s+|task\s+)?(?:n[uú]mero\s+|number\s+|#\s*)?", "", cleaned).strip()
    cleaned = re.sub(r"\s+(?:as\s+)?(?:done|completed|finished|hecha|completada|terminada|finalizada)$", "", cleaned).strip()
    if cleaned.isdigit():
        return int(cleaned)
    m = re.search(r"\b(\d+)\b", cleaned)
    if m:
        return int(m.group(1))
    for word in cleaned.split():
        if word in SPANISH_WORD_TO_NUMBER:
            return SPANISH_WORD_TO_NUMBER[word]
        if word in ENGLISH_WORD_TO_NUMBER:
            return ENGLISH_WORD_TO_NUMBER[word]
    return None


def extract_priority(text: str) -> tuple[str, int]:
    """
    Detect priority from text (alta/3/urgente/high -> 3, media/2/normal/medium -> 2, baja/1/low -> 1)
    and return (cleaned_title, priority_int).
    """
    prio = 2  # default Media
    cleaned = text

    # Alta / High (3)
    p_alta = re.compile(
        r'\b(?:with\s+)?(?:high|urgent|maximum)\s+priority\b|\b(?:con\s+)?(?:prioridad\s+(?:alta|3|m[aá]xima|urgente)|(?:alta|m[aá]xima|urgente)\s+prioridad|urgente|urgent)\b',
        re.IGNORECASE,
    )
    # Baja / Low (1)
    p_baja = re.compile(
        r'\b(?:with\s+)?(?:low|minor)\s+priority\b|\b(?:con\s+)?(?:prioridad\s+(?:baja|1|menor)|(?:baja|menor)\s+prioridad|no\s+urgente|not\s+urgent)\b',
        re.IGNORECASE,
    )
    # Media / Medium (2)
    p_media = re.compile(
        r'\b(?:with\s+)?(?:medium|normal)\s+priority\b|\b(?:con\s+)?(?:prioridad\s+(?:media|2|normal)|(?:media|normal)\s+prioridad)\b',
        re.IGNORECASE,
    )

    if p_alta.search(cleaned):
        prio = 3
        cleaned = p_alta.sub('', cleaned)
    elif p_baja.search(cleaned):
        prio = 1
        cleaned = p_baja.sub('', cleaned)
    elif p_media.search(cleaned):
        prio = 2
        cleaned = p_media.sub('', cleaned)

    cleaned = re.sub(r'\s+', ' ', cleaned).strip(' :-')
    if cleaned:
        cleaned = cleaned[0].upper() + cleaned[1:]
    return cleaned, prio


# ---------------------------------------------------------------------------
# Command patterns (Spanish & English)
# ---------------------------------------------------------------------------
COMMAND_PATTERNS = [
    # Mostrar Misiones / RPG / Operaciones
    (re.compile(r"^(?:mostrar|ver|abrir|ir\s+a(?:l|\s+las?)?|consultar|show|view|open|check)?\s*(?:las?\s+|the\s+)?(?:misiones|mision|operaciones|bounties|rpg|missions|quests)[\.\!\?]?$", re.IGNORECASE), "show_missions"),
    # Consultar Nivel / Rango / XP
    (re.compile(r"^(?:mostrar|ver|consultar|cu[aá]l\s+es|show|view|check|what\s+is)?\s*(?:mi\s+|my\s+)?(?:nivel|rango|experiencia|xp|perfil|level|rank|profile)[\.\!\?]?$", re.IGNORECASE), "show_level"),
    # Mostrar Dashboard / Estadísticas
    (re.compile(r"^(?:mostrar|ver|abrir|ir\s+al?|entrar\s+al?|show|view|open|go\s+to)?\s*(?:el\s+|the\s+)?(?:dashboard|dash|panel|estad[ií]sticas?|m[eé]tricas?|gr[aá]ficos?|progreso|stats|statistics|metrics|charts)[\.\!\?]?$", re.IGNORECASE), "show_dashboard"),
    # Mostrar Tareas / Lista
    (re.compile(r"^(?:mostrar|ver|abrir|ir\s+a(?:l|\s+la)?|volver\s+a(?:l|\s+la)?|volver|show|view|open|go\s+to)?\s*(?:las?\s+|the\s+)?(?:tareas?|lista|tasks?|task\s+list)[\.\!\?]?$", re.IGNORECASE), "show_tasks"),
    # Completar tarea (por número o título)
    (re.compile(r"^(?:completar|terminar|finalizar|marcar(?:\s+como\s+(?:hecha|completada))?|complete|finish|done|mark\s+(?:as\s+)?done)\s+(?:la\s+|the\s+)?(?:tarea\s+|task\s+)?(?:n[uú]mero\s+|number\s+|#\s*)?(.+)", re.IGNORECASE), "complete_task"),
    (re.compile(r"^(?:la\s+|the\s+)?(?:tarea\s+|task\s+)(.+?)\s+(?:como\s+|as\s+)?(?:completada|hecha|terminada|finalizada|done|finished)$", re.IGNORECASE), "complete_task"),
    # Eliminar tarea (por número o título)
    (re.compile(r"^(?:eliminar|borrar|quitar|delete|remove)\s+(?:la\s+|the\s+)?(?:tarea\s+|task\s+)?(?:n[uú]mero\s+|number\s+|#\s*)?(.+)", re.IGNORECASE), "delete_task"),
    # Añadir / Crear tarea con prefijo explícito
    (re.compile(r"^(?:añadir|agregar|crear|nueva|poner|anotar|recordar|add|create|new|remind\s+me\s+to)\s+(?:la\s+|una\s+|a\s+|the\s+)?(?:tarea\s+|task\s+)?(.+)", re.IGNORECASE), "add_task"),
    (re.compile(r"^(?:tarea|nueva\s+tarea|task|new\s+task)\s*[:\-]?\s*(.+)", re.IGNORECASE), "add_task"),
    (re.compile(r"^(?:recordar|anotar|remind\s+me\s+to)\s+(.+)", re.IGNORECASE), "add_task"),
]


def parse_command(text: str) -> Optional[Dict[str, Any]]:
    """
    Parse a recognised transcript into a command dict.
    If no special command is matched, the spoken text is treated as a new task!

    Returns
    -------
    dict with keys ``type`` and ``params``.
    """
    text = text.strip()
    if not text:
        return None

    for pattern, cmd_type in COMMAND_PATTERNS:
        m = pattern.search(text)
        if m:
            params: Dict[str, Any] = {"raw": text}
            if cmd_type == "add_task":
                title_val = m.group(1).strip() if (m.lastindex and m.lastindex >= 1) else text
                clean_title, prio = extract_priority(title_val)
                final_title, is_rec, r_days, r_time, r_type = extract_recurrence(clean_title)
                params["title"] = final_title
                params["priority"] = prio
                params["is_recurring"] = is_rec
                params["recurrence_days"] = r_days
                params["recurrence_time"] = r_time
                params["recurrence_type"] = r_type
                return {"type": cmd_type, "params": params}

            if m.lastindex and m.lastindex >= 1:
                title_val = m.group(1).strip()
                params["title"] = title_val
                # Check if it refers to a task number
                num = extract_task_number(title_val)
                if num is not None:
                    params["number"] = num
            return {"type": cmd_type, "params": params}

    # Si el usuario simplemente dijo algo (ej. "comprar leche prioridad alta"),
    # se convierte automáticamente en una nueva tarea con su prioridad y recurrencia extraídas:
    clean_title, prio = extract_priority(text)
    final_title, is_rec, r_days, r_time, r_type = extract_recurrence(clean_title)
    return {
        "type": "add_task",
        "params": {
            "title": final_title,
            "priority": prio,
            "is_recurring": is_rec,
            "recurrence_days": r_days,
            "recurrence_time": r_time,
            "recurrence_type": r_type,
            "raw": text,
        },
    }





# ===========================================================================
# Worker thread
# ===========================================================================

class _VoiceWorker(QObject):
    """
    Internal worker that lives in a QThread.
    Captures audio from the microphone and emits recognised text.
    """

    text_recognised = pyqtSignal(str)
    error_occurred  = pyqtSignal(str)
    finished        = pyqtSignal()

    def __init__(self, engine: str = "google", vosk_model_path: str = "", parent=None):
        super().__init__(parent)
        self.engine = engine                   # "vosk" | "google"
        self.vosk_model_path = vosk_model_path
        self._running = False
        self._mutex = QMutex()
        self._model = None     # vosk Model (lazy-loaded)
        self._rec   = None     # vosk KaldiRecognizer

    # ------------------------------------------------------------------
    # Vosk helpers
    # ------------------------------------------------------------------

    def _init_vosk(self) -> bool:
        """Attempt to initialise the Vosk model. Returns True on success."""
        try:
            import vosk  # type: ignore
            model_path = self.vosk_model_path or "model"
            import os
            if not os.path.isdir(model_path):
                self.error_occurred.emit(
                    f"Vosk: no se encontró el modelo en '{model_path}'. "
                    "Descarga uno desde https://alphacephei.com/vosk/models"
                )
                return False
            self._model = vosk.Model(model_path)
            self._rec   = vosk.KaldiRecognizer(self._model, 16000)
            logger.info("Vosk model loaded from '%s'", model_path)
            return True
        except ImportError:
            self.error_occurred.emit("Vosk no está instalado (pip install vosk).")
            return False
        except Exception as exc:
            self.error_occurred.emit(f"Vosk error: {exc}")
            return False

    def _run_vosk(self) -> None:
        """Continuous Vosk recognition loop."""
        try:
            import pyaudio  # type: ignore
        except ImportError:
            self.error_occurred.emit("PyAudio no está instalado (pip install pyaudio).")
            self._running = False
            self.finished.emit()
            return

        p = pyaudio.PyAudio()
        stream = None
        try:
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=8192,
            )
            stream.start_stream()
            while self._is_running():
                data = stream.read(4096, exception_on_overflow=False)
                if self._rec.AcceptWaveform(data):
                    result = json.loads(self._rec.Result())
                    text = result.get("text", "").strip()
                    if text:
                        self.text_recognised.emit(text)
            if self._rec:
                try:
                    final_res = json.loads(self._rec.FinalResult())
                    text = final_res.get("text", "").strip()
                    if text:
                        self.text_recognised.emit(text)
                except Exception:
                    pass
        except Exception as exc:
            self.error_occurred.emit(f"Error de audio Vosk: {exc}")
        finally:
            if stream:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception:
                    pass
            p.terminate()

    # ------------------------------------------------------------------
    # Google helpers
    # ------------------------------------------------------------------

    def _run_google(self) -> None:
        """Continuous Google recognition keeping the microphone active."""
        try:
            import speech_recognition as sr  # type: ignore
        except ImportError:
            self.error_occurred.emit(
                "SpeechRecognition no está instalado (pip install SpeechRecognition)."
            )
            self._running = False
            self.finished.emit()
            return

        recognizer = sr.Recognizer()
        recognizer.dynamic_energy_threshold = True
        recognizer.energy_threshold = 300
        recognizer.pause_threshold = 0.8
        try:
            with sr.Microphone() as source:
                # Calibrar ruido de fondo una sola vez al inicio
                try:
                    recognizer.adjust_for_ambient_noise(source, duration=0.5)
                except Exception:
                    pass

                while self._is_running():
                    try:
                        audio = recognizer.listen(source, timeout=3.0, phrase_time_limit=12.0)
                    except sr.WaitTimeoutError:
                        continue
                    except Exception as exc:
                        if not self._is_running():
                            break
                        logger.debug("Microphone listen error: %s", exc)
                        continue

                    if not self._is_running():
                        break

                    try:
                        try:
                            from core.i18n import get_language
                            lang_code = "en-US" if get_language() == "en" else "es-ES"
                        except Exception:
                            lang_code = "es-ES"

                        text = recognizer.recognize_google(audio, language=lang_code)
                        text = text.strip() if text else ""
                        if text:
                            self.text_recognised.emit(text)
                    except sr.UnknownValueError:
                        # Audio detectado pero sin palabras reconocibles
                        continue
                    except sr.RequestError as exc:
                        self.error_occurred.emit(f"Error de conexión de voz: {exc}")
                        break
                    except Exception as exc:
                        logger.debug("Speech recognition exception: %s", exc)
                        continue
        except Exception as exc:
            self.error_occurred.emit(f"Error de micrófono: {exc}")


    # ------------------------------------------------------------------
    # Main entry point (called by QThread.started)
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Start the recognition loop."""
        with QMutexLocker(self._mutex):
            self._running = True

        if self.engine == "vosk":
            if not self._init_vosk():
                # fallback to google
                self.engine = "google"

        if self.engine == "vosk" and self._model is not None:
            self._run_vosk()
        else:
            self._run_google()

        with QMutexLocker(self._mutex):
            self._running = False
        self.finished.emit()

    def stop(self) -> None:
        """Signal the recognition loop to stop."""
        with QMutexLocker(self._mutex):
            self._running = False

    def _is_running(self) -> bool:
        with QMutexLocker(self._mutex):
            return self._running


# ===========================================================================
# VoiceManager  (public API)
# ===========================================================================

class VoiceManager(QObject):
    """
    High-level voice manager.

    Signals
    -------
    command_recognized(str, dict)
        Emitted with (command_type, params_dict).
    listening_state_changed(bool)
        True when listening starts, False when it stops.
    error_occurred(str)
        Human-readable error message.
    raw_text_recognised(str)
        Raw transcript (useful for debug display).
    """

    command_recognized    = pyqtSignal(str, dict)
    listening_state_changed = pyqtSignal(bool)
    error_occurred        = pyqtSignal(str)
    raw_text_recognised   = pyqtSignal(str)

    def __init__(
        self,
        engine: str = "google",
        vosk_model_path: str = "",
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self.engine = engine
        self.vosk_model_path = vosk_model_path
        self._thread: Optional[QThread] = None
        self._worker: Optional[_VoiceWorker] = None
        self._listening = False

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_listening(self) -> bool:
        return self._listening

    # ------------------------------------------------------------------
    # Start / stop
    # ------------------------------------------------------------------

    def start_listening(self) -> None:
        """Begin voice recognition in a background thread."""
        if self._listening:
            return

        self._thread = QThread()
        self._worker = _VoiceWorker(
            engine=self.engine,
            vosk_model_path=self.vosk_model_path,
        )
        self._worker.moveToThread(self._thread)

        # Connections
        self._thread.started.connect(self._worker.run)
        self._worker.text_recognised.connect(self._on_text)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.finished.connect(self._on_finished)

        self._listening = True
        self.listening_state_changed.emit(True)
        self._thread.start()
        logger.info("VoiceManager: started listening (engine=%s)", self.engine)

    def stop_listening(self) -> None:
        """Stop voice recognition."""
        if not self._listening:
            return
        if self._worker:
            self._worker.stop()
        if self._thread:
            self._thread.quit()
            self._thread.wait(3000)
        self._listening = False
        self.listening_state_changed.emit(False)
        logger.info("VoiceManager: stopped listening")

    def toggle_listening(self) -> None:
        """Toggle listening on/off."""
        if self._listening:
            self.stop_listening()
        else:
            self.start_listening()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_text(self, text: str) -> None:
        """Process recognised text and emit parsed command."""
        logger.debug("Recognised: %s", text)
        self.raw_text_recognised.emit(text)
        result = parse_command(text)
        if result:
            self.command_recognized.emit(result["type"], result["params"])
        else:
            # Re-emit as unrecognised for UI feedback
            self.command_recognized.emit("unknown", {"raw": text})

    def _on_error(self, message: str) -> None:
        logger.error("VoiceManager error: %s", message)
        self.error_occurred.emit(message)

    def _on_finished(self) -> None:
        """Called when the worker loop exits."""
        self._listening = False
        self.listening_state_changed.emit(False)
        if self._thread:
            self._thread.quit()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        """Stop listening and release all resources."""
        self.stop_listening()
