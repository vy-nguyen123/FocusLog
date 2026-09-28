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

1. In Obsidian, choose **Create new vault**, select its location, and open it once.
2. In FocusLog, open **Settings** and choose **Select Vault**.
3. Select the vault's root folder, not a folder inside the vault.

The selected folder must contain an `.obsidian` folder. Obsidian creates this folder when it initializes a vault, and FocusLog rejects folders that do not contain it.

FocusLog appends events to:

```text
Selected Vault\Productivity Logs\YYYY-MM-DD.md
```

If the vault is unavailable, events remain in the local SQLite pending queue. Reconnect the vault and use **Retry Pending Logs**.

## Basic usage

### Tasks

- Enter a task title and create the task.
- Select a task to rename, complete, reopen, or delete it.
- Deleting a task requires confirmation.
- A task linked to a running or paused focus session cannot be changed or deleted until that session ends.

### Focus Timer

- Select an active task or enter a short activity description.
- Choose **Start Focus**, then pause, resume, or stop the session as needed.
- A session that reaches zero is completed automatically. Stopping early records it as cancelled.
- Break timers are started manually and are not added to History or Obsidian logs.

### History

- Open **History** to review completed and cancelled focus sessions.
- History is read-only and shows the planned and actual focused duration, newest first.

### Settings

- Open **Settings** to change the focus and break durations.
- Select or replace the Obsidian vault from this screen.
- Check the pending-log count and latest logging error, then choose **Retry Pending Logs** after restoring access to an unavailable vault.

## Test

```bash
python -m unittest discover -s tests -v
```
