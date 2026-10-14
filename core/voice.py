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

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Command patterns (Spanish)
# ---------------------------------------------------------------------------
COMMAND_PATTERNS = [
    # "añadir tarea título de la tarea"
    (re.compile(r"(?:añadir|agregar)\s+tarea\s+(.+)", re.IGNORECASE), "add_task"),
    # "nueva tarea título"
    (re.compile(r"nueva\s+tarea\s+(.+)", re.IGNORECASE), "add_task"),
    # "completar tarea título"
    (re.compile(r"completar\s+tarea\s+(.+)", re.IGNORECASE), "complete_task"),
    # "eliminar tarea título"
    (re.compile(r"(?:eliminar|borrar)\s+tarea\s+(.+)", re.IGNORECASE), "delete_task"),
    # "mostrar progreso"
    (re.compile(r"mostrar\s+progreso", re.IGNORECASE), "show_progress"),
]


def parse_command(text: str) -> Optional[Dict[str, Any]]:
    """
    Parse a recognised transcript into a command dict.

    Returns
    -------
    dict with keys ``type`` and ``params``, or None if unrecognised.
    """
    text = text.strip()
    for pattern, cmd_type in COMMAND_PATTERNS:
        m = pattern.search(text)
        if m:
            params: Dict[str, Any] = {"raw": text}
            if m.lastindex and m.lastindex >= 1:
                params["title"] = m.group(1).strip()
            return {"type": cmd_type, "params": params}
    return None


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
        except Exception as exc:
            self.error_occurred.emit(f"Error de audio Vosk: {exc}")
        finally:
            if stream:
                stream.stop_stream()
                stream.close()
            p.terminate()

    # ------------------------------------------------------------------
    # Google helpers
    # ------------------------------------------------------------------

    def _run_google(self) -> None:
        """Single-shot Google recognition (listens once, then emits)."""
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
        while self._is_running():
            try:
                with sr.Microphone() as source:
                    recognizer.adjust_for_ambient_noise(source, duration=0.3)
                    audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
                text = recognizer.recognize_google(audio, language="es-ES")
                if text:
                    self.text_recognised.emit(text)
            except sr.WaitTimeoutError:
                pass  # no speech detected within timeout, loop again
            except sr.UnknownValueError:
                pass  # couldn't understand audio
            except sr.RequestError as exc:
                self.error_occurred.emit(f"Google Speech error: {exc}")
                break
            except Exception as exc:
                self.error_occurred.emit(f"Error de micrófono: {exc}")
                break

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
