"""应用入口。"""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication

from config.settings import (
    APP_NAME,
    APP_ICON_FILE,
    APP_WINDOW_TITLE,
    APP_VERSION,
    ORGANIZATION,
)
from ui.main_window import MainWindow
from utils.logger import setup_logging
from utils.paths import ensure_runtime_dirs


def main() -> int:
    ensure_runtime_dirs()
    setup_logging()

    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_WINDOW_TITLE)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(ORGANIZATION)
    app.setWindowIcon(QIcon(str(APP_ICON_FILE)))

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
