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
from typing import Optional, List, Dict, Any


# ---------------------------------------------------------------------------
# Database path
# ---------------------------------------------------------------------------
DB_DIR = Path.home() / ".taskvoice"
DB_PATH = DB_DIR / "tasks.db"

# ---------------------------------------------------------------------------
# Default categories (name, hex-color)
# ---------------------------------------------------------------------------
DEFAULT_CATEGORIES = [
    ("Personal",  "#7c3aed"),
    ("Trabajo",   "#2563eb"),
    ("Salud",     "#16a34a"),
    ("Estudio",   "#d97706"),
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

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._connect()
        self._create_schema()
        self._seed_categories()

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _connect(self) -> None:
        """Open (or reopen) the SQLite connection."""
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")

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
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            title        TEXT NOT NULL,
            description  TEXT DEFAULT '',
            category_id  INTEGER REFERENCES categories(id) ON DELETE SET NULL,
            due_date     TEXT,
            priority     INTEGER NOT NULL DEFAULT 2 CHECK(priority BETWEEN 1 AND 3),
            progress     INTEGER NOT NULL DEFAULT 0 CHECK(progress BETWEEN 0 AND 100),
            completed    INTEGER NOT NULL DEFAULT 0,
            created_at   TEXT NOT NULL,
            completed_at TEXT
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
        """
        with self._conn:
            self._conn.executescript(sql)

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

    def add_task(
        self,
        title: str,
        description: str = "",
        category_id: Optional[int] = None,
        due_date: Optional[str] = None,
        priority: int = 2,
    ) -> int:
        """Insert a new task and return its id."""
        now = datetime.now().isoformat(sep=" ", timespec="seconds")
        with self._conn:
            cur = self._conn.execute(
                """
                INSERT INTO tasks
                    (title, description, category_id, due_date, priority, progress, completed, created_at)
                VALUES (?, ?, ?, ?, ?, 0, 0, ?)
                """,
                (title, description, category_id, due_date, priority, now)
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
    ) -> None:
        """Partially update a task's fields."""
        task = self.get_task(task_id)
        if task is None:
            return
        with self._conn:
            self._conn.execute(
                """
                UPDATE tasks
                SET title=?, description=?, category_id=?, due_date=?, priority=?
                WHERE id=?
                """,
                (
                    title if title is not None else task["title"],
                    description if description is not None else task["description"],
                    category_id if category_id is not None else task["category_id"],
                    due_date if due_date is not None else task["due_date"],
                    priority if priority is not None else task["priority"],
                    task_id,
                )
            )

    def complete_task(self, task_id: int) -> None:
        """Mark a task as completed and update its completed_at timestamp."""
        now = datetime.now().isoformat(sep=" ", timespec="seconds")
        with self._conn:
            self._conn.execute(
                "UPDATE tasks SET completed=1, progress=100, completed_at=? WHERE id=?",
                (now, task_id)
            )

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

    # ------------------------------------------------------------------
    # Context manager support
    # ------------------------------------------------------------------

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
