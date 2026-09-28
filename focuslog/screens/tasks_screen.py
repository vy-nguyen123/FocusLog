"""Tasks and timer screen."""

import time
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from focuslog.service import ProtectedTaskError, SessionStateError, ValidationError
from focuslog.timer import BreakTimer, TimerStateError, format_duration


class TasksScreen(ttk.Frame):
    def __init__(self, parent: tk.Misc, app) -> None:
        super().__init__(parent, style="Page.TFrame", padding=(24, 22))
        self.app = app
        self.break_timer = BreakTimer()
        self.break_allowed = False
        self.selected_task_id: str | None = None
        self._last_checkpoint = time.monotonic()

        self.columnconfigure(0, weight=7)
        self.columnconfigure(1, weight=4)
        self.rowconfigure(0, weight=1)
        self._build_task_card()
        self._build_timer_card()
        self.activity_var.trace_add("write", self._activity_changed)
        self.refresh()

    def _build_task_card(self) -> None:
        card = ttk.Frame(self, style="Card.TFrame", padding=24)
        card.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        card.columnconfigure(0, weight=1)
        card.rowconfigure(5, weight=1)

        ttk.Label(card, text="Task Management", style="Heading.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 22)
        )
        ttk.Label(card, text="New Task", style="FieldLabel.TLabel").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(0, 7)
        )
        self.new_task_var = tk.StringVar()
        self.new_task_entry = ttk.Entry(card, textvariable=self.new_task_var)
        self.new_task_entry.grid(row=2, column=0, sticky="ew", padx=(0, 12), ipady=7)
        self.new_task_entry.bind("<Return>", lambda _event: self.add_task())
        self.add_button = ttk.Button(
            card, text="Add Task", style="Primary.TButton", command=self.add_task
        )
        self.add_button.grid(row=2, column=1, sticky="ew", ipady=5)
        ttk.Separator(card).grid(
            row=3, column=0, columnspan=2, sticky="ew", pady=20
        )

        self.task_lists = ttk.Frame(card, style="Card.TFrame")
        self.task_lists.grid(row=4, column=0, columnspan=2, sticky="nsew")
        self.task_lists.columnconfigure(0, weight=1)
        self.selected_var = tk.StringVar(value="")

    def _build_timer_card(self) -> None:
        card = ttk.Frame(self, style="Card.TFrame", padding=30)
        card.grid(row=0, column=1, sticky="nsew", padx=(12, 0))
        card.columnconfigure((0, 1, 2), weight=1)

        ttk.Label(card, text="CURRENT FOCUS", style="Eyebrow.TLabel").grid(
            row=0, column=0, columnspan=3, pady=(12, 8)
        )
        self.current_focus_var = tk.StringVar(
            value="Select a task or describe an activity"
        )
        ttk.Label(
            card,
            textvariable=self.current_focus_var,
            style="Centered.TLabel",
            wraplength=350,
        ).grid(row=1, column=0, columnspan=3, pady=(0, 20))
        ttk.Label(card, text="OR", style="Muted.TLabel").grid(
            row=2, column=0, columnspan=3, pady=(0, 10)
        )
        ttk.Label(card, text="Activity Description", style="FieldLabel.TLabel").grid(
            row=3, column=0, columnspan=3, sticky="w", pady=(0, 7)
        )
        self.activity_var = tk.StringVar()
        self.activity_entry = ttk.Entry(card, textvariable=self.activity_var)
        self.activity_entry.grid(
            row=4, column=0, columnspan=3, sticky="ew", ipady=7, pady=(0, 28)
        )

        timer_panel = ttk.Frame(card, style="Timer.TFrame", padding=30)
        timer_panel.grid(row=5, column=0, columnspan=3, sticky="ew")
        self.timer_var = tk.StringVar(value="25:00")
        ttk.Label(timer_panel, textvariable=self.timer_var, style="Timer.TLabel").pack()

        self.start_button = ttk.Button(
            card,
            text="Start Session",
            style="Primary.TButton",
            command=self.start_focus,
        )
        self.start_button.grid(
            row=6, column=0, sticky="ew", padx=(0, 6), pady=(26, 16), ipady=7
        )
        self.pause_button = ttk.Button(card, text="Pause", command=self.pause_resume)
        self.pause_button.grid(
            row=6, column=1, sticky="ew", padx=6, pady=(26, 16), ipady=7
        )
        self.stop_button = ttk.Button(card, text="Stop", command=self.stop_timer)
        self.stop_button.grid(
            row=6, column=2, sticky="ew", padx=(6, 0), pady=(26, 16), ipady=7
        )
        self.break_button = ttk.Button(card, command=self.start_break)
        self.break_button.grid(
            row=7, column=0, columnspan=3, sticky="ew", ipady=7
        )
        ttk.Separator(card).grid(
            row=8, column=0, columnspan=3, sticky="ew", pady=28
        )
        self.status_var = tk.StringVar(value="●  Ready to focus")
        ttk.Label(card, textvariable=self.status_var, style="Muted.TLabel").grid(
            row=9, column=0, columnspan=3
        )

    def _activity_changed(self, *_args) -> None:
        if self.activity_var.get().strip() and self.selected_task_id:
            self.selected_task_id = None
            self.selected_var.set("")
        self._refresh_current_focus()

    def add_task(self) -> None:
        try:
            self.app.service.create_task(self.new_task_var.get())
        except ValidationError as error:
            messagebox.showerror("Invalid task", str(error), parent=self)
            return
        self.new_task_var.set("")
        self.app.refresh_all()

    def select_task(self, task_id: str) -> None:
        if self.app.service.get_active_session() is not None:
            return
        task = self.app.service.get_task(task_id)
        if task is None or task["is_completed"]:
            return
        self.selected_task_id = task_id
        self.selected_var.set(task_id)
        self.activity_var.set("")
        self._refresh_current_focus()

    def rename_task(self, task_id: str) -> None:
        task = self.app.service.get_task(task_id)
        if task is None:
            return
        title = simpledialog.askstring(
            "Rename Task", "Task title:", initialvalue=task["title"], parent=self
        )
        if title is None:
            return
        self._run_task_action(lambda: self.app.service.rename_task(task_id, title))

    def complete_task(self, task_id: str) -> None:
        self._run_task_action(lambda: self.app.service.complete_task(task_id))

    def reopen_task(self, task_id: str) -> None:
        self._run_task_action(lambda: self.app.service.reopen_task(task_id))

    def delete_task(self, task_id: str) -> None:
        task = self.app.service.get_task(task_id)
        if task is None:
            return
        confirmed = messagebox.askyesno(
            "Delete Task",
            f'Delete "{task["title"]}"? Previous focus history will remain.',
            parent=self,
        )
        if confirmed:
            self._run_task_action(lambda: self.app.service.delete_task(task_id))

    def _run_task_action(self, action) -> None:
        try:
            action()
        except (ValidationError, ProtectedTaskError) as error:
            messagebox.showerror("Task unavailable", str(error), parent=self)
            return
        self.app.refresh_all()

    def _build_task_row(self, parent: ttk.Frame, task: dict, row: int) -> None:
        item = ttk.Frame(parent, style="ListItem.TFrame", padding=(8, 7))
        item.grid(row=row, column=0, sticky="ew", pady=3)
        item.columnconfigure(1, weight=1)
        if task["is_completed"]:
            ttk.Label(item, text="✓", style="Muted.TLabel").grid(
                row=0, column=0, padx=(2, 9)
            )
            ttk.Label(item, text=task["title"], style="Muted.TLabel").grid(
                row=0, column=1, sticky="w"
            )
            ttk.Button(
                item, text="Reopen", command=lambda: self.reopen_task(task["id"])
            ).grid(row=0, column=2, padx=3)
        else:
            ttk.Radiobutton(
                item,
                variable=self.selected_var,
                value=task["id"],
                command=lambda: self.select_task(task["id"]),
                state=(
                    "disabled"
                    if self.app.service.get_active_session() is not None
                    else "normal"
                ),
            ).grid(row=0, column=0, padx=(0, 6))
            ttk.Label(item, text=task["title"], style="Body.TLabel").grid(
                row=0, column=1, sticky="w"
            )
            ttk.Button(
                item, text="Rename", command=lambda: self.rename_task(task["id"])
            ).grid(row=0, column=2, padx=3)
            ttk.Button(
                item, text="Complete", command=lambda: self.complete_task(task["id"])
            ).grid(row=0, column=3, padx=3)
        ttk.Button(
            item, text="Delete", command=lambda: self.delete_task(task["id"])
        ).grid(row=0, column=4, padx=(3, 0))

    def refresh(self) -> None:
        for child in self.task_lists.winfo_children():
            child.destroy()
        active = [task for task in self.app.service.list_tasks() if not task["is_completed"]]
        completed = [task for task in self.app.service.list_tasks() if task["is_completed"]]
        ttk.Label(
            self.task_lists,
            text=f"Active Tasks ({len(active)})",
            style="Subheading.TLabel",
        ).grid(row=0, column=0, sticky="w", pady=(0, 7))
        row = 1
        for task in active:
            self._build_task_row(self.task_lists, task, row)
            row += 1
        if not active:
            ttk.Label(
                self.task_lists, text="No active tasks", style="Muted.TLabel"
            ).grid(row=row, column=0, sticky="w", pady=8)
            row += 1
        ttk.Label(
            self.task_lists,
            text=f"Completed Tasks ({len(completed)})",
            style="Subheading.TLabel",
        ).grid(row=row, column=0, sticky="w", pady=(20, 7))
        row += 1
        for task in completed:
            self._build_task_row(self.task_lists, task, row)
            row += 1
        if self.selected_task_id:
            selected = self.app.service.get_task(self.selected_task_id)
            if selected is None or selected["is_completed"]:
                self.selected_task_id = None
                self.selected_var.set("")
        self._refresh_timer_controls()

    def _refresh_current_focus(self) -> None:
        active = self.app.service.get_active_session()
        if active:
            text = active["subject"]
        elif self.break_timer.state in {"running", "paused"}:
            text = "Break"
        elif self.selected_task_id:
            task = self.app.service.get_task(self.selected_task_id)
            text = task["title"] if task else "Select a task or describe an activity"
        elif self.activity_var.get().strip():
            text = self.activity_var.get().strip()
        else:
            text = "Select a task or describe an activity"
        self.current_focus_var.set(text)

    def _refresh_timer_controls(self) -> None:
        active = self.app.service.get_active_session()
        focus_minutes, break_minutes = self.app.service.get_durations()
        break_active = self.break_timer.state in {"running", "paused"}
        locked = active is not None or break_active
        self.activity_entry.configure(state="disabled" if locked else "normal")
        self.start_button.configure(state="disabled" if locked else "normal")
        self.pause_button.configure(state="normal" if locked else "disabled")
        self.stop_button.configure(state="normal" if locked else "disabled")
        pause_text = "Resume" if (
            active and active["status"] == "paused"
        ) or self.break_timer.state == "paused" else "Pause"
        self.pause_button.configure(text=pause_text)
        self.break_button.configure(
            text=f"Start Break ({break_minutes} min)",
            state="normal" if self.break_allowed and not locked else "disabled",
        )
        if active:
            remaining = active["planned_seconds"] - active["focused_seconds"]
            self.timer_var.set(format_duration(remaining))
            self.status_var.set(
                "●  Focus paused" if active["status"] == "paused" else "●  Focusing"
            )
        elif break_active:
            remaining = self.break_timer.remaining()
            self.timer_var.set(format_duration(remaining))
            self.status_var.set(
                "●  Break paused" if self.break_timer.state == "paused" else "●  On break"
            )
        else:
            self.timer_var.set(format_duration(focus_minutes * 60))
            if self.break_timer.state == "completed":
                self.status_var.set("●  Break complete")
            elif not self.status_var.get().startswith("●  Focus complete"):
                self.status_var.set("●  Ready to focus")
        self._refresh_current_focus()

    def start_focus(self) -> None:
        try:
            self.app.service.start_focus(
                task_id=self.selected_task_id,
                activity_description=None if self.selected_task_id else self.activity_var.get(),
            )
        except (ValidationError, SessionStateError) as error:
            messagebox.showerror("Cannot start focus", str(error), parent=self)
            return
        self.break_allowed = False
        self.status_var.set("●  Focusing")
        self.app.refresh_all()

    def pause_resume(self) -> None:
        try:
            active = self.app.service.get_active_session()
            if active:
                if active["status"] == "running":
                    result = self.app.service.pause_focus()
                    if result["status"] == "completed":
                        self._focus_completed()
                        self.app.refresh_all()
                        return
                else:
                    self.app.service.resume_focus()
            elif self.break_timer.state == "running":
                self.break_timer.pause()
            elif self.break_timer.state == "paused":
                self.break_timer.resume()
        except (SessionStateError, TimerStateError) as error:
            messagebox.showerror("Timer unavailable", str(error), parent=self)
        self._refresh_timer_controls()

    def stop_timer(self) -> None:
        try:
            if self.app.service.get_active_session():
                result = self.app.service.stop_focus()
                if result["status"] == "completed":
                    self._focus_completed()
                else:
                    self.status_var.set("●  Focus cancelled")
            elif self.break_timer.state in {"running", "paused"}:
                self.break_timer.stop()
                self.status_var.set("●  Break stopped")
        except SessionStateError as error:
            messagebox.showerror("Timer unavailable", str(error), parent=self)
        self.app.refresh_all()

    def start_break(self) -> None:
        _, break_minutes = self.app.service.get_durations()
        try:
            self.break_timer.start(break_minutes * 60)
        except TimerStateError as error:
            messagebox.showerror("Cannot start break", str(error), parent=self)
            return
        self.break_allowed = False
        self._refresh_timer_controls()

    def _focus_completed(self) -> None:
        self.break_allowed = True
        self.status_var.set("●  Focus complete — break available")
        self.app.play_completion_sound()

    def tick(self) -> None:
        active_before = self.app.service.get_active_session()
        if active_before:
            result = self.app.service.update_focus()
            if result and result["status"] == "completed":
                self._focus_completed()
                self.app.refresh_all()
                return
            now = time.monotonic()
            if now - self._last_checkpoint >= 5:
                self.app.service.checkpoint_active()
                self._last_checkpoint = now
        if self.break_timer.state in {"running", "paused"}:
            self.break_timer.remaining()
        self._refresh_timer_controls()
