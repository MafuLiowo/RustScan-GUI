"""浅色/深色主题与系统配色跟随。

QSS 负责主要外观，调色板则让原生控件、树形展开箭头、
输入对话框等非样式表元素也保持同步。
"""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication

from config.settings import (
    ASSETS_DIR,
    DEFAULT_DISPLAY_MODE,
    DISPLAY_MODE_DARK,
    DISPLAY_MODE_LIGHT,
    DISPLAY_MODE_SYSTEM,
    DARK_STYLE,
    LIGHT_STYLE,
)

_APPLIED_THEME_PROPERTY = "_rustscanAppliedTheme"


def build_dark_palette() -> QPalette:
    palette = QPalette()
    colors = {
        QPalette.ColorRole.Window: "#1d1f23",
        QPalette.ColorRole.WindowText: "#e8eaed",
        QPalette.ColorRole.Base: "#24262b",
        QPalette.ColorRole.AlternateBase: "#2a2d33",
        QPalette.ColorRole.ToolTipBase: "#24262b",
        QPalette.ColorRole.ToolTipText: "#e8eaed",
        QPalette.ColorRole.Text: "#e8eaed",
        QPalette.ColorRole.Button: "#2a2d33",
        QPalette.ColorRole.ButtonText: "#e8eaed",
        QPalette.ColorRole.BrightText: "#ffffff",
        QPalette.ColorRole.Link: "#6fa8dc",
        QPalette.ColorRole.Highlight: "#3d6fa5",
        QPalette.ColorRole.HighlightedText: "#ffffff",
        QPalette.ColorRole.PlaceholderText: "#6f747b",
        QPalette.ColorRole.Light: "#3a3f47",
        QPalette.ColorRole.Midlight: "#33363d",
        QPalette.ColorRole.Dark: "#16181b",
        QPalette.ColorRole.Mid: "#2a2d33",
        QPalette.ColorRole.Shadow: "#101214",
    }
    for role, value in colors.items():
        palette.setColor(role, QColor(value))

    disabled = QColor("#6f747b")
    for role in (
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
        QPalette.ColorRole.WindowText,
    ):
        palette.setColor(QPalette.ColorGroup.Disabled, role, disabled)
    return palette


def build_light_palette() -> QPalette:
    palette = QPalette()
    colors = {
        QPalette.ColorRole.Window: "#f3f5f7",
        QPalette.ColorRole.WindowText: "#20242a",
        QPalette.ColorRole.Base: "#ffffff",
        QPalette.ColorRole.AlternateBase: "#f7f8fa",
        QPalette.ColorRole.ToolTipBase: "#ffffff",
        QPalette.ColorRole.ToolTipText: "#20242a",
        QPalette.ColorRole.Text: "#20242a",
        QPalette.ColorRole.Button: "#eef1f4",
        QPalette.ColorRole.ButtonText: "#20242a",
        QPalette.ColorRole.BrightText: "#000000",
        QPalette.ColorRole.Link: "#1f6fb2",
        QPalette.ColorRole.Highlight: "#2f6faf",
        QPalette.ColorRole.HighlightedText: "#ffffff",
        QPalette.ColorRole.PlaceholderText: "#8a9199",
        QPalette.ColorRole.Light: "#ffffff",
        QPalette.ColorRole.Midlight: "#e7eaee",
        QPalette.ColorRole.Dark: "#c6ccd4",
        QPalette.ColorRole.Mid: "#d6dae0",
        QPalette.ColorRole.Shadow: "#b9c0c8",
    }
    for role, value in colors.items():
        palette.setColor(role, QColor(value))

    disabled = QColor("#9aa0a6")
    for role in (
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
        QPalette.ColorRole.WindowText,
    ):
        palette.setColor(QPalette.ColorGroup.Disabled, role, disabled)
    return palette


def _windows_prefers_dark() -> bool | None:
    """Windows 上作为 Qt 配色未知时的回退检测。"""
    if sys.platform != "win32":
        return None
    try:
        import winreg

        key_path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            light_enabled, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
    except (OSError, ValueError):
        return None
    return not bool(light_enabled)


def system_prefers_dark() -> bool:
    """返回当前系统是否处于深色外观。"""
    hints = QGuiApplication.styleHints()
    scheme = hints.colorScheme()
    if scheme == Qt.ColorScheme.Dark:
        return True
    if scheme == Qt.ColorScheme.Light:
        return False

    registry_value = _windows_prefers_dark()
    if registry_value is not None:
        return registry_value
    return True


def effective_display_mode(mode: str) -> str:
    """把显示模式解析为实际生效的 light/dark。"""
    if mode == DISPLAY_MODE_SYSTEM:
        return DISPLAY_MODE_DARK if system_prefers_dark() else DISPLAY_MODE_LIGHT
    if mode == DISPLAY_MODE_LIGHT:
        return DISPLAY_MODE_LIGHT
    if mode == DISPLAY_MODE_DARK:
        return DISPLAY_MODE_DARK
    return (
        DISPLAY_MODE_DARK
        if DEFAULT_DISPLAY_MODE == DISPLAY_MODE_DARK
        else DISPLAY_MODE_LIGHT
    )


@lru_cache(maxsize=2)
def _load_stylesheet(path: str) -> str:
    return Path(path).read_text(encoding="utf-8").replace(
        "{ASSETS_DIR}",
        ASSETS_DIR.as_posix(),
    )


def apply_app_theme(app: QApplication, mode: str) -> str:
    """应用指定显示模式，返回实际生效的 light/dark。"""
    effective = effective_display_mode(mode)
    if app.property(_APPLIED_THEME_PROPERTY) == effective and app.styleSheet():
        return effective

    style_path = LIGHT_STYLE if effective == DISPLAY_MODE_LIGHT else DARK_STYLE
    palette = build_light_palette() if effective == DISPLAY_MODE_LIGHT else build_dark_palette()

    app.setPalette(palette)
    if style_path.is_file():
        app.setStyleSheet(_load_stylesheet(str(style_path)))
    else:
        app.setStyleSheet("")
    app.setProperty(_APPLIED_THEME_PROPERTY, effective)
    return effective
