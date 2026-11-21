"""项目与扫描的本地目录模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class ScanNode:
    """项目下的一个扫描子项，对应一个本机子文件夹。"""

    name: str
    path: Path


@dataclass(slots=True)
class ProjectNode:
    """左侧栏中的一个项目，对应 project/ 下的一个文件夹。"""

    name: str
    path: Path
    scans: list[ScanNode] = field(default_factory=list)