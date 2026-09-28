import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from focuslog.database import get_database_path, initialize_database


class DatabaseInitializationTests(unittest.TestCase):
    def test_database_path_uses_local_app_data_not_project_folder(self):
        with tempfile.TemporaryDirectory() as local_app_data:
            with patch.dict(os.environ, {"LOCALAPPDATA": local_app_data}):
                database_path = get_database_path()

        self.assertEqual(
            database_path,
            Path(local_app_data) / "FocusLog" / "focuslog.db",
        )

    def test_initialize_database_creates_required_phase_one_tables(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "nested" / "focuslog.db"

            initialize_database(database_path)

            self.assertTrue(database_path.exists())
            with closing(sqlite3.connect(database_path)) as connection:
                table_names = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }

        self.assertEqual(
            table_names,
            {"tasks", "focus_sessions", "settings", "obsidian_events"},
        )


if __name__ == "__main__":
    unittest.main()
