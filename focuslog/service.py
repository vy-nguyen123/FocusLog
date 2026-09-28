"""SQLite-backed business logic for FocusLog Version 1."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from focuslog.database import initialize_database
from focuslog.obsidian import append_event, is_valid_vault, prepare_event_append


class ValidationError(ValueError):
    """Raised when user input does not meet a product rule."""


class ProtectedTaskError(RuntimeError):
    """Raised when an active focus session protects its linked task."""


class SessionStateError(RuntimeError):
    """Raised when a focus action is invalid in the current state."""


def _local_now() -> datetime:
    return datetime.now().astimezone()


class FocusLogService:
    """Owns application data and enforces the Version 1 business rules."""

    def __init__(
        self,
        database_path: Path | None = None,
        clock: Callable[[], datetime] = _local_now,
    ) -> None:
        self.database_path = initialize_database(database_path)
        self.clock = clock

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _task_from_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        task = dict(row)
        task["is_completed"] = bool(task["is_completed"])
        return task

    @staticmethod
    def _session_from_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
        return dict(row) if row is not None else None

    @staticmethod
    def _clean_title(title: str) -> str:
        cleaned = title.strip()
        if not cleaned:
            raise ValidationError("Task title cannot be empty.")
        return cleaned

    def _is_task_protected(
        self, connection: sqlite3.Connection, task_id: str
    ) -> bool:
        row = connection.execute(
            """
            SELECT 1 FROM focus_sessions
            WHERE task_id = ? AND status IN ('running', 'paused')
            LIMIT 1
            """,
            (task_id,),
        ).fetchone()
        return row is not None

    def _require_editable_task(
        self, connection: sqlite3.Connection, task_id: str
    ) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if row is None:
            raise ValidationError("Task was not found.")
        if self._is_task_protected(connection, task_id):
            raise ProtectedTaskError(
                "This task cannot be changed while its focus session is active."
            )
        return row

    def _insert_event(
        self,
        connection: sqlite3.Connection,
        event_type: str,
        payload: dict[str, Any],
        occurred_at: datetime,
    ) -> str:
        event_id = str(uuid4())
        offset = occurred_at.utcoffset()
        total_minutes = int(offset.total_seconds() // 60) if offset else 0
        sign = "+" if total_minutes >= 0 else "-"
        hours, minutes = divmod(abs(total_minutes), 60)
        utc_offset = f"{sign}{hours:02d}:{minutes:02d}"
        connection.execute(
            """
            INSERT INTO obsidian_events(
                id, event_type, occurred_at, timezone_name, utc_offset,
                payload, is_sent, last_error
            ) VALUES (?, ?, ?, ?, ?, ?, 0, NULL)
            """,
            (
                event_id,
                event_type,
                occurred_at.isoformat(),
                occurred_at.tzname() or "Local time",
                utc_offset,
                json.dumps(payload, ensure_ascii=False),
            ),
        )
        return event_id

    def _flush_events(self) -> None:
        self.retry_pending_events()

    # Tasks
    def create_task(self, title: str) -> dict[str, Any]:
        cleaned = self._clean_title(title)
        now = self.clock()
        task_id = str(uuid4())
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO tasks(id, title, is_completed, created_at, updated_at)
                VALUES (?, ?, 0, ?, ?)
                """,
                (task_id, cleaned, now.isoformat(), now.isoformat()),
            )
            self._insert_event(
                connection,
                "task_created",
                {"status": "active", "title": cleaned},
                now,
            )
            connection.commit()
        self._flush_events()
        return self.get_task(task_id)

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
        return self._task_from_row(row)

    def list_tasks(self) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT * FROM tasks
                ORDER BY is_completed ASC, created_at ASC, rowid ASC
                """
            ).fetchall()
        return [self._task_from_row(row) for row in rows]

    def rename_task(self, task_id: str, new_title: str) -> dict[str, Any]:
        cleaned = self._clean_title(new_title)
        now = self.clock()
        with closing(self._connect()) as connection:
            task = self._require_editable_task(connection, task_id)
            connection.execute(
                "UPDATE tasks SET title = ?, updated_at = ? WHERE id = ?",
                (cleaned, now.isoformat(), task_id),
            )
            self._insert_event(
                connection,
                "task_renamed",
                {
                    "status": "completed" if task["is_completed"] else "active",
                    "previous_title": task["title"],
                    "new_title": cleaned,
                },
                now,
            )
            connection.commit()
        self._flush_events()
        return self.get_task(task_id)

    def complete_task(self, task_id: str) -> dict[str, Any]:
        return self._set_task_completed(task_id, True)

    def reopen_task(self, task_id: str) -> dict[str, Any]:
        return self._set_task_completed(task_id, False)

    def _set_task_completed(
        self, task_id: str, is_completed: bool
    ) -> dict[str, Any]:
        now = self.clock()
        with closing(self._connect()) as connection:
            task = self._require_editable_task(connection, task_id)
            if bool(task["is_completed"]) == is_completed:
                return self._task_from_row(task)
            connection.execute(
                "UPDATE tasks SET is_completed = ?, updated_at = ? WHERE id = ?",
                (int(is_completed), now.isoformat(), task_id),
            )
            self._insert_event(
                connection,
                "task_completed" if is_completed else "task_reopened",
                {
                    "status": "completed" if is_completed else "active",
                    "title": task["title"],
                },
                now,
            )
            connection.commit()
        self._flush_events()
        return self.get_task(task_id)

    def delete_task(self, task_id: str) -> None:
        now = self.clock()
        with closing(self._connect()) as connection:
            task = self._require_editable_task(connection, task_id)
            connection.execute(
                "UPDATE focus_sessions SET task_id = NULL WHERE task_id = ?",
                (task_id,),
            )
            connection.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            self._insert_event(
                connection,
                "task_deleted",
                {"status": "deleted", "title": task["title"]},
                now,
            )
            connection.commit()
        self._flush_events()

    # Settings
    def _get_setting(self, key: str) -> str:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            ).fetchone()
        return row["value"]

    def _set_setting(self, key: str, value: str) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO settings(key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )
            connection.commit()

    def get_durations(self) -> tuple[int, int]:
        return (
            int(self._get_setting("focus_minutes")),
            int(self._get_setting("break_minutes")),
        )

    def set_durations(self, focus_minutes: int, break_minutes: int) -> None:
        if (
            isinstance(focus_minutes, bool)
            or isinstance(break_minutes, bool)
            or not isinstance(focus_minutes, int)
            or not isinstance(break_minutes, int)
            or focus_minutes <= 0
            or break_minutes <= 0
        ):
            raise ValidationError("Durations must be positive whole minutes.")
        with closing(self._connect()) as connection:
            connection.executemany(
                """
                INSERT INTO settings(key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (
                    ("focus_minutes", str(focus_minutes)),
                    ("break_minutes", str(break_minutes)),
                ),
            )
            connection.commit()

    # Focus sessions
    def _active_row(self, connection: sqlite3.Connection) -> sqlite3.Row | None:
        return connection.execute(
            """
            SELECT * FROM focus_sessions
            WHERE status IN ('running', 'paused')
            ORDER BY started_at DESC LIMIT 1
            """
        ).fetchone()

    @staticmethod
    def _elapsed(row: sqlite3.Row, now: datetime) -> float:
        elapsed = float(row["focused_seconds"])
        if row["status"] == "running" and row["last_resumed_at"]:
            resumed_at = datetime.fromisoformat(row["last_resumed_at"])
            elapsed += max(0.0, (now - resumed_at).total_seconds())
        return min(elapsed, float(row["planned_seconds"]))

    def start_focus(
        self,
        task_id: str | None = None,
        activity_description: str | None = None,
    ) -> dict[str, Any]:
        description = (activity_description or "").strip()
        if bool(task_id) == bool(description):
            raise ValidationError(
                "Choose one task or enter one activity description."
            )
        now = self.clock()
        session_id = str(uuid4())
        focus_minutes, _ = self.get_durations()
        planned_seconds = focus_minutes * 60
        with closing(self._connect()) as connection:
            if self._active_row(connection) is not None:
                raise SessionStateError("A focus session is already active.")
            if task_id:
                task = connection.execute(
                    "SELECT * FROM tasks WHERE id = ?", (task_id,)
                ).fetchone()
                if task is None or task["is_completed"]:
                    raise ValidationError("Select an active task.")
                subject = task["title"]
                description_value = None
            else:
                subject = description
                description_value = description
            connection.execute(
                """
                INSERT INTO focus_sessions(
                    id, task_id, activity_description, subject, status,
                    planned_seconds, focused_seconds, started_at, ended_at,
                    last_resumed_at
                ) VALUES (?, ?, ?, ?, 'running', ?, 0, ?, NULL, ?)
                """,
                (
                    session_id,
                    task_id,
                    description_value,
                    subject,
                    planned_seconds,
                    now.isoformat(),
                    now.isoformat(),
                ),
            )
            self._insert_event(
                connection,
                "focus_started",
                {
                    "status": "running",
                    "subject": subject,
                    "planned_seconds": planned_seconds,
                },
                now,
            )
            connection.commit()
        self._flush_events()
        return self.get_active_session()

    def get_active_session(self) -> dict[str, Any] | None:
        now = self.clock()
        with closing(self._connect()) as connection:
            row = self._active_row(connection)
        session = self._session_from_row(row)
        if session is not None:
            session["focused_seconds"] = self._elapsed(row, now)
        return session

    def pause_focus(self) -> dict[str, Any]:
        now = self.clock()
        completed = False
        with closing(self._connect()) as connection:
            row = self._active_row(connection)
            if row is None or row["status"] != "running":
                raise SessionStateError("Only a running session can be paused.")
            elapsed = self._elapsed(row, now)
            if elapsed >= row["planned_seconds"]:
                result = self._finish_focus(
                    connection, row, "completed", elapsed, now
                )
                completed = True
            else:
                connection.execute(
                    """
                    UPDATE focus_sessions
                    SET status = 'paused', focused_seconds = ?, last_resumed_at = NULL
                    WHERE id = ?
                    """,
                    (elapsed, row["id"]),
                )
            connection.commit()
        if completed:
            self._flush_events()
            return result
        return self.get_active_session()

    def resume_focus(self) -> dict[str, Any]:
        now = self.clock()
        with closing(self._connect()) as connection:
            row = self._active_row(connection)
            if row is None or row["status"] != "paused":
                raise SessionStateError("Only a paused session can be resumed.")
            connection.execute(
                """
                UPDATE focus_sessions
                SET status = 'running', last_resumed_at = ? WHERE id = ?
                """,
                (now.isoformat(), row["id"]),
            )
            connection.commit()
        return self.get_active_session()

    def checkpoint_active(self) -> dict[str, Any] | None:
        now = self.clock()
        with closing(self._connect()) as connection:
            row = self._active_row(connection)
            if row is None:
                return None
            if row["status"] == "running":
                elapsed = self._elapsed(row, now)
                connection.execute(
                    """
                    UPDATE focus_sessions
                    SET focused_seconds = ?, last_resumed_at = ? WHERE id = ?
                    """,
                    (elapsed, now.isoformat(), row["id"]),
                )
                connection.commit()
        return self.get_active_session()

    def _finish_focus(
        self,
        connection: sqlite3.Connection,
        row: sqlite3.Row,
        status: str,
        focused_seconds: float,
        now: datetime,
    ) -> dict[str, Any]:
        actual = min(max(0, int(focused_seconds)), int(row["planned_seconds"]))
        connection.execute(
            """
            UPDATE focus_sessions
            SET status = ?, focused_seconds = ?, ended_at = ?, ended_epoch = ?,
                last_resumed_at = NULL
            WHERE id = ?
            """,
            (status, actual, now.isoformat(), now.timestamp(), row["id"]),
        )
        self._insert_event(
            connection,
            "focus_completed" if status == "completed" else "focus_cancelled",
            {
                "status": status,
                "subject": row["subject"],
                "planned_seconds": int(row["planned_seconds"]),
                "actual_seconds": actual,
            },
            now,
        )
        result = dict(row)
        result.update(
            status=status,
            focused_seconds=actual,
            ended_at=now.isoformat(),
            ended_epoch=now.timestamp(),
            last_resumed_at=None,
        )
        return result

    def stop_focus(self) -> dict[str, Any]:
        now = self.clock()
        with closing(self._connect()) as connection:
            row = self._active_row(connection)
            if row is None:
                raise SessionStateError("No focus session is active.")
            elapsed = self._elapsed(row, now)
            status = (
                "completed"
                if elapsed >= row["planned_seconds"]
                else "cancelled"
            )
            result = self._finish_focus(connection, row, status, elapsed, now)
            connection.commit()
        self._flush_events()
        return result

    def update_focus(self) -> dict[str, Any] | None:
        now = self.clock()
        with closing(self._connect()) as connection:
            row = self._active_row(connection)
            if row is None:
                return None
            elapsed = self._elapsed(row, now)
            if row["status"] == "running" and elapsed >= row["planned_seconds"]:
                result = self._finish_focus(
                    connection,
                    row,
                    "completed",
                    int(row["planned_seconds"]),
                    now,
                )
                connection.commit()
            else:
                result = dict(row)
                result["focused_seconds"] = elapsed
                return result
        self._flush_events()
        return result

    def cancel_active_on_close(self) -> dict[str, Any] | None:
        if self.get_active_session() is None:
            return None
        return self.stop_focus()

    def recover_interrupted_session(self) -> dict[str, Any] | None:
        now = self.clock()
        with closing(self._connect()) as connection:
            row = self._active_row(connection)
            if row is None:
                return None
            result = self._finish_focus(
                connection,
                row,
                "cancelled",
                float(row["focused_seconds"]),
                now,
            )
            connection.commit()
        self._flush_events()
        return result

    def list_history(self) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT * FROM focus_sessions
                WHERE status IN ('completed', 'cancelled')
                ORDER BY COALESCE(ended_epoch, 0) DESC, rowid DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    # Obsidian queue
    def select_vault(self, vault_path: Path) -> None:
        path = Path(vault_path)
        if not is_valid_vault(path):
            raise ValidationError(
                "Select a folder that contains an .obsidian directory."
            )
        self._set_setting("vault_path", str(path))
        self.retry_pending_events()

    def get_vault_path(self) -> Path | None:
        value = self._get_setting("vault_path")
        return Path(value) if value else None

    @staticmethod
    def _event_from_row(row: sqlite3.Row) -> dict[str, Any]:
        event = dict(row)
        event["payload"] = json.loads(event["payload"])
        event["is_sent"] = bool(event["is_sent"])
        return event

    def list_events(self) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM obsidian_events ORDER BY occurred_at, rowid"
            ).fetchall()
        return [self._event_from_row(row) for row in rows]

    def retry_pending_events(self) -> int:
        vault_path = self.get_vault_path()
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT * FROM obsidian_events
                WHERE is_sent = 0 ORDER BY occurred_at ASC, rowid ASC
                """
            ).fetchall()
            if not rows:
                return 0
            if vault_path is None:
                error = "No valid Obsidian vault is configured."
                connection.execute(
                    "UPDATE obsidian_events SET last_error = ? WHERE is_sent = 0",
                    (error,),
                )
                connection.commit()
                return 0

            sent_count = 0
            for queued_row in rows:
                event_id = queued_row["id"]
                try:
                    connection.execute("BEGIN IMMEDIATE")
                    current_row = connection.execute(
                        """
                        SELECT * FROM obsidian_events
                        WHERE id = ? AND is_sent = 0
                        """,
                        (event_id,),
                    ).fetchone()
                    if current_row is None:
                        connection.commit()
                        continue

                    event = self._event_from_row(current_row)
                    timestamp = datetime.fromisoformat(event["occurred_at"])
                    expected_path = (
                        vault_path
                        / "Productivity Logs"
                        / f"{timestamp:%Y-%m-%d}.md"
                    )
                    stored_path = event.get("append_path")
                    append_offset = event.get("append_offset")
                    same_target = (
                        stored_path is not None
                        and Path(stored_path).resolve() == expected_path.resolve()
                    )
                    if append_offset is None or not same_target:
                        append_path, append_offset = prepare_event_append(
                            vault_path, event
                        )
                        connection.execute(
                            """
                            UPDATE obsidian_events
                            SET append_path = ?, append_offset = ?
                            WHERE id = ?
                            """,
                            (str(append_path), append_offset, event["id"]),
                        )
                    connection.commit()

                    connection.execute("BEGIN IMMEDIATE")
                    current_row = connection.execute(
                        """
                        SELECT * FROM obsidian_events
                        WHERE id = ? AND is_sent = 0
                        """,
                        (event_id,),
                    ).fetchone()
                    if current_row is None:
                        connection.commit()
                        continue
                    event = self._event_from_row(current_row)
                    append_event(
                        vault_path,
                        event,
                        append_offset=int(event["append_offset"]),
                    )
                except (OSError, UnicodeError) as error:
                    connection.execute(
                        "UPDATE obsidian_events SET last_error = ? WHERE id = ?",
                        (str(error), event_id),
                    )
                else:
                    connection.execute(
                        """
                        UPDATE obsidian_events
                        SET is_sent = 1, last_error = NULL WHERE id = ?
                        """,
                        (event_id,),
                    )
                    sent_count += 1
                connection.commit()
        return sent_count

    def get_logging_status(self) -> dict[str, Any]:
        vault_path = self.get_vault_path()
        with closing(self._connect()) as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM obsidian_events WHERE is_sent = 0"
            ).fetchone()[0]
            error_row = connection.execute(
                """
                SELECT last_error FROM obsidian_events
                WHERE is_sent = 0 AND last_error IS NOT NULL
                ORDER BY occurred_at DESC, rowid DESC LIMIT 1
                """
            ).fetchone()
        return {
            "vault_path": vault_path,
            "vault_valid": vault_path is not None and is_valid_vault(vault_path),
            "pending_count": count,
            "latest_error": error_row["last_error"] if error_row else None,
        }
