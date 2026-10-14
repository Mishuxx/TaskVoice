"""
core/notifier.py
================
Desktop notification manager for TaskVoice.

Uses `plyer` as the primary notification backend.
Falls back to `win10toast` if plyer is not available.
Schedules task reminders and a daily summary using APScheduler.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Callable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Notification backends
# ---------------------------------------------------------------------------

def _notify_plyer(title: str, message: str, timeout: int = 10) -> bool:
    """Send notification via plyer. Returns True on success."""
    try:
        from plyer import notification  # type: ignore
        notification.notify(
            title=title,
            message=message,
            app_name="TaskVoice",
            timeout=timeout,
        )
        return True
    except Exception as exc:
        logger.debug("plyer notification failed: %s", exc)
        return False


def _notify_win10toast(title: str, message: str, timeout: int = 10) -> bool:
    """Send notification via win10toast. Returns True on success."""
    try:
        from win10toast import ToastNotifier  # type: ignore
        toaster = ToastNotifier()
        toaster.show_toast(
            title,
            message,
            duration=timeout,
            threaded=True,
        )
        return True
    except Exception as exc:
        logger.debug("win10toast notification failed: %s", exc)
        return False


def send_notification(title: str, message: str, timeout: int = 10) -> None:
    """
    Send a desktop notification using the best available backend.
    Tries plyer first, then win10toast. Logs a warning if both fail.
    """
    if _notify_plyer(title, message, timeout):
        return
    if _notify_win10toast(title, message, timeout):
        return
    logger.warning(
        "No notification backend available. Notification dropped: [%s] %s",
        title, message,
    )


# ===========================================================================
# NotificationManager
# ===========================================================================

class NotificationManager:
    """
    Manages scheduled reminders and the daily summary.

    Parameters
    ----------
    db : DatabaseManager
        Database instance used to query tasks and stats.
    reminder_minutes : int
        How many minutes before a task's due date to send a reminder.
    daily_summary_hour : int
        Hour (24h) at which to send the daily summary.
    daily_summary_minute : int
        Minute at which to send the daily summary.
    """

    def __init__(
        self,
        db,
        reminder_minutes: int = 30,
        daily_summary_hour: int = 9,
        daily_summary_minute: int = 0,
    ):
        self._db = db
        self.reminder_minutes = reminder_minutes
        self.daily_summary_hour = daily_summary_hour
        self.daily_summary_minute = daily_summary_minute
        self._scheduler = None
        self._scheduled_reminders: Dict[int, str] = {}  # task_id -> job_id
        self._enabled = True
        self._init_scheduler()

    # ------------------------------------------------------------------
    # Scheduler setup
    # ------------------------------------------------------------------

    def _init_scheduler(self) -> None:
        """Initialise APScheduler BackgroundScheduler."""
        try:
            from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore
            from apscheduler.triggers.cron import CronTrigger                  # type: ignore
            from apscheduler.triggers.interval import IntervalTrigger          # type: ignore

            self._scheduler = BackgroundScheduler(
                job_defaults={"misfire_grace_time": 60},
                timezone="local",
            )

            # Check for due-soon tasks every minute
            self._scheduler.add_job(
                self._check_due_tasks,
                trigger=IntervalTrigger(minutes=1),
                id="check_due_tasks",
                replace_existing=True,
            )

            # Daily summary
            self._scheduler.add_job(
                self.daily_summary,
                trigger=CronTrigger(
                    hour=self.daily_summary_hour,
                    minute=self.daily_summary_minute,
                ),
                id="daily_summary",
                replace_existing=True,
            )

            self._scheduler.start()
            logger.info("APScheduler started.")
        except ImportError:
            logger.warning(
                "APScheduler not installed. Scheduled notifications will not work."
            )
        except Exception as exc:
            logger.error("Failed to start scheduler: %s", exc)

    # ------------------------------------------------------------------
    # Per-task reminders
    # ------------------------------------------------------------------

    def schedule_reminder(self, task: Dict[str, Any]) -> None:
        """
        Schedule a one-shot reminder for a task.
        Fires *reminder_minutes* before due_date.
        """
        if not self._enabled or self._scheduler is None:
            return
        task_id = task.get("id")
        due_date_str = task.get("due_date")
        if not task_id or not due_date_str:
            return

        try:
            due_dt = datetime.fromisoformat(due_date_str)
        except ValueError:
            logger.debug("Could not parse due_date '%s'", due_date_str)
            return

        fire_at = due_dt - timedelta(minutes=self.reminder_minutes)
        if fire_at <= datetime.now():
            return  # already past

        job_id = f"reminder_{task_id}"
        try:
            from apscheduler.triggers.date import DateTrigger  # type: ignore
            self._scheduler.add_job(
                self._send_task_reminder,
                trigger=DateTrigger(run_date=fire_at),
                args=[task],
                id=job_id,
                replace_existing=True,
            )
            self._scheduled_reminders[task_id] = job_id
            logger.debug("Reminder scheduled for task %d at %s", task_id, fire_at)
        except Exception as exc:
            logger.error("Failed to schedule reminder: %s", exc)

    def cancel_reminder(self, task_id: int) -> None:
        """Cancel a previously scheduled reminder for a task."""
        job_id = self._scheduled_reminders.pop(task_id, None)
        if job_id and self._scheduler:
            try:
                self._scheduler.remove_job(job_id)
                logger.debug("Reminder cancelled for task %d", task_id)
            except Exception:
                pass

    def _send_task_reminder(self, task: Dict[str, Any]) -> None:
        """Called by APScheduler to send the actual reminder notification."""
        title = f"⏰ Recordatorio: {task.get('title', 'Tarea')}"
        due = task.get("due_date", "")
        message = f"Vence en {self.reminder_minutes} min" + (f" ({due})" if due else "")
        send_notification(title, message)

    # ------------------------------------------------------------------
    # Periodic check
    # ------------------------------------------------------------------

    def _check_due_tasks(self) -> None:
        """Periodically called to find tasks due soon and send notifications."""
        if not self._enabled:
            return
        try:
            tasks = self._db.get_tasks_due_soon(self.reminder_minutes)
            for task in tasks:
                tid = task["id"]
                # Only notify once per check cycle (guard with scheduled reminders)
                if tid not in self._scheduled_reminders:
                    self._send_task_reminder(task)
                    # Mark as notified until restart
                    self._scheduled_reminders[tid] = f"notified_{tid}"
        except Exception as exc:
            logger.error("Error checking due tasks: %s", exc)

    # ------------------------------------------------------------------
    # Daily summary
    # ------------------------------------------------------------------

    def daily_summary(self) -> None:
        """Send a daily summary notification with task statistics."""
        if not self._enabled:
            return
        try:
            stats = self._db.get_stats()
            active = stats.get("active", 0)
            completed_today = stats.get("completed_today", 0)
            overdue = stats.get("overdue", 0)
            message = (
                f"Tareas activas: {active}\n"
                f"Completadas hoy: {completed_today}\n"
                f"Vencidas: {overdue}"
            )
            send_notification("📋 Resumen diario – TaskVoice", message, timeout=15)
        except Exception as exc:
            logger.error("Error generating daily summary: %s", exc)

    # ------------------------------------------------------------------
    # Settings update
    # ------------------------------------------------------------------

    def update_schedule(
        self,
        daily_hour: Optional[int] = None,
        daily_minute: Optional[int] = None,
        reminder_minutes: Optional[int] = None,
    ) -> None:
        """Update scheduler settings at runtime."""
        if daily_hour is not None:
            self.daily_summary_hour = daily_hour
        if daily_minute is not None:
            self.daily_summary_minute = daily_minute
        if reminder_minutes is not None:
            self.reminder_minutes = reminder_minutes

        if self._scheduler is None:
            return
        try:
            from apscheduler.triggers.cron import CronTrigger  # type: ignore
            self._scheduler.reschedule_job(
                "daily_summary",
                trigger=CronTrigger(
                    hour=self.daily_summary_hour,
                    minute=self.daily_summary_minute,
                ),
            )
        except Exception as exc:
            logger.error("Failed to reschedule daily summary: %s", exc)

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable all notifications."""
        self._enabled = enabled

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def shutdown(self) -> None:
        """Gracefully shut down the scheduler."""
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("APScheduler shut down.")

    def __del__(self):
        self.shutdown()
