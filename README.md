# FocusLog

FocusLog is an offline Windows desktop productivity application built with Python, Tkinter, SQLite, and local Markdown files.

## Version 1 features

- Create, rename, complete, reopen, and delete tasks.
- Run focus sessions linked to a task or short activity description.
- Pause, resume, stop, or automatically complete focus sessions.
- Run optional manual break timers.
- Review read-only completed and cancelled focus history.
- Configure focus and break durations.
- Append task and focus events to an Obsidian vault.
- Queue unavailable Obsidian writes and retry them safely.
- Recover interrupted focus sessions as cancelled.

## Requirements

- Windows
- Python 3.11 or newer with Tkinter

FocusLog uses only Python standard-library modules. No third-party packages are required.

## Run from a clean clone

1. Install Python 3.11 or newer from <https://www.python.org/downloads/windows/>.
2. During installation, enable **Add Python to PATH** and include **tcl/tk and IDLE**.
3. Open a terminal in the cloned `FocusLog` directory.
4. Run:

```bash
python main.py
```

The SQLite database is created outside the repository at:

```text
%LOCALAPPDATA%\FocusLog\focuslog.db
```

## Obsidian setup

Open **Settings**, choose **Select Vault**, and select the root folder of an Obsidian vault. The selected folder must contain `.obsidian`.

FocusLog appends events to:

```text
Selected Vault\Productivity Logs\YYYY-MM-DD.md
```

If the vault is unavailable, events remain in the local SQLite pending queue. Reconnect the vault and use **Retry Pending Logs**.

## Test

```bash
python -m unittest discover -s tests -v
```
