from datetime import datetime, timedelta, timezone
import tempfile
import unittest
from pathlib import Path

from focuslog.service import FocusLogService, ProtectedTaskError, ValidationError


class FakeClock:
    def __init__(self):
        self.current = datetime(2026, 9, 28, 9, 0, tzinfo=timezone(timedelta(hours=2), "CEST"))

    def __call__(self):
        return self.current

    def advance(self, seconds):
        self.current += timedelta(seconds=seconds)


class FocusLogServiceTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "focuslog.db"
        self.clock = FakeClock()
        self.service = FocusLogService(self.database_path, clock=self.clock)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_task_lifecycle_allows_duplicates_and_orders_active_first(self):
        first = self.service.create_task("Write report")
        second = self.service.create_task("Write report")
        self.service.rename_task(first["id"], "Write final report")
        self.service.complete_task(first["id"])

        tasks = self.service.list_tasks()
        self.assertEqual([task["id"] for task in tasks], [second["id"], first["id"]])
        self.assertEqual(tasks[1]["title"], "Write final report")
        self.assertTrue(tasks[1]["is_completed"])

        self.service.reopen_task(first["id"])
        self.assertFalse(self.service.get_task(first["id"])["is_completed"])
        self.service.delete_task(second["id"])
        self.assertIsNone(self.service.get_task(second["id"]))

    def test_empty_task_title_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.service.create_task("   ")

    def test_active_task_is_protected_until_focus_session_ends(self):
        task = self.service.create_task("Protected work")
        self.service.start_focus(task_id=task["id"])

        for operation in (
            lambda: self.service.rename_task(task["id"], "Changed"),
            lambda: self.service.complete_task(task["id"]),
            lambda: self.service.delete_task(task["id"]),
        ):
            with self.assertRaises(ProtectedTaskError):
                operation()

        self.service.stop_focus()
        self.service.rename_task(task["id"], "Changed")
        self.assertEqual(self.service.get_task(task["id"])["title"], "Changed")

    def test_focus_requires_exactly_one_work_source(self):
        task = self.service.create_task("Task")
        with self.assertRaises(ValidationError):
            self.service.start_focus()
        with self.assertRaises(ValidationError):
            self.service.start_focus(task_id=task["id"], activity_description="Other")

    def test_pause_time_is_excluded_and_stop_creates_cancelled_history(self):
        self.service.set_durations(1, 5)
        self.service.start_focus(activity_description="Study")
        self.clock.advance(20)
        self.service.pause_focus()
        self.clock.advance(30)
        self.service.resume_focus()
        self.clock.advance(10)
        session = self.service.stop_focus()

        self.assertEqual(session["status"], "cancelled")
        self.assertEqual(session["focused_seconds"], 30)
        history = self.service.list_history()
        self.assertEqual(history[0]["subject"], "Study")
        self.assertEqual(history[0]["planned_seconds"], 60)
        self.assertEqual(history[0]["focused_seconds"], 30)

    def test_reaching_zero_completes_and_caps_actual_duration(self):
        self.service.set_durations(1, 5)
        self.service.start_focus(activity_description="Read")
        self.clock.advance(75)

        session = self.service.update_focus()

        self.assertEqual(session["status"], "completed")
        self.assertEqual(session["focused_seconds"], 60)
        self.assertIsNone(self.service.get_active_session())

    def test_stop_pause_and_close_at_zero_complete_instead_of_cancel(self):
        actions = (
            lambda service: service.stop_focus(),
            lambda service: service.pause_focus(),
            lambda service: service.cancel_active_on_close(),
        )
        for action in actions:
            with self.subTest(action=action):
                with tempfile.TemporaryDirectory() as directory:
                    clock = FakeClock()
                    service = FocusLogService(
                        Path(directory) / "focuslog.db", clock=clock
                    )
                    service.set_durations(1, 5)
                    service.start_focus(activity_description="Boundary")
                    clock.advance(60)

                    session = action(service)

                    self.assertEqual(session["status"], "completed")
                    self.assertEqual(session["focused_seconds"], 60)

    def test_deleting_task_preserves_session_subject_in_history(self):
        task = self.service.create_task("Permanent history title")
        self.service.start_focus(task_id=task["id"])
        self.clock.advance(5)
        self.service.stop_focus()
        self.service.delete_task(task["id"])

        history = self.service.list_history()
        self.assertEqual(history[0]["subject"], "Permanent history title")

    def test_settings_persist_between_service_instances(self):
        self.service.set_durations(40, 10)

        reopened = FocusLogService(self.database_path, clock=self.clock)

        self.assertEqual(reopened.get_durations(), (40, 10))

    def test_invalid_duration_is_rejected(self):
        for focus, rest in ((0, 5), (25, -1), (1.5, 5)):
            with self.subTest(focus=focus, rest=rest):
                with self.assertRaises(ValidationError):
                    self.service.set_durations(focus, rest)

    def test_normal_close_cancels_using_current_elapsed_time(self):
        self.service.start_focus(activity_description="Close test")
        self.clock.advance(12)

        session = self.service.cancel_active_on_close()

        self.assertEqual(session["status"], "cancelled")
        self.assertEqual(session["focused_seconds"], 12)

    def test_recovery_uses_last_checkpoint_and_does_not_resume(self):
        self.service.start_focus(activity_description="Crash test")
        self.clock.advance(9)
        self.service.checkpoint_active()
        self.clock.advance(50)

        reopened = FocusLogService(self.database_path, clock=self.clock)
        recovered = reopened.recover_interrupted_session()

        self.assertEqual(recovered["status"], "cancelled")
        self.assertEqual(recovered["focused_seconds"], 9)
        self.assertIsNone(reopened.get_active_session())

    def test_history_order_uses_absolute_time_across_utc_offset_changes(self):
        self.service.set_durations(1, 5)
        self.clock.current = datetime(
            2026, 10, 25, 2, 30, tzinfo=timezone(timedelta(hours=2), "CEST")
        )
        self.service.start_focus(activity_description="Earlier absolute time")
        self.service.stop_focus()
        self.clock.current = datetime(
            2026, 10, 25, 2, 15, tzinfo=timezone(timedelta(hours=1), "CET")
        )
        self.service.start_focus(activity_description="Later absolute time")
        self.service.stop_focus()

        history = self.service.list_history()

        self.assertEqual(history[0]["subject"], "Later absolute time")


if __name__ == "__main__":
    unittest.main()
