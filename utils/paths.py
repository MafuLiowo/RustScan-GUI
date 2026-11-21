"""路径解析：内置可执行文件、日志目录等。"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from config.settings import (
    BIN_DIR,
    BUNDLED_LANGUAGE_DIR,
    BUNDLED_RUSTSCAN_EXECUTABLE,
    LANGUAGE_DIR,
    LOGS_DIR,
    PROJECTS_DIR,
    RUSTSCAN_EXECUTABLE,
    SCRIPTS_DIR,
)


def ensure_runtime_dirs() -> None:
    """创建运行目录，并把单文件 EXE 内置资源释放到程序目录。"""
    for directory in (
        BIN_DIR,
        LANGUAGE_DIR,
        LOGS_DIR,
        PROJECTS_DIR,
        SCRIPTS_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    _copy_if_changed(BUNDLED_RUSTSCAN_EXECUTABLE, RUSTSCAN_EXECUTABLE)
    if BUNDLED_LANGUAGE_DIR.is_dir():
        for source in BUNDLED_LANGUAGE_DIR.glob("*.xml"):
            _copy_if_changed(source, LANGUAGE_DIR / source.name)


def _copy_if_changed(source: Path, target: Path) -> None:
    if not source.is_file():
        return
    if source.resolve() == target.resolve():
        return
    try:
        if target.is_file() and source.read_bytes() == target.read_bytes():
            return
    except OSError:
        pass
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def resolve_rustscan() -> Path | None:
    """优先使用 bin/ 内置的 rustscan，其次回退到系统 PATH。"""
    if RUSTSCAN_EXECUTABLE.is_file():
        return RUSTSCAN_EXECUTABLE
    found = shutil.which("rustscan")
    return Path(found) if found else None


def resolve_nmap(configured_path: str | Path | None = None) -> Path | None:
    """优先使用配置路径，其次查找 PATH 与 Windows 常见安装目录。"""
    if configured_path:
        candidate = Path(str(configured_path).strip().strip('"')).expanduser()
        if candidate.is_dir():
            candidate = candidate / ("nmap.exe" if sys.platform == "win32" else "nmap")
        if candidate.is_file():
            return candidate

    found = shutil.which("nmap")
    if found:
        return Path(found)
    if sys.platform != "win32":
        return None
    for env_name in ("ProgramFiles(x86)", "ProgramFiles"):
        base = os.environ.get(env_name)
        if not base:
            continue
        candidate = Path(base) / "Nmap" / "nmap.exe"
        if candidate.is_file():
            return candidate
    return None
