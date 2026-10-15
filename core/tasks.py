"""
core/tasks.py
=============
SQLite database layer for TaskVoice.
Handles all CRUD operations for tasks, subtasks, categories and task history.
"""

import sqlite3
import os
import json
from datetime import datetime, date
from pathlib import Path
from typing import Optional, List, Dict, Any, Union

from core.categorizer import deduce_category_name
from core.recurrence import (
    calculate_next_occurrence, parse_recurrence_days,
    serialize_recurrence_days, parse_recurrence_times,
    serialize_recurrence_times, format_recurrence_badge,
)


# ---------------------------------------------------------------------------
# Database path
# ---------------------------------------------------------------------------
DB_DIR = Path.home() / ".taskvoice"
DB_PATH = DB_DIR / "tasks.db"

# ---------------------------------------------------------------------------
# Default categories (name, hex-color)
# ---------------------------------------------------------------------------
DEFAULT_CATEGORIES = [
    ("Estudio",   "#60A5FA"),
    ("Personal",  "#C084FC"),
    ("Salud",     "#34D399"),
    ("Trabajo",   "#F59E0B"),
]


# ---------------------------------------------------------------------------
# Helper: dataclass-like dicts
# ---------------------------------------------------------------------------

def _row_to_dict(cursor: sqlite3.Cursor, row: sqlite3.Row) -> Dict[str, Any]:
    """Convert a sqlite3.Row to a plain dictionary."""
    return dict(row)


# ===========================================================================
# DatabaseManager
# ===========================================================================

class DatabaseManager:
    """
    Manages the SQLite connection and all schema operations.

    Usage::

        db = DatabaseManager()
        tasks = db.get_all_tasks()
    """

    def __init__(self, db_path: Union[Path, str] = DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._connect()
        self._create_schema()
        self._seed_categories()
        self._seed_gamification()

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _connect(self) -> None:
        """Open (or reopen) the SQLite connection."""
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")

    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass

    def _cursor(self) -> sqlite3.Cursor:
        return self._conn.cursor()

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------
    # Schema creation
    # ------------------------------------------------------------------

    def _create_schema(self) -> None:
        """Create all tables if they do not exist."""
        sql = """
        CREATE TABLE IF NOT EXISTS categories (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL UNIQUE,
            color      TEXT NOT NULL DEFAULT '#7c3aed'
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            title            TEXT NOT NULL,
            description      TEXT DEFAULT '',
            category_id      INTEGER REFERENCES categories(id) ON DELETE SET NULL,
            due_date         TEXT,
            priority         INTEGER NOT NULL DEFAULT 2 CHECK(priority BETWEEN 1 AND 3),
            progress         INTEGER NOT NULL DEFAULT 0 CHECK(progress BETWEEN 0 AND 100),
            completed        INTEGER NOT NULL DEFAULT 0,
            is_recurring     INTEGER NOT NULL DEFAULT 0,
            recurrence_days  TEXT DEFAULT '',
            recurrence_time  TEXT DEFAULT '',
            recurrence_type  TEXT DEFAULT '',
            created_at       TEXT NOT NULL,
            completed_at     TEXT
        );

        CREATE TABLE IF NOT EXISTS subtasks (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id   INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            title     TEXT NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS task_history (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            original_id  INTEGER NOT NULL,
            title        TEXT NOT NULL,
            description  TEXT DEFAULT '',
            category_id  INTEGER,
            due_date     TEXT,
            priority     INTEGER,
            progress     INTEGER,
            created_at   TEXT,
            completed_at TEXT,
            archived_at  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS user_gamification (
            id                       INTEGER PRIMARY KEY CHECK(id = 1),
            xp                       INTEGER NOT NULL DEFAULT 0,
            level                    INTEGER NOT NULL DEFAULT 1,
            total_xp                 INTEGER NOT NULL DEFAULT 0,
            streak_days              INTEGER NOT NULL DEFAULT 1,
            last_active_date         TEXT,
            tasks_completed_count    INTEGER NOT NULL DEFAULT 0,
            subtasks_completed_count INTEGER NOT NULL DEFAULT 0,
            voice_commands_count     INTEGER NOT NULL DEFAULT 0,
            quests_completed_count   INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS gamification_quests (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            quest_key     TEXT NOT NULL,
            title         TEXT NOT NULL,
            description   TEXT NOT NULL,
            faction       TEXT NOT NULL DEFAULT 'Comando Terran',
            target_type   TEXT NOT NULL,
            target_count  INTEGER NOT NULL,
            current_count INTEGER NOT NULL DEFAULT 0,
            xp_reward     INTEGER NOT NULL,
            completed     INTEGER NOT NULL DEFAULT 0,
            claimed       INTEGER NOT NULL DEFAULT 0,
            quest_date    TEXT NOT NULL,
            icon          TEXT NOT NULL DEFAULT '🎯'
        );
        """
        with self._conn:
            self._conn.executescript(sql)

        # Migration: ensure new recurrence columns exist for existing databases
        migration_cols = [
            ("is_recurring", "INTEGER NOT NULL DEFAULT 0"),
            ("recurrence_days", "TEXT DEFAULT ''"),
            ("recurrence_time", "TEXT DEFAULT ''"),
            ("recurrence_type", "TEXT DEFAULT ''"),
        ]
        with self._conn:
            for col_name, col_type in migration_cols:
                try:
                    self._conn.execute(f"ALTER TABLE tasks ADD COLUMN {col_name} {col_type}")
                except sqlite3.OperationalError:
                    pass

    # ------------------------------------------------------------------
    # Seed default categories
    # ------------------------------------------------------------------

    def _seed_categories(self) -> None:
        """Insert default categories if the table is empty."""
        cur = self._cursor()
        cur.execute("SELECT COUNT(*) FROM categories")
        if cur.fetchone()[0] == 0:
            with self._conn:
                self._conn.executemany(
                    "INSERT INTO categories (name, color) VALUES (?, ?)",
                    DEFAULT_CATEGORIES
                )
        else:
            with self._conn:
                for name, col in DEFAULT_CATEGORIES:
                    self._conn.execute("UPDATE categories SET color = ? WHERE name = ?", (col, name))

    def _seed_gamification(self) -> None:
        """Insert default gamification user profile if empty."""
        cur = self._cursor()
        cur.execute("SELECT COUNT(*) FROM user_gamification WHERE id = 1")
        if cur.fetchone()[0] == 0:
            today_str = date.today().isoformat()
            with self._conn:
                self._conn.execute(
                    """
                    INSERT INTO user_gamification (
                        id, xp, level, total_xp, streak_days, last_active_date,
                        tasks_completed_count, subtasks_completed_count,
                        voice_commands_count, quests_completed_count
                    ) VALUES (1, 0, 1, 0, 1, ?, 0, 0, 0, 0)
                    """,
                    (today_str,)
                )

    # ==================================================================
    # CATEGORIES
    # ==================================================================

    def get_categories(self) -> List[Dict[str, Any]]:
        """Return all categories as a list of dicts."""
        cur = self._cursor()
        cur.execute("SELECT id, name, color FROM categories ORDER BY name")
        return [dict(row) for row in cur.fetchall()]

    def add_category(self, name: str, color: str = "#7c3aed") -> int:
        """Insert a new category and return its id."""
        with self._conn:
            cur = self._conn.execute(
                "INSERT INTO categories (name, color) VALUES (?, ?)", (name, color)
            )
            return cur.lastrowid

    def update_category(self, category_id: int, name: str, color: str) -> None:
        """Update an existing category."""
        with self._conn:
            self._conn.execute(
                "UPDATE categories SET name=?, color=? WHERE id=?",
                (name, color, category_id)
            )

    def delete_category(self, category_id: int) -> None:
        """Delete a category (tasks become uncategorised)."""
        with self._conn:
            self._conn.execute(
                "UPDATE tasks SET category_id=NULL WHERE category_id=?",
                (category_id,)
            )
            self._conn.execute("DELETE FROM categories WHERE id=?", (category_id,))

    # ==================================================================
    # TASKS
    # ==================================================================

    def get_all_tasks(
        self,
        category_id: Optional[int] = None,
        include_completed: bool = False,
        search: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Return tasks with an optional category filter, completion filter,
        and a title/description search term.
        """
        params: List[Any] = []
        conditions: List[str] = []

        if not include_completed:
            conditions.append("t.completed = 0")

        if category_id is not None:
            conditions.append("t.category_id = ?")
            params.append(category_id)

        if search:
            conditions.append("(t.title LIKE ? OR t.description LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])

        where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        sql = f"""
            SELECT t.*, c.name AS category_name, c.color AS category_color
            FROM tasks t
            LEFT JOIN categories c ON t.category_id = c.id
            {where_clause}
            ORDER BY
                t.completed ASC,
                t.priority DESC,
                t.due_date ASC NULLS LAST,
                t.created_at DESC
        """
        cur = self._cursor()
        cur.execute(sql, params)
        return [dict(row) for row in cur.fetchall()]

    def get_task(self, task_id: int) -> Optional[Dict[str, Any]]:
        """Return a single task by id, or None if not found."""
        cur = self._cursor()
        cur.execute(
            """
            SELECT t.*, c.name AS category_name, c.color AS category_color
            FROM tasks t
            LEFT JOIN categories c ON t.category_id = c.id
            WHERE t.id = ?
            """,
            (task_id,)
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def deduce_or_create_category(self, text: str) -> Optional[int]:
        """
        Deduce the category from text (title + description).
        If deduced as 'Hogar' (or any standard category) and it doesn't exist,
        automatically creates it and returns its id.
        """
        cat_name = deduce_category_name(text)
        if not cat_name:
            return None

        cur = self._cursor()
        cur.execute("SELECT id FROM categories WHERE LOWER(name) = LOWER(?)", (cat_name,))
        row = cur.fetchone()
        if row:
            return row["id"]

        # Category doesn't exist yet in the database -> create it automatically
        color_map = {
            "Trabajo": "#F59E0B",
            "Hogar": "#FB7185",
            "Salud": "#34D399",
            "Estudio": "#60A5FA",
            "Personal": "#C084FC",
        }
        color = color_map.get(cat_name, "#FB7185")
        return self.add_category(cat_name, color)

    def add_task(
        self,
        title: str,
        description: str = "",
        category_id: Optional[int] = None,
        due_date: Optional[str] = None,
        priority: int = 2,
        is_recurring: bool = False,
        recurrence_days: Optional[Union[List[int], str]] = None,
        recurrence_time: Optional[str] = None,
        recurrence_type: Optional[str] = None,
    ) -> int:
        """
        Insert a new task and return its id.
        If category_id is None, automatically deduces it from title and description.
        If is_recurring is True, calculates next recurrence due_date if not specified.
        """
        if category_id is None:
            category_id = self.deduce_or_create_category(f"{title} {description}".strip())

        r_days_str = serialize_recurrence_days(parse_recurrence_days(recurrence_days)) if is_recurring else ""
        r_time_str = serialize_recurrence_times(parse_recurrence_times(recurrence_time)) if is_recurring else ""
        r_type_str = (recurrence_type or "daily") if is_recurring else ""

        if is_recurring and not due_date:
            next_dt = calculate_next_occurrence(recurrence_days, r_time_str)
            due_date = next_dt.isoformat(sep=" ", timespec="seconds")

        now = datetime.now().isoformat(sep=" ", timespec="seconds")
        with self._conn:
            cur = self._conn.execute(
                """
                INSERT INTO tasks
                    (title, description, category_id, due_date, priority, progress, completed,
                     is_recurring, recurrence_days, recurrence_time, recurrence_type, created_at)
                VALUES (?, ?, ?, ?, ?, 0, 0, ?, ?, ?, ?, ?)
                """,
                (
                    title, description, category_id, due_date, priority,
                    1 if is_recurring else 0, r_days_str, r_time_str, r_type_str, now
                )
            )
            return cur.lastrowid

    def update_task(
        self,
        task_id: int,
        title: Optional[str] = None,
        description: Optional[str] = None,
        category_id: Optional[int] = None,
        due_date: Optional[str] = None,
        priority: Optional[int] = None,
        is_recurring: Optional[bool] = None,
        recurrence_days: Optional[Union[List[int], str]] = None,
        recurrence_time: Optional[Union[str, List[str]]] = None,
        recurrence_type: Optional[str] = None,
    ) -> None:
        """Partially update a task's fields."""
        task = self.get_task(task_id)
        if task is None:
            return

        new_is_rec = 1 if (is_recurring if is_recurring is not None else task.get("is_recurring", 0)) else 0
        new_r_days = serialize_recurrence_days(parse_recurrence_days(recurrence_days)) if recurrence_days is not None else task.get("recurrence_days", "")
        new_r_time = serialize_recurrence_times(parse_recurrence_times(recurrence_time)) if recurrence_time is not None else task.get("recurrence_time", "")
        new_r_type = recurrence_type if recurrence_type is not None else task.get("recurrence_type", "")

        if due_date is not None:
            new_due = due_date if due_date != "" else None
        else:
            new_due = task["due_date"]
        if new_is_rec and not new_due:
            new_due = calculate_next_occurrence(new_r_days, new_r_time).isoformat(sep=" ", timespec="seconds")

        with self._conn:
            self._conn.execute(
                """
                UPDATE tasks
                SET title=?, description=?, category_id=?, due_date=?, priority=?,
                    is_recurring=?, recurrence_days=?, recurrence_time=?, recurrence_type=?
                WHERE id=?
                """,
                (
                    title if title is not None else task["title"],
                    description if description is not None else task["description"],
                    category_id if category_id is not None else task["category_id"],
                    new_due,
                    priority if priority is not None else task["priority"],
                    new_is_rec,
                    new_r_days,
                    new_r_time,
                    new_r_type,
                    task_id,
                )
            )

    def complete_task(self, task_id: int) -> Dict[str, Any]:
        """
        Mark a task as completed.
        If it is a recurring task, archives the instance to task_history,
        calculates the next due date/time according to recurrence rules,
        and rolls the task over to the next cycle.
        """
        task = self.get_task(task_id)
        if not task:
            return {"success": False}

        now = datetime.now().isoformat(sep=" ", timespec="seconds")

        # Archive into task_history
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO task_history
                    (original_id, title, description, category_id, due_date,
                     priority, progress, created_at, completed_at, archived_at)
                VALUES (?, ?, ?, ?, ?, ?, 100, ?, ?, ?)
                """,
                (
                    task["id"], task["title"], task["description"],
                    task["category_id"], task["due_date"], task["priority"],
                    task["created_at"], now, now
                )
            )

        if task.get("is_recurring"):
            days = parse_recurrence_days(task.get("recurrence_days"))
            r_time = task.get("recurrence_time") or "09:00"
            now_dt = datetime.now()
            base_dt = now_dt
            if task.get("due_date"):
                try:
                    dt = datetime.fromisoformat(task["due_date"])
                    if dt.date() == now_dt.date() or dt > now_dt:
                        base_dt = dt
                    else:
                        base_dt = datetime.combine(now_dt.date(), datetime.min.time())
                except Exception:
                    pass
            next_dt = calculate_next_occurrence(days, r_time, from_dt=base_dt)
            next_due = next_dt.isoformat(sep=" ", timespec="seconds")

            with self._conn:
                self._conn.execute(
                    """
                    UPDATE tasks
                    SET completed=0, progress=0, completed_at=NULL, due_date=?
                    WHERE id=?
                    """,
                    (next_due, task_id)
                )
                self._conn.execute(
                    "UPDATE subtasks SET completed=0 WHERE task_id=?",
                    (task_id,)
                )
            return {
                "success": True,
                "was_recurring": True,
                "next_due": next_due,
                "title": task["title"],
            }
        else:
            with self._conn:
                self._conn.execute(
                    "UPDATE tasks SET completed=1, progress=100, completed_at=? WHERE id=?",
                    (now, task_id)
                )
            return {
                "success": True,
                "was_recurring": False,
                "title": task["title"],
            }

    def uncomplete_task(self, task_id: int) -> None:
        """Mark a task as not completed."""
        with self._conn:
            self._conn.execute(
                "UPDATE tasks SET completed=0, completed_at=NULL WHERE id=?",
                (task_id,)
            )
        self._recalc_progress(task_id)

    def delete_task(self, task_id: int) -> None:
        """Permanently delete a task and its subtasks."""
        with self._conn:
            self._conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))

    def archive_completed_tasks(self) -> int:
        """
        Move all completed tasks to task_history.
        Returns the number of tasks archived.
        """
        cur = self._cursor()
        cur.execute("SELECT * FROM tasks WHERE completed=1")
        rows = [dict(r) for r in cur.fetchall()]
        if not rows:
            return 0
        now = datetime.now().isoformat(sep=" ", timespec="seconds")
        with self._conn:
            self._conn.executemany(
                """
                INSERT INTO task_history
                    (original_id, title, description, category_id, due_date,
                     priority, progress, created_at, completed_at, archived_at)
                VALUES (:id, :title, :description, :category_id, :due_date,
                        :priority, :progress, :created_at, :completed_at, ?)
                """,
                [{**r, "?": now} for r in rows],
            )
            self._conn.execute("DELETE FROM tasks WHERE completed=1")
        return len(rows)

    # ------------------------------------------------------------------
    # Progress recalculation
    # ------------------------------------------------------------------

    def _recalc_progress(self, task_id: int) -> None:
        """
        Recompute the task progress (0-100) based on subtask completion.
        If no subtasks exist, progress is unchanged.
        """
        cur = self._cursor()
        cur.execute(
            "SELECT COUNT(*) AS total, SUM(completed) AS done FROM subtasks WHERE task_id=?",
            (task_id,)
        )
        row = dict(cur.fetchone())
        total = row["total"] or 0
        done = int(row["done"] or 0)
        if total == 0:
            return
        progress = round((done / total) * 100)
        with self._conn:
            self._conn.execute(
                "UPDATE tasks SET progress=? WHERE id=?", (progress, task_id)
            )

    # ==================================================================
    # SUBTASKS
    # ==================================================================

    def get_subtasks(self, task_id: int) -> List[Dict[str, Any]]:
        """Return all subtasks for a given task."""
        cur = self._cursor()
        cur.execute(
            "SELECT * FROM subtasks WHERE task_id=? ORDER BY id", (task_id,)
        )
        return [dict(r) for r in cur.fetchall()]

    def add_subtask(self, task_id: int, title: str) -> int:
        """Add a subtask to a task and return its id."""
        with self._conn:
            cur = self._conn.execute(
                "INSERT INTO subtasks (task_id, title, completed) VALUES (?, ?, 0)",
                (task_id, title)
            )
            return cur.lastrowid

    def update_subtask(self, subtask_id: int, title: Optional[str] = None, completed: Optional[bool] = None) -> None:
        """Update a subtask's title and/or completion status."""
        cur = self._cursor()
        cur.execute("SELECT * FROM subtasks WHERE id=?", (subtask_id,))
        row = cur.fetchone()
        if row is None:
            return
        row = dict(row)
        new_title = title if title is not None else row["title"]
        new_completed = int(completed) if completed is not None else row["completed"]
        with self._conn:
            self._conn.execute(
                "UPDATE subtasks SET title=?, completed=? WHERE id=?",
                (new_title, new_completed, subtask_id)
            )
        self._recalc_progress(row["task_id"])

    def complete_subtask(self, subtask_id: int, completed: bool = True) -> None:
        """Toggle subtask completion and recalculate parent task progress."""
        cur = self._cursor()
        cur.execute("SELECT task_id FROM subtasks WHERE id=?", (subtask_id,))
        row = cur.fetchone()
        if row is None:
            return
        task_id = row["task_id"]
        with self._conn:
            self._conn.execute(
                "UPDATE subtasks SET completed=? WHERE id=?", (int(completed), subtask_id)
            )
        self._recalc_progress(task_id)

    def delete_subtask(self, subtask_id: int) -> None:
        """Delete a subtask and recalculate parent task progress."""
        cur = self._cursor()
        cur.execute("SELECT task_id FROM subtasks WHERE id=?", (subtask_id,))
        row = cur.fetchone()
        if row is None:
            return
        task_id = row["task_id"]
        with self._conn:
            self._conn.execute("DELETE FROM subtasks WHERE id=?", (subtask_id,))
        self._recalc_progress(task_id)

    # ==================================================================
    # HISTORY
    # ==================================================================

    def get_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Return archived tasks ordered by archived_at descending."""
        cur = self._cursor()
        cur.execute(
            "SELECT * FROM task_history ORDER BY archived_at DESC LIMIT ?", (limit,)
        )
        return [dict(r) for r in cur.fetchall()]

    def reset_completed_tasks(self) -> int:
        """
        Archive and remove all completed tasks, resetting active metrics.
        Returns count of archived tasks.
        """
        with self._conn:
            cur = self._cursor()
            cur.execute("SELECT * FROM tasks WHERE completed=1")
            done_tasks = cur.fetchall()
            now = datetime.now().isoformat(sep=" ", timespec="seconds")
            for t in done_tasks:
                self._conn.execute(
                    """
                    INSERT INTO task_history
                        (original_id, title, description, category_id, due_date,
                         priority, progress, created_at, completed_at, archived_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        t["id"], t["title"], t["description"], t["category_id"],
                        t["due_date"], t["priority"], t["progress"],
                        t["created_at"], t["completed_at"], now,
                    ),
                )
            self._conn.execute("DELETE FROM tasks WHERE completed=1")
            return len(done_tasks)

    def reset_all_data(self) -> None:
        """
        Completely reset all tasks, subtasks and history to start fresh from zero.
        Categories are preserved.
        """
        with self._conn:
            self._conn.execute("DELETE FROM subtasks")
            self._conn.execute("DELETE FROM tasks")
            self._conn.execute("DELETE FROM task_history")


    # ==================================================================
    # STATS
    # ==================================================================

    def get_stats(self) -> Dict[str, int]:
        """Return a quick summary of task counts."""
        cur = self._cursor()
        cur.execute("SELECT COUNT(*) FROM tasks WHERE completed=0")
        active = cur.fetchone()[0]

        today = date.today().isoformat()
        cur.execute(
            "SELECT COUNT(*) FROM tasks WHERE completed=1 AND DATE(completed_at)=?",
            (today,)
        )
        completed_today = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM tasks")
        total = cur.fetchone()[0]

        cur.execute(
            "SELECT COUNT(*) FROM tasks WHERE completed=0 AND due_date IS NOT NULL AND due_date < ?",
            (datetime.now().isoformat(sep=" ", timespec="seconds"),)
        )
        overdue = cur.fetchone()[0]

        return {
            "total": total,
            "active": active,
            "completed_today": completed_today,
            "overdue": overdue,
        }

    def get_dashboard_data(self) -> Dict[str, Any]:
        """
        Return comprehensive statistical and analytical metrics for the visual dashboard.
        """
        from datetime import datetime, date, timedelta
        cur = self._cursor()
        now_str = datetime.now().isoformat(sep=" ", timespec="seconds")
        today_str = date.today().isoformat()

        # Summary KPIs
        cur.execute("SELECT COUNT(*) FROM tasks")
        total_tasks = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM tasks WHERE completed=0")
        active_tasks = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM tasks WHERE completed=1")
        completed_tasks = cur.fetchone()[0]

        cur.execute(
            "SELECT COUNT(*) FROM tasks WHERE completed=0 AND due_date IS NOT NULL AND due_date < ?",
            (now_str,)
        )
        overdue_tasks = cur.fetchone()[0]

        cur.execute(
            "SELECT COUNT(*) FROM tasks WHERE completed=0 AND due_date IS NOT NULL AND DATE(due_date)=?",
            (today_str,)
        )
        due_today_tasks = cur.fetchone()[0]

        cur.execute(
            "SELECT COUNT(*) FROM tasks WHERE completed=1 AND DATE(completed_at)=?",
            (today_str,)
        )
        completed_today = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM subtasks")
        subtasks_total = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM subtasks WHERE completed=1")
        subtasks_completed = cur.fetchone()[0]

        completion_rate = round((completed_tasks / total_tasks * 100), 1) if total_tasks > 0 else 0.0

        # Categories distribution
        cur.execute("""
            SELECT c.id, c.name, c.color,
                   COUNT(t.id) AS total,
                   SUM(CASE WHEN t.completed = 1 THEN 1 ELSE 0 END) AS completed,
                   SUM(CASE WHEN t.completed = 0 THEN 1 ELSE 0 END) AS active
            FROM categories c
            LEFT JOIN tasks t ON t.category_id = c.id
            GROUP BY c.id, c.name, c.color
            ORDER BY total DESC, c.name ASC
        """)
        categories = []
        for r in cur.fetchall():
            tot = r["total"]
            done = r["completed"] or 0
            act = r["active"] or 0
            rate = round((done / tot * 100), 1) if tot > 0 else 0.0
            categories.append({
                "id": r["id"],
                "name": r["name"],
                "color": r["color"],
                "total": tot,
                "completed": done,
                "active": act,
                "rate": rate,
            })

        # Priority breakdown (1: Baja, 2: Media, 3: Alta)
        cur.execute("""
            SELECT priority,
                   COUNT(*) AS total,
                   SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) AS completed,
                   SUM(CASE WHEN completed = 0 THEN 1 ELSE 0 END) AS active
            FROM tasks
            GROUP BY priority
        """)
        prio_map = {
            1: {"priority": 1, "name": "Baja", "color": "#6b7280", "total": 0, "completed": 0, "active": 0},
            2: {"priority": 2, "name": "Media", "color": "#d97706", "total": 0, "completed": 0, "active": 0},
            3: {"priority": 3, "name": "Alta", "color": "#dc2626", "total": 0, "completed": 0, "active": 0},
        }
        for r in cur.fetchall():
            p = r["priority"]
            if p in prio_map:
                prio_map[p]["total"] = r["total"]
                prio_map[p]["completed"] = r["completed"] or 0
                prio_map[p]["active"] = r["active"] or 0
        priorities = [prio_map[1], prio_map[2], prio_map[3]]

        # Last 7 days activity (productividad semanal)
        days_es = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
        weekly_activity = []
        today = date.today()
        for i in range(6, -1, -1):
            day_dt = today - timedelta(days=i)
            day_str = day_dt.isoformat()
            day_label = days_es[day_dt.weekday()]

            cur.execute(
                "SELECT COUNT(*) FROM tasks WHERE completed=1 AND DATE(completed_at)=?",
                (day_str,)
            )
            count_tasks = cur.fetchone()[0]

            cur.execute(
                "SELECT COUNT(*) FROM task_history WHERE DATE(completed_at)=? OR DATE(archived_at)=?",
                (day_str, day_str)
            )
            count_history = cur.fetchone()[0]

            cur.execute(
                "SELECT COUNT(*) FROM tasks WHERE DATE(created_at)=?",
                (day_str,)
            )
            count_created = cur.fetchone()[0]

            weekly_activity.append({
                "date": day_str,
                "label": f"{day_label} {day_dt.day}",
                "day_name": day_label,
                "is_today": (i == 0),
                "completed": count_tasks + count_history,
                "created": count_created,
            })

        return {
            "summary": {
                "total": total_tasks,
                "active": active_tasks,
                "completed": completed_tasks,
                "overdue": overdue_tasks,
                "due_today": due_today_tasks,
                "completed_today": completed_today,
                "completion_rate": completion_rate,
                "subtasks_total": subtasks_total,
                "subtasks_completed": subtasks_completed,
            },
            "categories": categories,
            "priorities": priorities,
            "weekly_activity": weekly_activity,
        }

    def get_tasks_due_soon(self, minutes: int = 30) -> List[Dict[str, Any]]:

        """Return incomplete tasks due within *minutes* from now."""
        from datetime import timedelta
        now = datetime.now()
        threshold = (now + timedelta(minutes=minutes)).isoformat(sep=" ", timespec="seconds")
        now_str = now.isoformat(sep=" ", timespec="seconds")
        cur = self._cursor()
        cur.execute(
            """
            SELECT t.*, c.name AS category_name, c.color AS category_color
            FROM tasks t
            LEFT JOIN categories c ON t.category_id = c.id
            WHERE t.completed=0 AND t.due_date IS NOT NULL
              AND t.due_date BETWEEN ? AND ?
            """,
            (now_str, threshold)
        )
        return [dict(r) for r in cur.fetchall()]

    # ==================================================================
    # GAMIFICATION & MISSIONS
    # ==================================================================

    def get_gamification_profile(self) -> Dict[str, Any]:
        """Return the current user RPG progression profile."""
        cur = self._cursor()
        cur.execute("SELECT * FROM user_gamification WHERE id = 1")
        row = cur.fetchone()
        if not row:
            self._seed_gamification()
            cur.execute("SELECT * FROM user_gamification WHERE id = 1")
            row = cur.fetchone()

        profile = dict(row)
        today_str = date.today().isoformat()
        last_active = profile.get("last_active_date")

        # Update daily streak
        if last_active != today_str:
            from datetime import timedelta
            yesterday_str = (date.today() - timedelta(days=1)).isoformat()
            if last_active == yesterday_str:
                new_streak = profile["streak_days"] + 1
            else:
                new_streak = 1
            with self._conn:
                self._conn.execute(
                    "UPDATE user_gamification SET streak_days = ?, last_active_date = ? WHERE id = 1",
                    (new_streak, today_str)
                )
            profile["streak_days"] = new_streak
            profile["last_active_date"] = today_str

        level = profile["level"]
        xp = profile["xp"]
        xp_needed = get_xp_needed_for_level(level)
        progress_pct = min(100.0, round((xp / xp_needed) * 100, 1)) if xp_needed > 0 else 100.0
        rank_info = get_rank_info(level)

        # Count unclaimed completed quests
        cur.execute(
            "SELECT COUNT(*) FROM gamification_quests WHERE quest_date = ? AND completed = 1 AND claimed = 0",
            (today_str,)
        )
        unclaimed_quests = cur.fetchone()[0]

        return {
            "level": level,
            "xp": xp,
            "xp_needed": xp_needed,
            "xp_progress_pct": progress_pct,
            "total_xp": profile["total_xp"],
            "streak_days": profile["streak_days"],
            "tasks_completed_count": profile["tasks_completed_count"],
            "subtasks_completed_count": profile["subtasks_completed_count"],
            "voice_commands_count": profile["voice_commands_count"],
            "quests_completed_count": profile["quests_completed_count"],
            "unclaimed_quests": unclaimed_quests,
            "rank": rank_info,
        }

    def add_xp(self, amount: int, reason: str = "") -> Dict[str, Any]:
        """
        Add XP to the user, handle level-ups, and update the database.
        Returns level-up info and new stats.
        """
        cur = self._cursor()
        cur.execute("SELECT xp, level, total_xp FROM user_gamification WHERE id = 1")
        row = cur.fetchone()
        if not row:
            self._seed_gamification()
            cur.execute("SELECT xp, level, total_xp FROM user_gamification WHERE id = 1")
            row = cur.fetchone()

        xp = row["xp"] + amount
        total_xp = row["total_xp"] + amount
        level = row["level"]
        old_level = level
        leveled_up = False

        xp_needed = get_xp_needed_for_level(level)
        while xp >= xp_needed:
            xp -= xp_needed
            level += 1
            leveled_up = True
            xp_needed = get_xp_needed_for_level(level)

        with self._conn:
            self._conn.execute(
                "UPDATE user_gamification SET xp = ?, level = ?, total_xp = ? WHERE id = 1",
                (xp, level, total_xp)
            )

        rank_info = get_rank_info(level)
        return {
            "amount_added": amount,
            "leveled_up": leveled_up,
            "old_level": old_level,
            "new_level": level,
            "current_xp": xp,
            "xp_needed": xp_needed,
            "total_xp": total_xp,
            "rank": rank_info,
            "reason": reason,
        }

    def get_daily_quests(self) -> List[Dict[str, Any]]:
        """Return daily quests for today, creating them if not existing."""
        today_str = date.today().isoformat()
        cur = self._cursor()
        cur.execute("SELECT * FROM gamification_quests WHERE quest_date = ? ORDER BY claimed ASC, completed DESC, id ASC", (today_str,))
        quests = [dict(r) for r in cur.fetchall()]

        if not quests:
            default_quests = [
                (
                    "daily_first_blood",
                    "Primera Sangre Táctica",
                    "Neutraliza al menos 1 tarea cualquiera de tu lista de operaciones.",
                    "Comando Terran",
                    "task_completed",
                    1,
                    60,
                    today_str,
                    "⚔️",
                ),
                (
                    "daily_purge_sector",
                    "Purga del Sector",
                    "Completa 3 tareas operativas durante la jornada.",
                    "Exiliados de Wraeclast",
                    "task_completed",
                    3,
                    150,
                    today_str,
                    "🎯",
                ),
                (
                    "daily_critical_op",
                    "Protocolo Omega Crítico",
                    "Completa una tarea clasificada de prioridad Alta sin dudar.",
                    "Conclave Protoss",
                    "urgent_completed",
                    1,
                    120,
                    today_str,
                    "🚨",
                ),
                (
                    "daily_psionic_voice",
                    "Enlace Psiónico de Voz",
                    "Ejecuta una acción usando tu voz mediante comandos tácticos.",
                    "Comando Táctico",
                    "voice_command",
                    1,
                    80,
                    today_str,
                    "🎙️",
                ),
                (
                    "daily_squad_micro",
                    "Microgestión de Escuadra",
                    "Completa al menos 2 subtareas en tus asignaciones.",
                    "Armería del Dominio",
                    "subtask_completed",
                    2,
                    100,
                    today_str,
                    "🛡️",
                ),
            ]
            with self._conn:
                self._conn.executemany(
                    """
                    INSERT INTO gamification_quests (
                        quest_key, title, description, faction,
                        target_type, target_count, xp_reward, quest_date, icon
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    default_quests
                )
            cur.execute("SELECT * FROM gamification_quests WHERE quest_date = ? ORDER BY claimed ASC, completed DESC, id ASC", (today_str,))
            quests = [dict(r) for r in cur.fetchall()]

        return quests

    def record_action(self, action_type: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Record a gamified action (task_completed, subtask_completed, voice_command),
        grant XP, advance daily quests, and check for completions/level-ups.
        """
        meta = metadata or {}
        today_str = date.today().isoformat()
        self.get_daily_quests()  # Ensure quests for today exist

        xp_gained = 0
        cur = self._cursor()

        # Update action counters
        if action_type == "task_completed":
            prio = meta.get("priority", 2)
            xp_gained = 30 if prio == 1 else (60 if prio == 2 else 100)
            with self._conn:
                self._conn.execute(
                    "UPDATE user_gamification SET tasks_completed_count = tasks_completed_count + 1 WHERE id = 1"
                )

            # Advance task_completed quests
            with self._conn:
                self._conn.execute(
                    """
                    UPDATE gamification_quests
                    SET current_count = current_count + 1
                    WHERE quest_date = ? AND target_type = 'task_completed' AND completed = 0
                    """,
                    (today_str,)
                )
            # If high priority, advance urgent_completed quests
            if prio == 3:
                with self._conn:
                    self._conn.execute(
                        """
                        UPDATE gamification_quests
                        SET current_count = current_count + 1
                        WHERE quest_date = ? AND target_type = 'urgent_completed' AND completed = 0
                        """,
                        (today_str,)
                    )

        elif action_type == "subtask_completed":
            xp_gained = 15
            with self._conn:
                self._conn.execute(
                    "UPDATE user_gamification SET subtasks_completed_count = subtasks_completed_count + 1 WHERE id = 1"
                )
                self._conn.execute(
                    """
                    UPDATE gamification_quests
                    SET current_count = current_count + 1
                    WHERE quest_date = ? AND target_type = 'subtask_completed' AND completed = 0
                    """,
                    (today_str,)
                )

        elif action_type == "voice_command":
            xp_gained = 25
            with self._conn:
                self._conn.execute(
                    "UPDATE user_gamification SET voice_commands_count = voice_commands_count + 1 WHERE id = 1"
                )
                self._conn.execute(
                    """
                    UPDATE gamification_quests
                    SET current_count = current_count + 1
                    WHERE quest_date = ? AND target_type = 'voice_command' AND completed = 0
                    """,
                    (today_str,)
                )

        # Check newly completed quests
        cur.execute(
            """
            SELECT * FROM gamification_quests
            WHERE quest_date = ? AND completed = 0 AND current_count >= target_count
            """,
            (today_str,)
        )
        newly_completed = [dict(r) for r in cur.fetchall()]
        if newly_completed:
            with self._conn:
                self._conn.execute(
                    """
                    UPDATE gamification_quests
                    SET completed = 1
                    WHERE quest_date = ? AND completed = 0 AND current_count >= target_count
                    """,
                    (today_str,)
                )

        # Award base action XP
        xp_result = self.add_xp(xp_gained, reason=f"Acción: {action_type}")
        xp_result["newly_completed_quests"] = newly_completed

        return xp_result

    def claim_quest(self, quest_id: int) -> Dict[str, Any]:
        """Claim the reward of a completed quest."""
        cur = self._cursor()
        cur.execute("SELECT * FROM gamification_quests WHERE id = ?", (quest_id,))
        row = cur.fetchone()
        if not row:
            return {"success": False, "error": "Misión no encontrada"}

        quest = dict(row)
        if quest["claimed"]:
            return {"success": False, "error": "Esta misión ya fue reclamada"}
        if not quest["completed"]:
            return {"success": False, "error": "La misión aún no ha sido completada"}

        with self._conn:
            self._conn.execute("UPDATE gamification_quests SET claimed = 1 WHERE id = ?", (quest_id,))
            self._conn.execute("UPDATE user_gamification SET quests_completed_count = quests_completed_count + 1 WHERE id = 1")

        xp_res = self.add_xp(quest["xp_reward"], reason=f"Misión: {quest['title']}")
        return {
            "success": True,
            "quest": quest,
            "xp_res": xp_res,
        }

    def reset_gamification(self) -> None:
        """Reset gamification stats to level 1 with 0 XP."""
        today_str = date.today().isoformat()
        with self._conn:
            self._conn.execute("DELETE FROM gamification_quests")
            self._conn.execute(
                """
                UPDATE user_gamification
                SET xp = 0, level = 1, total_xp = 0, streak_days = 1,
                    last_active_date = ?, tasks_completed_count = 0,
                    subtasks_completed_count = 0, voice_commands_count = 0,
                    quests_completed_count = 0
                WHERE id = 1
                """,
                (today_str,)
            )

    # ------------------------------------------------------------------
    # Context manager support
    # ------------------------------------------------------------------

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


# ===========================================================================
# GAMIFICATION CONSTANTS & RANKS
# ===========================================================================

RANKS = [
    (1, "Recluta Terran", "⚔️", "Primeros pasos en la línea de frente."),
    (2, "Soldado Marine", "🛡️", "Veterano de escaramuzas tácticas."),
    (3, "Fantasma Psiónico", "⚡", "Especialista en operaciones encubiertas."),
    (4, "Inquisidor del Vacío", "🔥", "Purificador de sectores hostiles."),
    (5, "Piloto Siege Tank", "💎", "Poder de fuego destructivo y disciplinado."),
    (6, "Exiliado Ascendente", "🌌", "Ha trascendido las pruebas del laberinto."),
    (7, "Matadioses del Atlas", "👑", "Dominador de las fuerzas cósmicas."),
    (8, "Capitán Battlecruiser", "🪐", "Comandante supremo de flotas estelares."),
    (9, "Alto Templario", "🌟", "Maestría psiónica y concentración absoluta."),
    (10, "Arconte Supremo", "⚡", "Fusión pura de energía y voluntad imparable."),
]


def get_rank_info(level: int) -> Dict[str, Any]:
    """Return rank title, icon, description, and next rank info for a level."""
    current = RANKS[0]
    next_rank = RANKS[1] if len(RANKS) > 1 else None
    for idx, r in enumerate(RANKS):
        if level >= r[0]:
            current = r
            next_rank = RANKS[idx + 1] if idx + 1 < len(RANKS) else None
    return {
        "title": current[1],
        "icon": current[2],
        "desc": current[3],
        "level": current[0],
        "next_title": next_rank[1] if next_rank else "Máximo Rango Alcanzado",
        "next_level": next_rank[0] if next_rank else None,
    }


def get_xp_needed_for_level(level: int) -> int:
    """XP needed to advance from level to level + 1."""
    return 100 + level * 50
