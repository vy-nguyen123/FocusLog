"""Main FocusLog Tkinter window and screen navigation."""

import tkinter as tk
from pathlib import Path
from tkinter import ttk

from focuslog.screens.history_screen import HistoryScreen
from focuslog.screens.settings_screen import SettingsScreen
from focuslog.screens.tasks_screen import TasksScreen
from focuslog.service import FocusLogService


class FocusLogApp:
    SCREEN_TYPES = {
        "Tasks": TasksScreen,
        "History": HistoryScreen,
        "Settings": SettingsScreen,
    }

    def __init__(
        self, root: tk.Tk, database_path: Path | None = None
    ) -> None:
        self.root = root
        self.root.title("FocusLog")
        self.root.geometry("1200x760")
        self.root.minsize(900, 600)
        self.service = FocusLogService(database_path)
        self.database_path = self.service.database_path
        self.service.recover_interrupted_session()
        self.current_screen = ""
        self._closing = False

        self._configure_styles()
        self._build_layout()
        self.show_screen("Tasks")
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self._after_id = self.root.after(250, self._tick)

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        background = "#f5f5f7"
        card = "#ffffff"
        border = "#d5d5da"
        foreground = "#202024"
        muted = "#62626b"

        self.root.configure(background=background)
        style.configure("Page.TFrame", background=background)
        style.configure("Nav.TFrame", background=background)
        style.configure("Card.TFrame", background=card, relief="solid", borderwidth=1)
        style.configure("ListItem.TFrame", background=card, relief="solid", borderwidth=1)
        style.configure("Timer.TFrame", background="#f4f4f6", relief="solid", borderwidth=1)

        for name, size, weight, color in (
            ("Heading.TLabel", 14, "bold", foreground),
            ("Subheading.TLabel", 10, "bold", muted),
            ("FieldLabel.TLabel", 9, "normal", muted),
            ("Body.TLabel", 10, "normal", foreground),
            ("Muted.TLabel", 9, "normal", muted),
            ("Centered.TLabel", 11, "normal", foreground),
            ("Eyebrow.TLabel", 9, "bold", muted),
        ):
            style.configure(
                name,
                background=card,
                foreground=color,
                font=("Segoe UI", size, weight),
            )
        style.configure(
            "Timer.TLabel",
            background="#f4f4f6",
            foreground=foreground,
            font=("Consolas", 42, "bold"),
        )
        style.configure(
            "Primary.TButton",
            background="#1f1f23",
            foreground="#ffffff",
            font=("Segoe UI", 10, "bold"),
            borderwidth=0,
        )
        style.map("Primary.TButton", background=[("active", "#34343a")])
        style.configure("Nav.TButton", font=("Segoe UI", 10), padding=(16, 10))
        style.configure(
            "ActiveNav.TButton", font=("Segoe UI", 10, "bold"), padding=(16, 10)
        )
        style.configure("Treeview", rowheight=38, font=("Segoe UI", 10))
        style.configure(
            "Treeview.Heading",
            font=("Segoe UI", 9, "bold"),
            foreground=muted,
        )
        style.configure("TEntry", fieldbackground=card, bordercolor=border, padding=5)

    def _build_layout(self) -> None:
        shell = ttk.Frame(self.root, style="Page.TFrame")
        shell.pack(fill="both", expand=True)
        shell.columnconfigure(0, weight=1)
        shell.rowconfigure(1, weight=1)

        navigation = ttk.Frame(shell, style="Nav.TFrame", padding=(24, 18, 24, 0))
        navigation.grid(row=0, column=0, sticky="ew")
        self.navigation_buttons: dict[str, ttk.Button] = {}
        for column, screen_name in enumerate(self.SCREEN_TYPES):
            button = ttk.Button(
                navigation,
                text=screen_name,
                style="Nav.TButton",
                command=lambda name=screen_name: self.show_screen(name),
            )
            button.grid(row=0, column=column, sticky="w", padx=(0, 4))
            self.navigation_buttons[screen_name] = button

        self.screen_container = ttk.Frame(shell, style="Page.TFrame")
        self.screen_container.grid(row=1, column=0, sticky="nsew")
        self.screen_container.columnconfigure(0, weight=1)
        self.screen_container.rowconfigure(0, weight=1)

        self.screens: dict[str, ttk.Frame] = {}
        for screen_name, screen_type in self.SCREEN_TYPES.items():
            screen = screen_type(self.screen_container, self)
            screen.grid(row=0, column=0, sticky="nsew")
            self.screens[screen_name] = screen

    def show_screen(self, screen_name: str) -> None:
        """Bring one application screen to the front and refresh its data."""
        screen = self.screens[screen_name]
        if hasattr(screen, "refresh"):
            screen.refresh()
        screen.tkraise()
        self.current_screen = screen_name
        for name, button in self.navigation_buttons.items():
            button.configure(
                style="ActiveNav.TButton" if name == screen_name else "Nav.TButton"
            )

    def refresh_all(self) -> None:
        for screen in self.screens.values():
            if hasattr(screen, "refresh"):
                screen.refresh()

    def play_completion_sound(self) -> None:
        """Play the Windows completion sound without an added dependency."""
        try:
            import winsound

            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except (ImportError, RuntimeError):
            self.root.bell()

    def _tick(self) -> None:
        if self._closing:
            return
        self.screens["Tasks"].tick()
        self._after_id = self.root.after(250, self._tick)

    def close(self) -> None:
        """Turn an unfinished focus into a cancelled history entry before exit."""
        if self._closing:
            return
        self._closing = True
        if self._after_id:
            self.root.after_cancel(self._after_id)
            self._after_id = None
        self.service.cancel_active_on_close()
        self.root.destroy()
