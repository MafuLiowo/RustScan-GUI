"""端口扫描结果的数据结构。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class PortResult:
    """一条端口结果，可直接写入 XML 或展示在表格中。"""

    address: str
    port: str
    protocol: str = ""
    state: str = ""
    service: str = ""
    version: str = ""