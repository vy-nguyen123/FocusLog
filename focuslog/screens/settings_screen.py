"""Persistent duration and Obsidian settings screen."""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from focuslog.service import ValidationError


class SettingsScreen(ttk.Frame):
    def __init__(self, parent: tk.Misc, app) -> None:
        super().__init__(parent, style="Page.TFrame", padding=(24, 22))
        self.app = app
        self.columnconfigure(0, weight=2)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        self._build_settings_card()
        self._build_troubleshooting_card()
        self.refresh()

    def _build_settings_card(self) -> None:
        card = ttk.Frame(self, style="Card.TFrame", padding=24)
        card.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        card.columnconfigure((0, 1), weight=1)
        ttk.Label(card, text="Interval Configurations", style="Heading.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 18)
        )
        ttk.Label(card, text="Focus Duration (minutes)", style="FieldLabel.TLabel").grid(
            row=1, column=0, sticky="w", padx=(0, 8), pady=(0, 7)
        )
        ttk.Label(card, text="Break Duration (minutes)", style="FieldLabel.TLabel").grid(
            row=1, column=1, sticky="w", padx=(8, 0), pady=(0, 7)
        )
        self.focus_var = tk.StringVar()
        self.break_var = tk.StringVar()
        ttk.Entry(card, textvariable=self.focus_var).grid(
            row=2, column=0, sticky="ew", padx=(0, 8), ipady=6
        )
        ttk.Entry(card, textvariable=self.break_var).grid(
            row=2, column=1, sticky="ew", padx=(8, 0), ipady=6
        )
        self.save_button = ttk.Button(
            card,
            text="Save Durations",
            style="Primary.TButton",
            command=self.save_durations,
        )
        self.save_button.grid(
            row=3, column=0, columnspan=2, sticky="ew", pady=(12, 0), ipady=5
        )

        ttk.Separator(card).grid(
            row=4, column=0, columnspan=2, sticky="ew", pady=24
        )
        ttk.Label(card, text="Obsidian Logging Sync", style="Heading.TLabel").grid(
            row=5, column=0, columnspan=2, sticky="w"
        )
        ttk.Label(
            card,
            text="Focus events will be appended to your Productivity Logs folder.",
            style="Muted.TLabel",
        ).grid(row=6, column=0, columnspan=2, sticky="w", pady=(8, 18))
        ttk.Label(card, text="Obsidian Vault Path", style="FieldLabel.TLabel").grid(
            row=7, column=0, columnspan=2, sticky="w", pady=(0, 7)
        )
        self.vault_var = tk.StringVar()
        vault_entry = ttk.Entry(card, textvariable=self.vault_var, state="readonly")
        vault_entry.grid(row=8, column=0, sticky="ew", padx=(0, 12), ipady=6)
        ttk.Button(card, text="Select Vault", command=self.select_vault).grid(
            row=8, column=1, sticky="e", ipady=5
        )

        status = ttk.Frame(card, style="Timer.TFrame", padding=16)
        status.grid(row=9, column=0, columnspan=2, sticky="ew", pady=(18, 0))
        status.columnconfigure(1, weight=1)
        ttk.Label(status, text="Vault Connection Status", style="Subheading.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        self.vault_status_var = tk.StringVar()
        ttk.Label(status, textvariable=self.vault_status_var, style="Muted.TLabel").grid(
            row=0, column=1, sticky="e"
        )
        ttk.Separator(status).grid(
            row=1, column=0, columnspan=2, sticky="ew", pady=12
        )
        ttk.Label(status, text="Pending Backlog Events", style="Subheading.TLabel").grid(
            row=2, column=0, sticky="w"
        )
        self.pending_var = tk.StringVar()
        ttk.Label(status, textvariable=self.pending_var, style="Body.TLabel").grid(
            row=2, column=1, sticky="e"
        )

    def _build_troubleshooting_card(self) -> None:
        card = ttk.Frame(self, style="Card.TFrame", padding=24)
        card.grid(row=0, column=1, sticky="new", padx=(12, 0))
        card.columnconfigure(0, weight=1)
        ttk.Label(card, text="System Troubleshooting", style="Heading.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 20)
        )
        ttk.Label(card, text="Latest Logging Error", style="FieldLabel.TLabel").grid(
            row=1, column=0, sticky="w", pady=(0, 7)
        )
        self.error_var = tk.StringVar()
        ttk.Entry(card, textvariable=self.error_var, state="readonly").grid(
            row=2, column=0, sticky="ew", ipady=7, pady=(0, 16)
        )
        self.retry_button = ttk.Button(
            card,
            text="Retry Pending Logs",
            style="Primary.TButton",
            command=self.retry_pending,
        )
        self.retry_button.grid(row=3, column=0, sticky="ew", ipady=6)

    def save_durations(self) -> None:
        try:
            focus = int(self.focus_var.get())
            rest = int(self.break_var.get())
            self.app.service.set_durations(focus, rest)
        except (ValueError, ValidationError) as error:
            messagebox.showerror(
                "Invalid durations",
                str(error) if isinstance(error, ValidationError) else "Use positive whole minutes.",
                parent=self,
            )
            return
        self.app.refresh_all()

    def select_vault(self) -> None:
        selected = filedialog.askdirectory(title="Select Obsidian Vault", parent=self)
        if not selected:
            return
        try:
            self.app.service.select_vault(selected)
        except ValidationError as error:
            messagebox.showerror("Invalid Obsidian vault", str(error), parent=self)
            return
        self.app.refresh_all()

    def retry_pending(self) -> None:
        self.app.service.retry_pending_events()
        self.app.refresh_all()

    def refresh(self) -> None:
        focus, rest = self.app.service.get_durations()
        self.focus_var.set(str(focus))
        self.break_var.set(str(rest))
        status = self.app.service.get_logging_status()
        self.vault_var.set(str(status["vault_path"] or "No vault selected"))
        self.vault_status_var.set("Connected" if status["vault_valid"] else "Not configured")
        self.pending_var.set(str(status["pending_count"]))
        self.error_var.set(status["latest_error"] or "None (No errors encountered)")
