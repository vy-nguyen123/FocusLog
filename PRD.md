# Product Requirements Document: FocusLog

**Document type:** Short Product Requirements Document  
**Platform:** Windows desktop  
**Scope:** Student assignment, Version 1

---

## 1. Product name

**FocusLog**

FocusLog combines basic task management, Pomodoro focus sessions, local history, and append-only Obsidian activity logging in one offline Windows desktop application.

---

## 2. Product purpose

FocusLog helps a user choose a task or describe an activity, focus on it for a set amount of time, and retain a clear record of the work completed.

The application is designed to be:

- Simple.
- Offline-first.
- Private.
- Easy to understand.
- Small enough to complete as a student project.

Local application data is the main source of truth. Obsidian provides a readable, append-only journal of important task and focus events.

---

## 3. Intended user and problem

### Intended user

A single student or individual user working on a Windows computer who:

- Manages a small list of tasks.
- Uses timed focus sessions.
- Wants local data rather than a cloud account.
- Uses Obsidian to keep a long-term activity record.

### Problem

Task lists and focus timers are often separate. This makes it harder to see what work a focus session was connected to and to keep a permanent record.

FocusLog combines these activities into one workflow:

1. Choose the work.
2. Run a focus session.
3. Review the result.
4. Record important events in Obsidian.

---

## 4. Core features

### 4.1 Task management

The user can:

- Create tasks.
- View tasks.
- Rename tasks.
- Complete tasks.
- Reopen completed tasks.
- Delete tasks.

Active tasks appear first. Completed tasks remain visible below them.

### 4.2 Focus timer

The user can:

- Link a session to a selected task or enter a short activity description.
- Start a focus session.
- Pause and resume it.
- Stop it early.
- Allow it to complete automatically when the timer reaches zero.

The default focus duration is 25 minutes.

### 4.3 Break timer

The user can manually start an optional break after completing a focus session.

The break timer supports:

- Start.
- Pause.
- Resume.
- Stop.

The default break duration is 5 minutes.

### 4.4 Editable durations

The user can change focus and break durations in Settings.

Changes apply to the next timer and do not modify a timer already in progress.

### 4.5 Focus history

The app stores completed and cancelled focus sessions locally.

History is displayed as a read-only, newest-first list.

### 4.6 Offline persistence

Tasks, settings, focus history, vault configuration, and pending Obsidian events are stored locally and survive closing and reopening the app.

---

## 5. Custom features

### 5.1 Task-aware focus sessions

A focus session can be connected to either:

- A selected task, or
- A typed short activity description.

This creates a direct relationship between planned work and recorded focus time.

### 5.2 Append-only Obsidian journal

Important events are written as Markdown to a user-selected Obsidian vault.

The app never silently replaces previous events. Each task or focus action creates a new journal entry.

### 5.3 Reliable pending-event queue

If Obsidian is unavailable, the application continues working and keeps events in a local pending queue.

The user can see:

- The pending-event count.
- The latest logging error.
- A Retry button.

---

## 6. Non-goals

Version 1 will not include:

- User accounts.
- Cloud storage or synchronization.
- Collaboration or task sharing.
- Multiple users.
- Complex analytics.
- Mobile, web, macOS, or Linux versions.
- Advanced history search or filtering.
- History deletion.
- Local data import, export, or backup tools.
- Automatic migration of old logs when changing vaults.
- Break history.
- Obsidian logging for break events.
- Obsidian logging for focus pause and resume events.
- Integrations other than local Obsidian Markdown logging.

---

## 7. Main user flow

1. The user opens FocusLog.
2. The app restores saved tasks, settings, history, and Obsidian status.
3. The user creates or selects a task, or enters a short activity description.
4. The user starts the focus timer.
5. The user may pause, resume, or stop the session.
6. If the timer reaches zero:
   - The session is marked completed.
   - History records its planned and actual duration.
   - A completed event is sent or queued for Obsidian.
   - The app displays a message and plays a sound.
7. If the user stops early:
   - The session is marked cancelled.
   - Actual focused time is recorded.
   - A cancelled event is sent or queued for Obsidian.
8. The user may manually start a break.
9. The user can review completed and cancelled sessions in History.

---

## 8. Testable acceptance criteria

### 8.1 General

- The app starts and remains usable without an internet connection.
- Data created before closing the app is available after reopening it.
- The project can be installed and run from a clean repository clone by following the README.

### 8.2 Tasks

- The user can create a task with a valid non-empty title.
- The user can view active and completed tasks.
- The user can rename a task.
- The user can complete and reopen a task.
- The user can delete a task after confirming the action.
- Active tasks appear before completed tasks.
- Duplicate task titles are allowed and remain separate.
- Deleting a task does not remove its previous focus history.
- A task linked to an active session cannot be renamed, completed, or deleted until the session ends.

### 8.3 Focus sessions

- A session cannot start without either a selected task or a non-empty activity description.
- The user can start, pause, resume, and stop a focus session.
- Paused time is not counted as focused time.
- The linked task or description cannot change after the session starts.
- A session that reaches zero is saved as completed.
- A session stopped before zero is saved as cancelled.
- Completed and cancelled sessions include actual focused time.
- Closing the app during an active or paused session saves it as cancelled.
- A completed timer produces an in-app message and sound.

### 8.4 Breaks and settings

- The user can change focus and break durations.
- A duration change does not alter a timer already running.
- A break starts only when the user starts it manually.
- The user can start, pause, resume, and stop a break.
- Breaks do not appear in History or Obsidian.

### 8.5 History

- Completed and cancelled focus sessions appear in History.
- History is ordered newest first.
- Each entry shows:
  - Task or activity description.
  - Date and time.
  - Planned duration.
  - Actual focused time.
  - Completed or cancelled status.
- History entries cannot be edited or deleted.

### 8.6 Obsidian

- The app accepts only a selected folder containing an `.obsidian` folder.
- Events are written to `Productivity Logs/YYYY-MM-DD.md`.
- New events are appended without replacing previous content.
- Each entry contains all required event fields.
- Task creation, rename, completion, reopening, and deletion are logged.
- Focus start, completion, and cancellation are logged.
- Focus pause, resume, and break events are not logged.
- Events remain queued when no valid vault is available.
- The interface shows pending-event count and the latest error.
- Retry writes pending events after the vault becomes available.
- Retried events retain their original occurrence time and daily-file date.
- Retrying an event does not create a duplicate entry.
- Changing vaults sends future and pending events to the new vault without copying old log files.

---

## 9. Technical approach

### 9.1 Desktop framework

**Recommendation: Python with Tkinter**

Tkinter is included with standard Windows Python installations and provides:

- Native desktop windows.
- Buttons, text fields, lists, and navigation.
- A Windows folder-selection dialog.
- Timer callbacks through `after()`.
- A small dependency footprint.

This is suitable for a beginner because it avoids the additional web technologies and build tools required by frameworks such as Electron.

Python’s Windows `winsound` module can provide the timer-completion sound without adding an audio dependency.

### 9.2 Local storage

**Recommendation: SQLite using Python’s built-in `sqlite3` module**

SQLite will store:

- Tasks.
- Focus sessions.
- Settings.
- Selected vault location.
- Pending Obsidian events.
- Active-session recovery information.

SQLite fits this project because it:

- Works offline.
- Stores everything in one local database file.
- Is included with Python.
- Supports reliable transactions.
- Is safer than manually rewriting a JSON file after every change.
- Makes task, history, and pending-event relationships straightforward.

Hidden UUIDs should identify tasks, sessions, and Obsidian events. This allows duplicate task titles while keeping records separate.

### 9.3 Obsidian integration

Obsidian integration will use normal local filesystem operations rather than an Obsidian plugin or API.

The app will:

1. Open a folder-selection dialog.
2. Verify that the folder contains `.obsidian`.
3. Create `Productivity Logs` if needed.
4. Create or append to the correct daily Markdown file.
5. Write files using UTF-8 encoding.

This approach is simple because an Obsidian vault is a normal folder containing Markdown files.

### 9.4 Timer implementation

The displayed timer should be based on stored timestamps rather than only subtracting one from a counter every second.

This avoids large timing errors if the interface briefly freezes.

Paused time will be excluded from actual focused time.

### 9.5 Resolved implementation decisions

#### Crash or power loss

The app will periodically save a lightweight elapsed-time checkpoint for an active session.

If the app discovers an unfinished session on its next launch, it will:

- Mark the session cancelled.
- Use the latest saved elapsed time.
- Add the cancellation to History.
- Queue the cancellation for Obsidian.

The session will not resume automatically.

#### Windows lock or sleep

The timer will continue based on elapsed clock time while Windows is locked or asleep.

When the app resumes:

- If time remains, it displays the correct remaining time.
- If the planned end time passed, the session is completed.
- Actual focused time for a normally completed session is capped at its planned duration.

This is simpler and more predictable than adding Windows-specific sleep and lock monitoring.

#### Active task changes

A task linked to an active session cannot be:

- Renamed.
- Completed.
- Deleted.

This keeps the task information stable for the duration of the session.

#### Duplicate-safe Obsidian retries

Each logged event receives a UUID.

The event ID is included in Markdown. Before retrying an uncertain event, the app checks the relevant daily file for that ID:

- If found, the event is marked sent locally.
- If not found, it is appended.

This prevents duplicate entries after an unexpected shutdown during logging.

---

## 10. Obsidian vault structure and Markdown logging format

### 10.1 Folder structure

```text
Selected Obsidian Vault/
├── .obsidian/
└── Productivity Logs/
    ├── 2026-09-27.md
    ├── 2026-09-28.md
    └── ...
```

The file date is based on the event’s original local date.

### 10.2 Daily file heading

A new daily file begins with:

```markdown
# Productivity Log — 2026-09-27
```

### 10.3 Event format

Each event is appended as its own section:

```markdown
## 14:30:00 — Focus Session Completed

- Event ID: `7d8f23d4-2e61-4d99-8afd-81a3b2c89b83`
- Date: 2026-09-27
- Time: 14:30:00
- Timezone: Romance Daylight Time
- UTC offset: +02:00
- Event type: focus_completed
- Status: completed
- Task/activity: Write research summary
- Planned duration: 25 minutes
- Actual duration: 25 minutes
```

A task rename event includes the previous and new titles:

```markdown
## 13:10:00 — Task Renamed

- Event ID: `4c353d52-03bb-4294-a87f-e544d2096428`
- Date: 2026-09-27
- Time: 13:10:00
- Timezone: Romance Daylight Time
- UTC offset: +02:00
- Event type: task_renamed
- Status: active
- Previous title: Write report
- New title: Write final report
```

Only fields relevant to the event are included after the required common fields.

### 10.4 Append-only rule

The application must:

- Append new sections to the end of the daily file.
- Never rewrite previous event sections.
- Never remove existing entries.
- Never silently replace unrelated Markdown content.
- Represent later changes as new events.

---

## 11. Screen layout

### 11.1 Main Tasks/Timer

The main screen contains:

**Task area**

- New-task input.
- Add button.
- Active task list.
- Completed task list.
- Rename, complete/reopen, and delete actions.

**Timer area**

- Selected task display.
- Short activity-description input.
- Remaining time.
- Current timer state.
- Start, pause/resume, and stop controls.
- Manual Start Break action after focus completion.
- In-app completion message.

Only one source is used for a session: a selected task or a typed activity description.

### 11.2 History

The History screen contains:

- A read-only newest-first session list.
- Task or activity description.
- Date and time.
- Planned duration.
- Actual duration.
- Completed or cancelled status.

No editing, deletion, search, or filtering is included.

### 11.3 Settings

The Settings screen contains:

- Focus-duration setting.
- Break-duration setting.
- Selected Obsidian vault path.
- Select/Change Vault button.
- Vault validation result.
- Pending-event count.
- Latest Obsidian error.
- Retry button.

---

## 12. Usability decisions

- Active tasks appear before completed tasks.
- Completed tasks remain visible instead of disappearing.
- Duplicate titles are allowed because hidden IDs keep tasks separate.
- Task deletion always requires confirmation.
- A task attached to an active session is protected from changes.
- A session requires a task or short description, preventing unclear history entries.
- The linked work is locked after the session begins.
- Stopping early always means cancelled.
- Reaching zero always means completed.
- Breaks start manually so the user remains in control.
- Settings changes apply to the next timer.
- Timer completion uses both a visible message and sound.
- History is read-only to keep the first version simple and reliable.
- Obsidian failures do not block tasks or focus sessions.
- Logging failures are visible rather than silent.

---

## 13. Rejected alternative

### Electron with JSON-file storage

Electron was considered because it allows desktop applications to be built with HTML, CSS, and JavaScript.

It was rejected for Version 1 because it would introduce:

- A larger dependency and build setup.
- More technologies for a beginner to manage.
- Higher application resource usage.
- More packaging complexity.
- Manual safety concerns when rewriting JSON data.

Python, Tkinter, and SQLite provide the required Windows desktop interface and reliable local persistence with a smaller technical scope.

---

## 14. Design artifacts to create next

Before coding, create the following small design artifacts:

1. **Low-fidelity wireframes**
   - Main Tasks/Timer screen.
   - History screen.
   - Settings screen.

2. **Main user-flow diagram**
   - Create/select work.
   - Start focus.
   - Complete or cancel.
   - Save History.
   - Write or queue the Obsidian event.

3. **Timer-state diagram**
   - Idle.
   - Running.
   - Paused.
   - Completed.
   - Cancelled.
   - Break running.

4. **Simple data model**
   - Tasks.
   - Focus sessions.
   - Settings.
   - Pending Obsidian events.

5. **Obsidian structure mock-up**
   - Vault folder layout.
   - Daily Markdown file.
   - Example task and focus events.

These artifacts are sufficient to guide implementation without adding unnecessary design work.