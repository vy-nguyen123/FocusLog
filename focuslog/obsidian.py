"""Append-only Markdown writing for a local Obsidian vault."""

from datetime import datetime
from pathlib import Path
from typing import Any

EVENT_TITLES = {
    "task_created": "Task Created",
    "task_renamed": "Task Renamed",
    "task_completed": "Task Completed",
    "task_reopened": "Task Reopened",
    "task_deleted": "Task Deleted",
    "focus_started": "Focus Session Started",
    "focus_completed": "Focus Session Completed",
    "focus_cancelled": "Focus Session Cancelled",
}

FIELD_LABELS = {
    "status": "Status",
    "title": "Task",
    "previous_title": "Previous title",
    "new_title": "New title",
    "subject": "Task/activity",
    "planned_seconds": "Planned duration",
    "actual_seconds": "Actual duration",
}


def is_valid_vault(path: Path) -> bool:
    """A vault is a folder containing an .obsidian directory."""
    return path.is_dir() and (path / ".obsidian").is_dir()


def _utc_offset(timestamp: datetime) -> str:
    offset = timestamp.utcoffset()
    if offset is None:
        return "+00:00"
    total_minutes = int(offset.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "-"
    hours, minutes = divmod(abs(total_minutes), 60)
    return f"{sign}{hours:02d}:{minutes:02d}"


def _format_duration(seconds: int) -> str:
    minutes, remaining_seconds = divmod(max(0, int(seconds)), 60)
    if remaining_seconds == 0:
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    if minutes == 0:
        return f"{remaining_seconds} second{'s' if remaining_seconds != 1 else ''}"
    return f"{minutes} min {remaining_seconds} sec"


def render_event(event: dict[str, Any]) -> str:
    """Render one stored event using its original local timestamp."""
    timestamp = datetime.fromisoformat(event["occurred_at"])
    event_type = event["event_type"]
    payload = event["payload"]
    timezone_name = event.get("timezone_name") or timestamp.tzname() or "Local time"
    utc_offset = event.get("utc_offset") or _utc_offset(timestamp)
    lines = [
        f"<!-- FocusLog Event Start: {event['id']} -->",
        "",
        f"## {timestamp:%H:%M:%S} — {EVENT_TITLES[event_type]}",
        "",
        f"- Event ID: `{event['id']}`",
        f"- Date: {timestamp:%Y-%m-%d}",
        f"- Time: {timestamp:%H:%M:%S}",
        f"- Timezone: {timezone_name}",
        f"- UTC offset: {utc_offset}",
        f"- Event type: {event_type}",
    ]
    for key in (
        "status",
        "title",
        "previous_title",
        "new_title",
        "subject",
        "planned_seconds",
        "actual_seconds",
    ):
        if key not in payload or payload[key] is None:
            continue
        value = payload[key]
        if key in {"planned_seconds", "actual_seconds"}:
            value = _format_duration(value)
        lines.append(f"- {FIELD_LABELS[key]}: {value}")
    lines.extend(("", f"<!-- FocusLog Event Complete: {event['id']} -->"))
    return "\n".join(lines) + "\n"


def _daily_file(vault_path: Path, event: dict[str, Any]) -> tuple[Path, datetime]:
    if not is_valid_vault(vault_path):
        raise OSError("The configured Obsidian vault is unavailable or invalid.")

    timestamp = datetime.fromisoformat(event["occurred_at"])
    log_directory = vault_path / "Productivity Logs"
    log_directory.mkdir(parents=True, exist_ok=True)
    return log_directory / f"{timestamp:%Y-%m-%d}.md", timestamp


def _section_separator(existing: bytes) -> bytes:
    if not existing:
        return b""
    if existing.endswith(b"\n\n"):
        return b""
    if existing.endswith(b"\n"):
        return b"\n"
    return b"\n\n"


def prepare_event_append(
    vault_path: Path, event: dict[str, Any]
) -> tuple[Path, int]:
    """Create a clean section boundary and return its durable byte offset."""
    daily_file, timestamp = _daily_file(vault_path, event)
    existing = daily_file.read_bytes() if daily_file.exists() else b""
    if not existing:
        header = f"# Productivity Log — {timestamp:%Y-%m-%d}\n\n".encode("utf-8")
        with daily_file.open("ab") as handle:
            handle.write(header)
        existing = header

    separator = _section_separator(existing)
    if separator:
        with daily_file.open("ab") as handle:
            handle.write(separator)
        existing += separator
    return daily_file, len(existing)


def append_event(
    vault_path: Path,
    event: dict[str, Any],
    append_offset: int | None = None,
) -> None:
    """Append or resume one event without changing existing Markdown."""
    daily_file, timestamp = _daily_file(vault_path, event)

    existing = daily_file.read_bytes() if daily_file.exists() else b""
    marker = f"<!-- FocusLog Event Complete: {event['id']} -->".encode("utf-8")
    rendered = render_event(event).encode("utf-8")
    start_marker = f"<!-- FocusLog Event Start: {event['id']} -->".encode("utf-8")
    text_to_append = rendered
    continuing_partial_event = False

    if marker in existing:
        return

    if append_offset is not None and 0 <= append_offset <= len(existing):
        partial = existing[append_offset:]
        if partial.startswith(start_marker) and rendered.startswith(partial):
            text_to_append = rendered[len(partial):]
            continuing_partial_event = True

    with daily_file.open("ab") as handle:
        if not existing:
            handle.write(
                f"# Productivity Log — {timestamp:%Y-%m-%d}\n\n".encode("utf-8")
            )
        elif not continuing_partial_event:
            handle.write(_section_separator(existing))
        handle.write(text_to_append)
        if not text_to_append.endswith(b"\n"):
            handle.write(b"\n")
        handle.write(b"\n")
