from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication

from src.ui.main_window import MainWindow
from src.ui.styles import APP_QSS


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("SPAudioTruth")
    app.setStyleSheet(APP_QSS)

    initial_file = sys.argv[1] if len(sys.argv) > 1 else None
    window = MainWindow(initial_file=initial_file)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
