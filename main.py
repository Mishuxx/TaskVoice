"""
main.py
=======
Entry point for the TaskVoice application.

Initialises the QApplication, applies the dark theme, creates the database,
notification manager, and main window. Handles SIGINT gracefully so the app
can be interrupted from the terminal during development.
"""

import sys
import os
import signal
import logging

# --------------------------------------------------------------------------
# Configure logging before anything else
# --------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("taskvoice")

# --------------------------------------------------------------------------
# Qt imports
# --------------------------------------------------------------------------
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon, QFont
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

# --------------------------------------------------------------------------
# Local imports
# --------------------------------------------------------------------------
from core.tasks import DatabaseManager
from core.notifier import NotificationManager
from ui.main_window import MainWindow, load_settings, DARK_QSS


def main() -> int:
    """Application entry point. Returns exit code."""

    # ------------------------------------------------------------------
    # Create QApplication
    # ------------------------------------------------------------------
    app = QApplication(sys.argv)
    app.setApplicationName("Taskmaster")
    app.setApplicationDisplayName("Taskmaster")
    app.setOrganizationName("Antigravity")
    app.setOrganizationDomain("antigravity.local")

    # ------------------------------------------------------------------
    # Single instance lock (prevent multiple instances)
    # ------------------------------------------------------------------
    server_name = "Taskmaster_SingleInstance_App_Server"
    check_socket = QLocalSocket()
    check_socket.connectToServer(server_name)
    if check_socket.waitForConnected(400):
        logger.info("Otra instancia de Taskmaster ya está abierta. Activando la ventana existente...")
        check_socket.write(b"ACTIVATE")
        check_socket.waitForBytesWritten(400)
        check_socket.disconnectFromServer()
        return 0

    # Ensure stale server is removed and start listening
    QLocalServer.removeServer(server_name)
    local_server = QLocalServer()
    if not local_server.listen(server_name):
        logger.warning("No se pudo iniciar el servidor local de instancia única.")

    # Enable High-DPI scaling
    app.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # ------------------------------------------------------------------
    # Load settings
    # ------------------------------------------------------------------
    settings = load_settings()

    # ------------------------------------------------------------------
    # Apply initial stylesheet (dark Taskmaster by default)
    # ------------------------------------------------------------------
    from ui.tokens import TASKMASTER_QSS
    app.setStyleSheet(TASKMASTER_QSS)

    # ------------------------------------------------------------------
    # Global font
    # ------------------------------------------------------------------
    font = QFont("Manrope", 10)
    font.setStyleHint(QFont.StyleHint.SansSerif)
    app.setFont(font)

    # ------------------------------------------------------------------
    # Application icon
    # ------------------------------------------------------------------
    icon_path = os.path.join(os.path.dirname(__file__), "assets", "icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    else:
        # Use a built-in Qt icon as fallback
        app.setWindowIcon(
            app.style().standardIcon(app.style().StandardPixmap.SP_ComputerIcon)
        )

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------
    logger.info("Opening database…")
    db = DatabaseManager()

    # ------------------------------------------------------------------
    # Notification manager
    # ------------------------------------------------------------------
    logger.info("Starting notification manager…")
    notifier = NotificationManager(
        db=db,
        reminder_minutes=settings.get("reminder_minutes", 30),
        daily_summary_hour=settings.get("daily_summary_hour", 9),
        daily_summary_minute=settings.get("daily_summary_minute", 0),
    )
    notifier.set_enabled(settings.get("notifications_enabled", True))

    # ------------------------------------------------------------------
    # Main window
    # ------------------------------------------------------------------
    logger.info("Creating main window…")
    window = MainWindow(db=db, notifier=notifier, settings=settings)
    window.show()

    # ------------------------------------------------------------------
    # Bring window to front when another instance tries to open
    # ------------------------------------------------------------------
    def _on_single_instance_activate():
        conn = local_server.nextPendingConnection()
        if conn:
            conn.waitForReadyRead(200)
            conn.disconnectFromServer()
        if window.isMinimized():
            window.showNormal()
        window.show()
        window.raise_()
        window.activateWindow()

    local_server.newConnection.connect(_on_single_instance_activate)

    # ------------------------------------------------------------------
    # SIGINT (Ctrl+C from terminal) → graceful quit
    # ------------------------------------------------------------------
    def _sigint_handler(*_):
        logger.info("SIGINT received – shutting down…")
        window.quit_app()

    signal.signal(signal.SIGINT, _sigint_handler)

    # PyQt doesn't process Python signals unless the event loop yields;
    # a small periodic timer forces the interpreter to check for signals.
    sigint_timer = QTimer()
    sigint_timer.setInterval(200)
    sigint_timer.timeout.connect(lambda: None)  # just yield to Python
    sigint_timer.start()

    # ------------------------------------------------------------------
    # Schedule reminders for all existing tasks with due dates
    # ------------------------------------------------------------------
    try:
        for task in db.get_all_tasks(include_completed=False):
            if task.get("due_date"):
                notifier.schedule_reminder(task)
    except Exception as exc:
        logger.warning("Could not pre-schedule reminders: %s", exc)

    # ------------------------------------------------------------------
    # Run event loop
    # ------------------------------------------------------------------
    logger.info("TaskVoice started.")
    exit_code = app.exec()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    local_server.close()
    QLocalServer.removeServer(server_name)
    notifier.shutdown()
    db.close()
    logger.info("TaskVoice exited with code %d.", exit_code)
    return exit_code



if __name__ == "__main__":
    sys.exit(main())
