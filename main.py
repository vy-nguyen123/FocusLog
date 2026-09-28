"""FocusLog application entry point."""

import tkinter as tk

from focuslog.app import FocusLogApp


def main() -> None:
    root = tk.Tk()
    FocusLogApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
