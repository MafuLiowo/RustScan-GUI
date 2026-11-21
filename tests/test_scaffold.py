"""骨架自检：不依赖 PySide6，可在安装 GUI 依赖前运行。"""

from config import settings
from utils.paths import ensure_runtime_dirs, resolve_rustscan


def test_project_directories_exist() -> None:
    directories = (
        settings.ASSETS_DIR,
        settings.STYLES_DIR,
        settings.ICONS_DIR,
        settings.IMAGES_DIR,
        settings.LANGUAGE_DIR,
        settings.BIN_DIR,
        settings.LOGS_DIR,
        settings.PROJECT_ROOT / "core",
        settings.PROJECT_ROOT / "models",
        settings.PROJECT_ROOT / "services",
        settings.PROJECT_ROOT / "ui",
        settings.PROJECT_ROOT / "utils",
        settings.PROJECT_ROOT / "tests",
        settings.PROJECT_ROOT / "docs",
        settings.PROJECT_ROOT / "scripts",
    )
    for directory in directories:
        assert directory.is_dir(), f"缺少目录: {directory}"


def test_rustscan_executable_available() -> None:
    executable = resolve_rustscan()
    assert executable is not None, "未找到 rustscan 可执行文件"
    assert executable.is_file()


def test_style_file_exists() -> None:
    assert settings.DEFAULT_STYLE.is_file()


def test_runtime_dirs_created() -> None:
    ensure_runtime_dirs()
    assert settings.LOGS_DIR.is_dir()
