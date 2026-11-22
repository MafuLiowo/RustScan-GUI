"""应用级常量、路径与默认配置。

所有路径都基于项目根目录解析，避免从不同工作目录启动时失效。
"""

from __future__ import annotations

import sys
from pathlib import Path

APP_NAME = "RustScan GUI"
APP_WINDOW_TITLE = "RustScan-GUI by MafuLiowo"
APP_VERSION = "1.0.0"
ORGANIZATION = "RustScan GUI"

def _application_root() -> Path:
    """单文件 EXE 使用其所在目录，源码运行使用项目目录。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def _bundle_root() -> Path:
    """PyInstaller 解压资源所在目录；源码运行时与项目目录相同。"""
    bundle = getattr(sys, "_MEIPASS", None)
    return Path(bundle).resolve() if bundle else PROJECT_ROOT


PROJECT_ROOT = _application_root()
BUNDLE_ROOT = _bundle_root()

ASSETS_DIR = BUNDLE_ROOT / "assets"
STYLES_DIR = ASSETS_DIR / "styles"
ICONS_DIR = ASSETS_DIR / "icons"
IMAGES_DIR = ASSETS_DIR / "images"
LOGO_FILE = IMAGES_DIR / "rsg-logo.png"
APP_ICON_FILE = ICONS_DIR / "rsg-app.png"
GITHUB_ICON_FILE = ICONS_DIR / "github.svg"

BIN_DIR = PROJECT_ROOT / "bin"
RUSTSCAN_EXECUTABLE = BIN_DIR / "rustscan.exe"
BUNDLED_RUSTSCAN_EXECUTABLE = BUNDLE_ROOT / "bin" / "rustscan.exe"

CONFIG_DIR = PROJECT_ROOT / "config"
APP_CONFIG_FILE = PROJECT_ROOT / "config.ini"
LANGUAGE_DIR = PROJECT_ROOT / "language"
BUNDLED_LANGUAGE_DIR = BUNDLE_ROOT / "language"
LOGS_DIR = PROJECT_ROOT / "logs"
PROJECTS_DIR = PROJECT_ROOT / "project"
SCRIPTS_DIR = PROJECT_ROOT / "script"

DARK_STYLE = STYLES_DIR / "dark.qss"
LIGHT_STYLE = STYLES_DIR / "light.qss"
DEFAULT_STYLE = DARK_STYLE

DISPLAY_MODE_LIGHT = "light"
DISPLAY_MODE_DARK = "dark"
DISPLAY_MODE_SYSTEM = "system"
DISPLAY_MODES = (DISPLAY_MODE_LIGHT, DISPLAY_MODE_DARK, DISPLAY_MODE_SYSTEM)
DEFAULT_DISPLAY_MODE = DISPLAY_MODE_DARK

DEFAULT_LANGUAGE = "en"
DEFAULT_NMAP_PATH = r"C:\Program Files (x86)\Nmap\nmap.exe"
DEFAULT_WINDOW_SIZE = (1120, 720)
DEFAULT_WINDOW_MIN_SIZE = (900, 600)

LOG_FILE = LOGS_DIR / "app.log"
LOG_MAX_BYTES = 2 * 1024 * 1024
LOG_BACKUP_COUNT = 3

SCAN_INFO_FILENAME = "scan_info.xml"
