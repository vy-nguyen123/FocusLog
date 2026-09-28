from datetime import datetime, timedelta, timezone
import sqlite3
import tempfile
import threading
import time
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from focuslog.obsidian import append_event, prepare_event_append, render_event
from focuslog.service import FocusLogService, ValidationError


class FixedClock:
    def __call__(self):
        return datetime(2026, 9, 28, 14, 30, tzinfo=timezone(timedelta(hours=2), "CEST"))


class ObsidianIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        self.database_path = root / "focuslog.db"
        self.vault = root / "vault"
        self.vault.mkdir()
        (self.vault / ".obsidian").mkdir()
        self.service = FocusLogService(self.database_path, clock=FixedClock())

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_only_an_obsidian_vault_is_accepted(self):
        invalid = Path(self.temporary_directory.name) / "invalid"
        invalid.mkdir()
        with self.assertRaises(ValidationError):
            self.service.select_vault(invalid)

        self.service.select_vault(self.vault)
        self.assertEqual(self.service.get_vault_path(), self.vault)

    def test_task_and_focus_events_append_to_daily_markdown(self):
        self.service.select_vault(self.vault)
        task = self.service.create_task("Write summary")
        self.service.rename_task(task["id"], "Write final summary")
        self.service.complete_task(task["id"])
        self.service.reopen_task(task["id"])
        self.service.start_focus(task_id=task["id"])
        self.service.stop_focus()
        self.service.delete_task(task["id"])

        daily_file = self.vault / "Productivity Logs" / "2026-09-28.md"
        content = daily_file.read_text(encoding="utf-8")
        self.assertTrue(content.startswith("# Productivity Log — 2026-09-28"))
        for event_type in (
            "task_created", "task_renamed", "task_completed", "task_reopened",
            "focus_started", "focus_cancelled", "task_deleted",
        ):
            self.assertIn(f"- Event type: {event_type}", content)
        self.assertIn("- Timezone: CEST", content)
        self.assertIn("- UTC offset: +02:00", content)
        self.assertEqual(self.service.get_logging_status()["pending_count"], 0)

    def test_unavailable_vault_queues_and_retry_is_duplicate_safe(self):
        task = self.service.create_task("Queued task")
        status = self.service.get_logging_status()
        self.assertEqual(status["pending_count"], 1)
        self.assertTrue(status["latest_error"])

        self.service.select_vault(self.vault)
        daily_file = self.vault / "Productivity Logs" / "2026-09-28.md"
        first_content = daily_file.read_text(encoding="utf-8")
        event_id = self.service.list_events()[0]["id"]
        self.assertIn(event_id, first_content)

        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute(
                "UPDATE obsidian_events SET is_sent = 0 WHERE id = ?",
                (event_id,),
            )
            connection.commit()
        self.service.retry_pending_events()
        second_content = daily_file.read_text(encoding="utf-8")

        self.assertEqual(first_content, second_content)
        self.assertEqual(
            second_content.count(f"<!-- FocusLog Event Complete: {event_id} -->"),
            1,
        )
        self.assertEqual(self.service.get_logging_status()["pending_count"], 0)
        self.assertEqual(self.service.get_task(task["id"])["title"], "Queued task")

    def test_partial_event_id_does_not_count_as_a_complete_retry(self):
        self.service.create_task("Interrupted write")
        self.service.select_vault(self.vault)
        event = self.service.list_events()[0]
        event_id = event["id"]
        daily_file = self.vault / "Productivity Logs" / "2026-09-28.md"
        append_offset = event["append_offset"]
        section = render_event(event).encode("utf-8")
        cut = section.index(b"- Date:")
        daily_file.write_bytes(daily_file.read_bytes()[:append_offset] + section[:cut])
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute(
                "UPDATE obsidian_events SET is_sent = 0 WHERE id = ?",
                (event_id,),
            )
            connection.commit()

        self.service.retry_pending_events()
        content = daily_file.read_text(encoding="utf-8")

        self.assertIn("- Event type: task_created", content)
        self.assertIn(f"<!-- FocusLog Event Complete: {event_id} -->", content)
        self.assertEqual(content.count("## 14:30:00 — Task Created"), 1)
        self.assertEqual(content.count(f"- Event ID: `{event_id}`"), 1)
        self.assertEqual(self.service.get_logging_status()["pending_count"], 0)

    def test_pause_resume_and_breaks_do_not_create_events(self):
        self.service.select_vault(self.vault)
        self.service.start_focus(activity_description="Focus")
        before_pause = len(self.service.list_events())
        self.service.pause_focus()
        self.service.resume_focus()

        self.assertEqual(len(self.service.list_events()), before_pause)

    def test_retry_recovers_every_partial_write_boundary_without_duplicates(self):
        event = {
            "id": "7d8f23d4-2e61-4d99-8afd-81a3b2c89b83",
            "event_type": "task_created",
            "occurred_at": "2026-09-28T14:30:00+02:00",
            "timezone_name": "CEST",
            "utc_offset": "+02:00",
            "payload": {"status": "active", "title": "Boundary task"},
        }
        rendered = render_event(event)
        base = Path(self.temporary_directory.name) / "cut-points"

        for cut in range(len(rendered) + 1):
            with self.subTest(cut=cut):
                vault = base / str(cut)
                (vault / ".obsidian").mkdir(parents=True)
                logs = vault / "Productivity Logs"
                logs.mkdir()
                daily_file = logs / "2026-09-28.md"
                daily_file.write_text("# User notes\n\nKeep this.\n", encoding="utf-8")
                _, append_offset = prepare_event_append(vault, event)
                with daily_file.open("ab") as handle:
                    handle.write(rendered[:cut].encode("utf-8"))
                original = daily_file.read_bytes()

                append_event(vault, event, append_offset=append_offset)
                content = daily_file.read_text(encoding="utf-8")

                self.assertTrue(daily_file.read_bytes().startswith(original))
                self.assertEqual(content.count("## 14:30:00 — Task Created"), 1)
                self.assertEqual(
                    content.count(f"- Event ID: `{event['id']}`"), 1
                )
                self.assertEqual(
                    content.count(
                        f"<!-- FocusLog Event Complete: {event['id']} -->"
                    ),
                    1,
                )

    def test_unrelated_markdown_suffix_is_not_treated_as_partial_event(self):
        event = {
            "id": "7d8f23d4-2e61-4d99-8afd-81a3b2c89b83",
            "event_type": "task_created",
            "occurred_at": "2026-09-28T14:30:00+02:00",
            "timezone_name": "CEST",
            "utc_offset": "+02:00",
            "payload": {"status": "active", "title": "Boundary task"},
        }
        daily_file = self.vault / "Productivity Logs" / "2026-09-28.md"
        daily_file.parent.mkdir()

        for suffix in ("#", "##", "## 14:30"):
            with self.subTest(suffix=suffix):
                original = f"# User notes\n\nUnrelated content ending in {suffix}"
                daily_file.write_text(original, encoding="utf-8")

                append_event(self.vault, event)
                content = daily_file.read_text(encoding="utf-8")

                self.assertTrue(content.startswith(original))
                self.assertIn("\n\n## 14:30:00 — Task Created", content)
                self.assertEqual(content.count("## 14:30:00 — Task Created"), 1)

    def test_unrelated_content_after_journaled_offset_is_not_consumed(self):
        event = {
            "id": "7d8f23d4-2e61-4d99-8afd-81a3b2c89b83",
            "event_type": "task_created",
            "occurred_at": "2026-09-28T14:30:00+02:00",
            "timezone_name": "CEST",
            "utc_offset": "+02:00",
            "payload": {"status": "active", "title": "Boundary task"},
        }
        daily_file, append_offset = prepare_event_append(self.vault, event)
        with daily_file.open("ab") as handle:
            handle.write(b"#")

        append_event(self.vault, event, append_offset=append_offset)
        content = daily_file.read_text(encoding="utf-8")

        self.assertIn(
            f"#\n\n<!-- FocusLog Event Start: {event['id']} -->\n\n"
            "## 14:30:00 — Task Created",
            content,
        )
        self.assertEqual(content.count("## 14:30:00 — Task Created"), 1)

    def test_concurrent_retries_claim_a_pending_event_only_once(self):
        self.service.create_task("Concurrent retry")
        self.service._set_setting("vault_path", str(self.vault))
        other_service = FocusLogService(self.database_path, clock=FixedClock())
        first_attempt_started = threading.Event()
        attempts = []
        errors = []
        real_append = append_event

        def delayed_append(vault_path, event, append_offset=None):
            attempts.append(event["id"])
            first_attempt_started.set()
            time.sleep(0.2)
            real_append(vault_path, event, append_offset)

        def retry(service):
            try:
                service.retry_pending_events()
            except Exception as error:  # pragma: no cover - captured for assertion
                errors.append(error)

        with patch("focuslog.service.append_event", delayed_append):
            first = threading.Thread(target=retry, args=(self.service,))
            second = threading.Thread(target=retry, args=(other_service,))
            first.start()
            self.assertTrue(first_attempt_started.wait(timeout=2))
            second.start()
            first.join(timeout=3)
            second.join(timeout=3)

        self.assertFalse(errors)
        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertEqual(len(attempts), 1)


if __name__ == "__main__":
    unittest.main()
