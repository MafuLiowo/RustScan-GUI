"""一次扫描所需的命令行参数。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ScanOptions:
    """界面收集并由命令构建器转换为 rustscan 参数。"""

    address: str
    ports: str = ""
    port_range: str = ""
    exclude_addresses: str = ""
    exclude_ports: str = ""
    ignore_config: bool = False
    udp: bool = False
    use_nmap: bool = False
    nmap_extra_args: str = ""
    use_script: bool = False
    script_path: str = ""
