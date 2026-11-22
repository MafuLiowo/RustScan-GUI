"""script/ 目录中脚本文件的读取与创建。"""

from __future__ import annotations

import re
from pathlib import Path

from config.settings import SCRIPTS_DIR

_INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


class ScriptStoreError(Exception):
    """脚本文件操作失败的基类。"""


class InvalidScriptNameError(ScriptStoreError):
    """脚本名称不合法。"""


class ScriptExistsError(ScriptStoreError):
    """同名脚本已经存在。"""


class ScriptStore:
    """负责 script/ 目录下脚本文件的列表、读取和添加。"""

    def __init__(self, root: Path | str = SCRIPTS_DIR) -> None:
        self.root = Path(root)

    def ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def list_scripts(self) -> list[str]:
        self.ensure()
        try:
            entries = list(self.root.iterdir())
        except OSError:
            return []
        return sorted(
            (
                entry.name
                for entry in entries
                if entry.is_file() and not entry.name.startswith(".")
            ),
            key=str.casefold,
        )

    def read_script(self, name: str) -> str:
        path = self.root / self.validate_name(name)
        return path.read_text(encoding="utf-8", errors="replace")

    def write_script(self, name: str, content: str) -> str:
        cleaned = self.validate_name(name)
        self.ensure()
        path = self.root / cleaned
        if path.exists():
            raise ScriptExistsError(f"“{cleaned}”已存在。")
        path.write_text(content, encoding="utf-8")
        return cleaned

    def delete_script(self, name: str) -> None:
        path = self.root / self.validate_name(name)
        path.unlink()

    def validate_name(self, name: str) -> str:
        cleaned = name.strip()
        if not cleaned:
            raise InvalidScriptNameError("脚本名称不能为空。")
        if cleaned in {".", ".."}:
            raise InvalidScriptNameError("脚本名称不能是 . 或 ..。")
        if _INVALID_CHARS.search(cleaned):
            raise InvalidScriptNameError('脚本名称不能包含 \\ / : * ? " < > | 等字符。')
        if cleaned.endswith((" ", ".")):
            raise InvalidScriptNameError("脚本名称不能以空格或句点结尾。")
        if cleaned.split(".")[0].upper() in _RESERVED_NAMES:
            raise InvalidScriptNameError("该名称是 Windows 保留名称。")
        if len(cleaned) > 100:
            raise InvalidScriptNameError("脚本名称过长（最多 100 个字符）。")
        return cleaned
