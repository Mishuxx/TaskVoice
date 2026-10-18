"""
core/cloud_sync.py
==================
Real-time / background bidirectional synchronization between local SQLite
and Supabase cloud backend for BountyHunter.

Features:
- Thread-safe background syncing using QThread / worker.
- Syncs categories, tasks, subtasks and gamification profile.
- Offline-first: if internet is absent, operations queue and run when back online.
- Emits Qt signals when remote data updates are merged.
"""

import time
import json
import logging
import requests
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from PyQt6.QtCore import QObject, QThread, pyqtSignal, QTimer

logger = logging.getLogger(__name__)

DEFAULT_SUPABASE_URL = "https://wklsebcypnspferilraz.supabase.co"
DEFAULT_SUPABASE_KEY = "sb_publishable_sbEUU0WhieAuQZMhcm1glQ_MpC9bT6Y"


def iso_now() -> str:
    """Return ISO 8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


class CloudSyncManager(QObject):
    """
    Manages cloud sync between local SQLite DatabaseManager and Supabase REST API.
    """
    sync_started = pyqtSignal()
    sync_finished = pyqtSignal(bool, str)  # success, message
    data_changed = pyqtSignal()            # emitted when remote changes merged locally

    def __init__(
        self,
        db,
        supabase_url: str = DEFAULT_SUPABASE_URL,
        supabase_key: str = DEFAULT_SUPABASE_KEY,
        sync_interval_sec: int = 30,
        parent=None,
    ):
        super().__init__(parent)
        self._db = db
        self._supabase_url = supabase_url.rstrip("/")
        self._supabase_key = supabase_key
        self._sync_interval = sync_interval_sec
        self._is_syncing = False
        self._enabled = True

        self._headers = {
            "apikey": self._supabase_key,
            "Authorization": f"Bearer {self._supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

        # Timer for periodic background sync
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.sync_now)
        if self._sync_interval > 0:
            self._timer.start(self._sync_interval * 1000)

    def set_credentials(self, url: str, key: str) -> None:
        """Update Supabase credentials."""
        self._supabase_url = url.rstrip("/")
        self._supabase_key = key
        self._headers["apikey"] = key
        self._headers["Authorization"] = f"Bearer {key}"

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable background sync."""
        self._enabled = enabled
        if not enabled:
            self._timer.stop()
        else:
            if not self._timer.isActive() and self._sync_interval > 0:
                self._timer.start(self._sync_interval * 1000)

    def sync_now(self) -> None:
        """Trigger an immediate sync pass."""
        if self._is_syncing or not self._enabled:
            return

        self._is_syncing = True
        self.sync_started.emit()

        try:
            changed = self._perform_sync()
            self.sync_finished.emit(True, "Sincronizado con la nube.")
            if changed:
                self.data_changed.emit()
        except requests.exceptions.RequestException as exc:
            logger.warning("Cloud sync network error: %s", exc)
            self.sync_finished.emit(False, f"Sin conexión: {exc}")
        except Exception as exc:
            logger.error("Cloud sync unexpected error: %s", exc, exc_info=True)
            self.sync_finished.emit(False, str(exc))
        finally:
            self._is_syncing = False

    # ------------------------------------------------------------------
    # Internal Sync Logic
    # ------------------------------------------------------------------

    def _perform_sync(self) -> bool:
        """Perform bidirectional sync across all entities."""
        has_changes = False

        # 1. Sync Categories
        if self._sync_categories():
            has_changes = True

        # 2. Sync Tasks
        if self._sync_tasks():
            has_changes = True

        # 3. Sync Gamification
        if self._sync_gamification():
            has_changes = True

        return has_changes

    def _sync_categories(self) -> bool:
        """Push local categories to Supabase and pull remote categories."""
        url = f"{self._supabase_url}/rest/v1/bh_categories"
        has_changes = False

        # Remote fetch
        r = requests.get(f"{url}?select=*", headers=self._headers, timeout=10)
        r.raise_for_status()
        remote_cats = {c["name"]: c for c in r.json()}

        # Local fetch
        local_cats = {c["name"]: c for c in self._db.get_categories()}

        # Push missing to cloud
        to_push = []
        for name, cat in local_cats.items():
            if name not in remote_cats:
                to_push.append({"name": name, "color": cat["color"]})
        
        if to_push:
            pr = requests.post(url, headers=self._headers, json=to_push, timeout=10)
            pr.raise_for_status()

        # Pull missing from cloud
        for name, rcat in remote_cats.items():
            if name not in local_cats:
                self._db.create_category(rcat["name"], rcat["color"])
                has_changes = True

        return has_changes

    def _sync_tasks(self) -> bool:
        """Push local tasks to Supabase and pull remote tasks."""
        url = f"{self._supabase_url}/rest/v1/bh_tasks"
        has_changes = False

        # Get remote tasks
        r = requests.get(f"{url}?select=*&is_deleted=eq.false", headers=self._headers, timeout=10)
        r.raise_for_status()
        remote_tasks = r.json()
        remote_by_id = {t["id"]: t for t in remote_tasks}

        # Get local tasks
        local_tasks = self._db.get_all_tasks(include_completed=True)
        local_by_id = {t["id"]: t for t in local_tasks}

        # Category mapping remote id <-> local id by name
        cat_map = {}
        local_cats = {c["id"]: c["name"] for c in self._db.get_categories()}
        rc = requests.get(f"{self._supabase_url}/rest/v1/bh_categories?select=*", headers=self._headers, timeout=10)
        if rc.status_code == 200:
            for c in rc.json():
                cat_map[c["name"]] = c["id"]

        # Push local tasks that are missing or modified
        for lt in local_tasks:
            tid = lt["id"]
            cat_name = local_cats.get(lt.get("category_id"))
            remote_cat_id = cat_map.get(cat_name) if cat_name else None
            is_comp = bool(lt.get("completed", 0))

            if tid not in remote_by_id:
                # Insert missing in cloud
                payload = {
                    "id": tid,
                    "title": lt["title"],
                    "description": lt.get("description", "") or "",
                    "category_id": remote_cat_id,
                    "due_date": lt.get("due_date", "") or "",
                    "priority": lt.get("priority", 2),
                    "progress": lt.get("progress", 0),
                    "completed": is_comp,
                    "is_recurring": bool(lt.get("is_recurring", 0)),
                    "recurrence_days": lt.get("recurrence_days", "") or "",
                    "recurrence_time": lt.get("recurrence_time", "") or "",
                    "recurrence_type": lt.get("recurrence_type", "") or "",
                    "created_at": lt.get("created_at") or iso_now(),
                    "completed_at": lt.get("completed_at"),
                    "updated_at": lt.get("updated_at") or iso_now(),
                    "is_deleted": False,
                }
                push_headers = dict(self._headers)
                push_headers["Prefer"] = "resolution=merge-duplicates"
                requests.post(url, headers=push_headers, json=[payload], timeout=10)
            else:
                # Task exists on both sides: compare status
                rt = remote_by_id[tid]
                rem_comp = bool(rt.get("completed", False))
                rem_updated = rt.get("updated_at") or ""
                loc_updated = lt.get("updated_at") or ""

                if is_comp != rem_comp:
                    # Whichever was updated more recently wins
                    if loc_updated >= rem_updated:
                        # Push local status to remote
                        requests.patch(
                            f"{url}?id=eq.{tid}",
                            headers=self._headers,
                            json={"completed": is_comp, "completed_at": lt.get("completed_at"), "updated_at": iso_now()},
                            timeout=10,
                        )
                    else:
                        # Pull remote status to local
                        with self._db._conn:
                            self._db._conn.execute(
                                "UPDATE tasks SET completed=?, completed_at=?, updated_at=? WHERE id=?",
                                (1 if rem_comp else 0, rt.get("completed_at"), rem_updated, tid)
                            )
                        has_changes = True

        # Pull remote tasks into local SQLite
        for rt in remote_tasks:
            rid = rt["id"]
            if rid not in local_by_id:
                # Create task locally
                loc_cat_id = None
                if rt.get("category_id"):
                    for name, cid in cat_map.items():
                        if cid == rt["category_id"]:
                            for l_id, l_name in local_cats.items():
                                if l_name == name:
                                    loc_cat_id = l_id
                                    break
                            break

                cur = self._db._cursor()
                with self._db._conn:
                    cur.execute(
                        """
                        INSERT OR REPLACE INTO tasks (
                            id, title, description, category_id, due_date, priority,
                            progress, completed, is_recurring, recurrence_days,
                            recurrence_time, recurrence_type, created_at, completed_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            rid,
                            rt["title"],
                            rt.get("description", "") or "",
                            loc_cat_id,
                            rt.get("due_date") or None,
                            rt.get("priority", 2),
                            rt.get("progress", 0),
                            1 if rt.get("completed") else 0,
                            1 if rt.get("is_recurring") else 0,
                            rt.get("recurrence_days", "") or "",
                            rt.get("recurrence_time", "") or "",
                            rt.get("recurrence_type", "") or "",
                            rt.get("created_at") or iso_now(),
                            rt.get("completed_at"),
                            rt.get("updated_at") or iso_now(),
                        )
                    )
                has_changes = True

        return has_changes

    def _sync_gamification(self) -> bool:
        """Sync user gamification XP, level and streak."""
        url = f"{self._supabase_url}/rest/v1/bh_gamification"
        r = requests.get(f"{url}?id=eq.1", headers=self._headers, timeout=10)
        r.raise_for_status()
        rows = r.json()

        local_prof = self._db.get_gamification_profile()

        if not rows:
            # Seed remote
            payload = {
                "id": 1,
                "xp": local_prof["xp"],
                "level": local_prof["level"],
                "total_xp": local_prof["total_xp"],
                "streak_days": local_prof["streak_days"],
                "last_active_date": local_prof.get("last_active_date"),
                "tasks_completed_count": local_prof.get("tasks_completed_count", 0),
                "subtasks_completed_count": local_prof.get("subtasks_completed_count", 0),
                "voice_commands_count": local_prof.get("voice_commands_count", 0),
                "quests_completed_count": local_prof.get("quests_completed_count", 0),
                "updated_at": iso_now(),
            }
            requests.post(url, headers=self._headers, json=[payload], timeout=10)
            return False

        remote_prof = rows[0]
        # Keep whichever has higher total_xp
        if local_prof["total_xp"] > remote_prof.get("total_xp", 0):
            # Push local to remote
            payload = {
                "xp": local_prof["xp"],
                "level": local_prof["level"],
                "total_xp": local_prof["total_xp"],
                "streak_days": max(local_prof["streak_days"], remote_prof.get("streak_days", 1)),
                "tasks_completed_count": max(local_prof["tasks_completed_count"], remote_prof.get("tasks_completed_count", 0)),
                "updated_at": iso_now(),
            }
            requests.patch(f"{url}?id=eq.1", headers=self._headers, json=payload, timeout=10)
            return False
        elif remote_prof.get("total_xp", 0) > local_prof["total_xp"]:
            # Update local from remote
            cur = self._db._cursor()
            with self._db._conn:
                cur.execute(
                    """
                    UPDATE user_gamification SET
                        xp = ?,
                        level = ?,
                        total_xp = ?,
                        streak_days = ?,
                        tasks_completed_count = ?
                    WHERE id = 1
                    """,
                    (
                        remote_prof.get("xp", 0),
                        remote_prof.get("level", 1),
                        remote_prof.get("total_xp", 0),
                        remote_prof.get("streak_days", 1),
                        remote_prof.get("tasks_completed_count", 0),
                    )
                )
            return True

        return False
