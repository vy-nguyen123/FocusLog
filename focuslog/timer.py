"""Small timer helpers used by the Tkinter application."""

import math
import time


class TimerStateError(RuntimeError):
    """Raised when a timer action is invalid for its current state."""


class BreakTimer:
    """In-memory manual break timer; breaks are intentionally not persisted."""

    def __init__(self) -> None:
        self.state = "idle"
        self.planned_seconds = 0
        self._elapsed_seconds = 0.0
        self._running_since: float | None = None

    def start(self, duration_seconds: int, now: float | None = None) -> None:
        if self.state in {"running", "paused"}:
            raise TimerStateError("A break is already in progress.")
        if duration_seconds <= 0:
            raise ValueError("Break duration must be positive.")
        self.planned_seconds = duration_seconds
        self._elapsed_seconds = 0.0
        self._running_since = time.monotonic() if now is None else now
        self.state = "running"

    def pause(self, now: float | None = None) -> None:
        if self.state != "running":
            raise TimerStateError("Only a running break can be paused.")
        current = time.monotonic() if now is None else now
        self._elapsed_seconds += current - self._running_since
        self._running_since = None
        self.state = "paused"

    def resume(self, now: float | None = None) -> None:
        if self.state != "paused":
            raise TimerStateError("Only a paused break can be resumed.")
        self._running_since = time.monotonic() if now is None else now
        self.state = "running"

    def stop(self) -> None:
        self.state = "idle"
        self.planned_seconds = 0
        self._elapsed_seconds = 0.0
        self._running_since = None

    def remaining(self, now: float | None = None) -> int:
        if self.state == "idle":
            return 0
        elapsed = self._elapsed_seconds
        if self.state == "running":
            current = time.monotonic() if now is None else now
            elapsed += current - self._running_since
        remaining = max(0, math.ceil(self.planned_seconds - elapsed))
        if remaining == 0:
            self.state = "completed"
            self._running_since = None
        return remaining


def format_duration(seconds: int) -> str:
    """Format a non-negative duration as MM:SS."""
    minutes, remaining_seconds = divmod(max(0, int(seconds)), 60)
    return f"{minutes:02d}:{remaining_seconds:02d}"
