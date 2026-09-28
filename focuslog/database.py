"""SQLite setup for FocusLog's local application data."""

import os
import sqlite3
from contextlib import closing
from pathlib import Path

APP_DIRECTORY_NAME = "FocusLog"
DATABASE_FILE_NAME = "focuslog.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    is_completed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS focus_sessions (
    id TEXT PRIMARY KEY,
    task_id TEXT,
    activity_description TEXT,
    subject TEXT,
    status TEXT NOT NULL,
    planned_seconds INTEGER NOT NULL,
    focused_seconds REAL NOT NULL DEFAULT 0,
    started_at TEXT,
    ended_at TEXT,
    ended_epoch REAL,
    last_resumed_at TEXT,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS obsidian_events (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    timezone_name TEXT,
    utc_offset TEXT,
    payload TEXT NOT NULL,
    is_sent INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    append_path TEXT,
    append_offset INTEGER
);

CREATE INDEX IF NOT EXISTS idx_focus_sessions_status
    ON focus_sessions(status);
CREATE INDEX IF NOT EXISTS idx_obsidian_events_pending
    ON obsidian_events(is_sent, occurred_at);
"""

DEFAULT_SETTINGS = {
    "focus_minutes": "25",
    "break_minutes": "5",
    "vault_path": "",
}


def get_database_path() -> Path:
    """Return the database path in the current user's local app-data folder."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        local_app_data = str(Path.home() / "AppData" / "Local")
    return Path(local_app_data) / APP_DIRECTORY_NAME / DATABASE_FILE_NAME


def _add_missing_columns(connection: sqlite3.Connection) -> None:
    """Upgrade a Phase 1 database without deleting existing data."""
    columns = {
        row[1] for row in connection.execute("PRAGMA table_info(focus_sessions)")
    }
    additions = {
        "subject": "TEXT",
        "last_resumed_at": "TEXT",
        "ended_epoch": "REAL",
    }
    for name, column_type in additions.items():
        if name not in columns:
            connection.execute(
                f"ALTER TABLE focus_sessions ADD COLUMN {name} {column_type}"
            )

    event_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(obsidian_events)")
    }
    event_additions = {
        "timezone_name": "TEXT",
        "utc_offset": "TEXT",
        "append_path": "TEXT",
        "append_offset": "INTEGER",
    }
    for name, column_type in event_additions.items():
        if name not in event_columns:
            connection.execute(
                f"ALTER TABLE obsidian_events ADD COLUMN {name} {column_type}"
            )


def initialize_database(database_path: Path | None = None) -> Path:
    """Create or migrate the application database and insert defaults."""
    path = database_path or get_database_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    with closing(sqlite3.connect(path)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(SCHEMA)
        _add_missing_columns(connection)
        connection.executemany(
            "INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)",
            DEFAULT_SETTINGS.items(),
        )
        connection.commit()

    return path
