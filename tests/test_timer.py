import unittest

from focuslog.timer import BreakTimer, TimerStateError, format_duration


class BreakTimerTests(unittest.TestCase):
    def test_manual_break_can_pause_resume_and_stop(self):
        timer = BreakTimer()
        timer.start(300, now=100.0)
        self.assertEqual(timer.remaining(now=110.0), 290)

        timer.pause(now=110.0)
        self.assertEqual(timer.remaining(now=150.0), 290)
        timer.resume(now=150.0)
        self.assertEqual(timer.remaining(now=160.0), 280)
        timer.stop()

        self.assertEqual(timer.state, "idle")

    def test_break_does_not_start_until_requested(self):
        timer = BreakTimer()
        self.assertEqual(timer.state, "idle")
        with self.assertRaises(TimerStateError):
            timer.pause(now=1.0)

    def test_break_completes_at_zero(self):
        timer = BreakTimer()
        timer.start(5, now=10.0)
        self.assertEqual(timer.remaining(now=16.0), 0)
        self.assertEqual(timer.state, "completed")

    def test_duration_format(self):
        self.assertEqual(format_duration(65), "01:05")


if __name__ == "__main__":
    unittest.main()
