"""程序级配置文件 config.ini 的读写。"""

from __future__ import annotations

import re
from pathlib import Path

from config.settings import (
    APP_CONFIG_FILE,
    DEFAULT_DISPLAY_MODE,
    DEFAULT_LANGUAGE,
    DEFAULT_NMAP_PATH,
    DISPLAY_MODES,
)


def _value_pattern(key: str) -> re.Pattern[str]:
    return re.compile(
        rf'^\s*{re.escape(key)}\s*=\s*"?(?P<value>[^"\r\n]*)"?\s*$',
        re.MULTILINE,
    )


def _read_value(path: Path | str, key: str, default: str) -> str:
    try:
        content = Path(path).read_text(encoding="utf-8")
    except OSError:
        return default
    match = _value_pattern(key).search(content)
    if match is None:
        return default
    value = match.group("value").strip()
    return value or default


def _write_value(path: Path | str, key: str, value: str) -> Path:
    config_path = Path(path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        lines = config_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []

    line_pattern = re.compile(rf"^\s*{re.escape(key)}\s*=")
    for index, line in enumerate(lines):
        if line_pattern.match(line):
            lines[index] = f'{key} = "{value}"'
            break
    else:
        lines.append(f'{key} = "{value}"')

    config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return config_path


def read_language(path: Path | str = APP_CONFIG_FILE) -> str:
    """读取 language 配置；文件缺失或格式无效时返回默认语言。"""
    return _read_value(path, "language", DEFAULT_LANGUAGE)


def write_language(path: Path | str, language: str) -> Path:
    """以 language = "code" 的格式写入语言配置。"""
    return _write_value(path, "language", language)


def read_display_mode(path: Path | str = APP_CONFIG_FILE) -> str:
    """读取 display_mode 配置；缺失或无效时返回默认显示模式。"""
    mode = _read_value(path, "display_mode", DEFAULT_DISPLAY_MODE)
    return mode if mode in DISPLAY_MODES else DEFAULT_DISPLAY_MODE


def write_display_mode(path: Path | str, mode: str) -> Path:
    """以 display_mode = "mode" 的格式写入显示模式。"""
    return _write_value(path, "display_mode", mode)


def read_nmap_path(path: Path | str = APP_CONFIG_FILE) -> str:
    """读取 Nmap 可执行文件路径；缺失时返回 Windows 常见安装路径。"""
    return _read_value(path, "nmap_path", DEFAULT_NMAP_PATH)


def write_nmap_path(path: Path | str, nmap_path: str) -> Path:
    """以 nmap_path = "path" 的格式写入 Nmap 路径。"""
    return _write_value(path, "nmap_path", nmap_path)
