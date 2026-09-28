import tempfile
import tkinter as tk
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from focuslog.app import FocusLogApp


class ApplicationNavigationTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = tk.Tk()
        self.root.geometry("800x600+10000+10000")
        self.app = FocusLogApp(
            self.root,
            database_path=Path(self.temporary_directory.name) / "focuslog.db",
        )
        self.root.update()

    def tearDown(self):
        self.app.close()
        self.temporary_directory.cleanup()

    def test_application_starts_on_tasks_screen(self):
        self.assertEqual(self.root.title(), "FocusLog")
        self.assertEqual(self.app.current_screen, "Tasks")
        self.assertTrue(self.app.screens["Tasks"].winfo_ismapped())

    def test_each_navigation_button_shows_its_screen(self):
        for screen_name in ("History", "Settings", "Tasks"):
            with self.subTest(screen_name=screen_name):
                self.app.navigation_buttons[screen_name].invoke()
                self.root.update()

                self.assertEqual(self.app.current_screen, screen_name)
                self.assertTrue(self.app.screens[screen_name].winfo_ismapped())

    def test_task_and_focus_controls_are_wired_to_persistence(self):
        tasks = self.app.screens["Tasks"]
        tasks.new_task_var.set("UI task")
        tasks.add_button.invoke()
        self.root.update()
        created = self.app.service.list_tasks()
        self.assertEqual(created[0]["title"], "UI task")

        tasks.select_task(created[0]["id"])
        tasks.start_button.invoke()
        self.assertIsNotNone(self.app.service.get_active_session())
        tasks.stop_button.invoke()
        self.assertIsNone(self.app.service.get_active_session())

        self.app.show_screen("History")
        history = self.app.screens["History"]
        self.assertEqual(len(history.history.get_children()), 1)

    def test_settings_controls_save_durations(self):
        settings = self.app.screens["Settings"]
        settings.focus_var.set("40")
        settings.break_var.set("10")
        settings.save_button.invoke()

        self.assertEqual(self.app.service.get_durations(), (40, 10))

    def test_completing_selected_task_clears_focus_selection(self):
        task = self.app.service.create_task("Selected task")
        tasks = self.app.screens["Tasks"]
        tasks.select_task(task["id"])

        self.app.service.complete_task(task["id"])
        tasks.refresh()

        self.assertIsNone(tasks.selected_task_id)
        self.assertEqual(
            tasks.current_focus_var.get(),
            "Select a task or describe an activity",
        )

    def test_pause_at_deadline_shows_completion_and_enables_break(self):
        current = datetime(2026, 9, 28, 9, 0, tzinfo=timezone.utc)
        self.app.service.clock = lambda: current
        self.app.service.set_durations(1, 5)
        self.app.service.start_focus(activity_description="Boundary UI")
        current += timedelta(seconds=60)
        self.app.play_completion_sound = lambda: None
        tasks = self.app.screens["Tasks"]

        tasks.pause_resume()

        self.assertTrue(tasks.break_allowed)
        self.assertIn("Focus complete", tasks.status_var.get())


if __name__ == "__main__":
    unittest.main()
