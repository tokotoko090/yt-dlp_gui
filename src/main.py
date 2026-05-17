from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from src.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("yt-dlp GUI")
    window = MainWindow()
    window.resize(1120, 760)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
