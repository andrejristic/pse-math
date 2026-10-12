"""Packaged entry point: launch the GUI with a research.db in a writable place."""
import os
import sys
from pathlib import Path


def _db_path() -> str:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    d = base / "pse-math"
    d.mkdir(parents=True, exist_ok=True)
    return str(d / "research.db")


def main() -> int:
    from PySide6 import QtWidgets
    from pse_research.gui import MainWindow
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("PSE Math")
    win = MainWindow(_db_path())
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
