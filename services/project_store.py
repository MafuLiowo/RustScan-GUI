"""项目目录的创建、加载与重命名。

磁盘布局：

project/
├── 新建项目/
│   ├── 新扫描/
│   └── 新扫描2/
└── 新建项目2/
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from config.settings import PROJECTS_DIR
from models.project import ProjectNode, ScanNode

DEFAULT_PROJECT_NAME = "新建项目"
DEFAULT_SCAN_NAME = "新扫描"
HIDDEN_MANIFEST_FILENAME = ".rustscan-gui-hidden.json"

_INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


class ProjectStoreError(Exception):
    """项目目录操作失败的基类。"""


class InvalidNameError(ProjectStoreError):
    """名称不合法。"""


class NameConflictError(ProjectStoreError):
    """目标名称已被占用。"""


class ProjectStore:
    """负责 project/ 目录下项目与扫描文件夹的增删改查。"""

    def __init__(self, root: Path | str | None = None) -> None:
        self.root = Path(root) if root is not None else PROJECTS_DIR
        self.root.mkdir(parents=True, exist_ok=True)

    def load(self) -> list[ProjectNode]:
        self.root.mkdir(parents=True, exist_ok=True)
        hidden = self._load_hidden_paths()
        projects: list[ProjectNode] = []
        for entry in self._sorted_dirs(self.root):
            if self._relative_key(entry) in hidden:
                continue
            scans = [
                ScanNode(name=child.name, path=child)
                for child in self._sorted_dirs(entry)
                if self._relative_key(child) not in hidden
            ]
            projects.append(ProjectNode(name=entry.name, path=entry, scans=scans))
        return projects

    def create_project(self, base_name: str = DEFAULT_PROJECT_NAME) -> ProjectNode:
        name = self._unique_name(self.root, base_name)
        path = self._ensure_dir(self.root, name)
        return ProjectNode(name=name, path=path)

    def create_scan(
        self,
        project: ProjectNode | Path,
        base_name: str = DEFAULT_SCAN_NAME,
    ) -> ScanNode:
        project_path = project.path if isinstance(project, ProjectNode) else Path(project)
        project_path.mkdir(parents=True, exist_ok=True)
        name = self._unique_name(project_path, base_name)
        path = self._ensure_dir(project_path, name)
        return ScanNode(name=name, path=path)

    def rename_project(self, project: ProjectNode, new_name: str) -> ProjectNode:
        name = self.validate_name(new_name)
        path = self._rename_dir(project.path, name)
        return ProjectNode(name=path.name, path=path)

    def rename_scan(self, scan: ScanNode, new_name: str) -> ScanNode:
        name = self.validate_name(new_name)
        path = self._rename_dir(scan.path, name)
        return ScanNode(name=path.name, path=path)

    def delete_project(
        self,
        project: ProjectNode | Path,
        *,
        delete_files: bool = False,
    ) -> None:
        project_path = project.path if isinstance(project, ProjectNode) else Path(project)
        self._validate_project_path(project_path)
        self._delete_or_hide(project_path, delete_files)

    def delete_scan(
        self,
        scan: ScanNode | Path,
        *,
        delete_files: bool = False,
    ) -> None:
        scan_path = scan.path if isinstance(scan, ScanNode) else Path(scan)
        self._validate_scan_path(scan_path)
        self._delete_or_hide(scan_path, delete_files)

    def validate_name(self, name: str) -> str:
        cleaned = name.strip()
        if not cleaned:
            raise InvalidNameError("名称不能为空。")
        if cleaned in {".", ".."}:
            raise InvalidNameError("名称不能是 . 或 ..。")
        if _INVALID_CHARS.search(cleaned):
            raise InvalidNameError('名称不能包含 \\ / : * ? " < > | 等字符。')
        if cleaned.endswith((" ", ".")):
            raise InvalidNameError("名称不能以空格或句点结尾。")
        if cleaned.split(".")[0].upper() in _RESERVED_NAMES:
            raise InvalidNameError("该名称是 Windows 保留名称。")
        if len(cleaned) > 80:
            raise InvalidNameError("名称过长（最多 80 个字符）。")
        return cleaned

    def _sorted_dirs(self, parent: Path) -> list[Path]:
        return sorted(
            (entry for entry in parent.iterdir() if entry.is_dir()),
            key=lambda entry: entry.name.lower(),
        )

    def _unique_name(self, parent: Path, base: str) -> str:
        if not (parent / base).exists():
            return base
        index = 2
        while (parent / f"{base}{index}").exists():
            index += 1
        return f"{base}{index}"

    def _ensure_dir(self, parent: Path, name: str) -> Path:
        path = parent / name
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _rename_dir(self, source: Path, new_name: str) -> Path:
        source = Path(source)
        parent = source.parent
        parent.mkdir(parents=True, exist_ok=True)
        destination = parent / new_name

        if destination == source:
            if not source.exists():
                source.mkdir(parents=True, exist_ok=True)
            return source

        if destination.exists() and destination.name.lower() != source.name.lower():
            raise NameConflictError(f"“{new_name}”已存在。")

        if source.exists():
            source.rename(destination)
        else:
            destination.mkdir(parents=True, exist_ok=True)
        return destination

    @property
    def _hidden_file(self) -> Path:
        return self.root / HIDDEN_MANIFEST_FILENAME

    def _validate_project_path(self, path: Path) -> None:
        target = Path(path).resolve()
        if target.parent != self.root.resolve():
            raise OSError(f"项目路径不属于当前项目目录：{target}")

    def _validate_scan_path(self, path: Path) -> None:
        target = Path(path).resolve()
        if target.parent.parent != self.root.resolve():
            raise OSError(f"扫描路径不属于当前项目目录：{target}")

    def _delete_or_hide(self, path: Path, delete_files: bool) -> None:
        target = Path(path).resolve()
        if delete_files:
            if target.exists():
                shutil.rmtree(target)
            self._remove_hidden_path(target)
        else:
            hidden = self._load_hidden_paths()
            hidden.add(self._relative_key(target))
            self._save_hidden_paths(hidden)

    def _load_hidden_paths(self) -> set[str]:
        try:
            payload = json.loads(self._hidden_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return set()
        if not isinstance(payload, list):
            return set()
        return {
            value.replace("\\", "/")
            for value in payload
            if isinstance(value, str) and value
        }

    def _save_hidden_paths(self, paths: set[str]) -> None:
        if not paths:
            try:
                self._hidden_file.unlink()
            except FileNotFoundError:
                pass
            return
        self._hidden_file.write_text(
            json.dumps(sorted(paths), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _remove_hidden_path(self, path: Path) -> None:
        hidden = self._load_hidden_paths()
        key = self._relative_key(path)
        prefix = key + "/"
        remaining = {
            item
            for item in hidden
            if item != key and not item.startswith(prefix)
        }
        if remaining != hidden:
            self._save_hidden_paths(remaining)

    def _relative_key(self, path: Path) -> str:
        return Path(path).resolve().relative_to(self.root.resolve()).as_posix()
