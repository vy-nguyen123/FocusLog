"""Read-only focus history screen."""

from datetime import datetime
import tkinter as tk
from tkinter import ttk

from focuslog.timer import format_duration


class HistoryScreen(ttk.Frame):
    def __init__(self, parent: tk.Misc, app) -> None:
        super().__init__(parent, style="Page.TFrame", padding=(24, 22))
        self.app = app
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        card = ttk.Frame(self, style="Card.TFrame", padding=24)
        card.grid(row=0, column=0, sticky="nsew")
        card.columnconfigure(0, weight=1)
        card.rowconfigure(2, weight=1)
        ttk.Label(card, text="Focus History", style="Heading.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            card,
            text="A read-only log of your completed and cancelled focus blocks",
            style="Muted.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(4, 20))

        columns = ("description", "date", "planned", "actual", "status")
        self.history = ttk.Treeview(card, columns=columns, show="headings", height=12)
        headings = {
            "description": "TASK / ACTIVITY DESCRIPTION",
            "date": "DATE & TIME",
            "planned": "PLANNED",
            "actual": "ACTUAL",
            "status": "STATUS",
        }
        widths = {
            "description": 480,
            "date": 180,
            "planned": 100,
            "actual": 100,
            "status": 120,
        }
        for column in columns:
            self.history.heading(column, text=headings[column])
            self.history.column(column, width=widths[column], anchor="w")
        self.history.grid(row=2, column=0, sticky="nsew")
        self.refresh()

    def refresh(self) -> None:
        for item in self.history.get_children():
            self.history.delete(item)
        for session in self.app.service.list_history():
            ended_at = datetime.fromisoformat(session["ended_at"])
            self.history.insert(
                "",
                "end",
                values=(
                    session["subject"],
                    ended_at.strftime("%Y-%m-%d %H:%M"),
                    format_duration(session["planned_seconds"]),
                    format_duration(session["focused_seconds"]),
                    session["status"].title(),
                ),
            )
