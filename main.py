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
    app.setApplicationName("TaskVoice")
    app.setApplicationDisplayName("TaskVoice")
    app.setOrganizationName("Antigravity")
    app.setOrganizationDomain("antigravity.local")

    # Enable High-DPI scaling
    app.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # ------------------------------------------------------------------
    # Load settings
    # ------------------------------------------------------------------
    settings = load_settings()

    # ------------------------------------------------------------------
    # Apply initial stylesheet (dark by default)
    # ------------------------------------------------------------------
    from ui.main_window import DARK_QSS, LIGHT_QSS
    qss = DARK_QSS if settings.get("theme", "dark") == "dark" else LIGHT_QSS
    app.setStyleSheet(qss)

    # ------------------------------------------------------------------
    # Global font
    # ------------------------------------------------------------------
    font = QFont("Segoe UI", 10)
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
    notifier.shutdown()
    db.close()
    logger.info("TaskVoice exited with code %d.", exit_code)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
