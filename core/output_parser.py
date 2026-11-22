"""解析 RustScan 的 greppable / Open 行及 Nmap 服务行输出。"""

from __future__ import annotations

import re

from models.result import PortResult

_GREPPABLE_LINE = re.compile(r"^\s*(\S+)\s*->\s*\[([^\]]*)\]\s*$")
_OPEN_LINE = re.compile(r"^\s*Open\s+(\S+):(\d+)\s*$", re.IGNORECASE)
_NMAP_REPORT_LINE = re.compile(
    r"^\s*Nmap scan report for (?P<host>.+?)(?:\s+\((?P<ip>[^)]+)\))?\s*$",
    re.IGNORECASE,
)
_NMAP_SERVICE_LINE = re.compile(
    r"^\s*(?P<port>\d+)/(?P<protocol>tcp|udp)\s+"
    r"(?P<state>open\|filtered|open|closed|filtered)\s+"
    r"(?P<service>\S+)(?:\s+(?P<rest>.*?))?\s*$",
    re.IGNORECASE,
)
_NMAP_REASON_PREFIX = re.compile(
    r"^(?:syn-ack|no-response|reset|conn-refused|host-unreach|net-unreach|"
    r"proto-unreach|port-unreach|admin-prohibited)(?:\s+ttl\s+\d+)?\s+",
    re.IGNORECASE,
)
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def parse_open_port_line(
    line: str,
    *,
    protocol: str = "tcp",
) -> PortResult | None:
    """解析单行 ``Open host:port`` 输出，用于扫描过程中的即时结果。"""
    opened = _OPEN_LINE.match(_ANSI_ESCAPE.sub("", line))
    if opened is None:
        return None
    return PortResult(
        address=opened.group(1),
        port=opened.group(2),
        protocol=protocol,
        state="open",
    )


def parse_rustscan_output(
    output: str,
    *,
    protocol: str = "tcp",
    target: str = "",
) -> list[PortResult]:
    """把 rustscan 输出转换为去重、排序后的端口结果。"""
    results: list[PortResult] = []
    current_address = target.strip()
    for raw_line in output.splitlines():
        line = _ANSI_ESCAPE.sub("", raw_line)
        report = _NMAP_REPORT_LINE.match(line)
        if report:
            current_address = (
                report.group("ip") or report.group("host") or current_address
            ).strip()
            continue

        greppable = _GREPPABLE_LINE.match(line)
        if greppable:
            address = greppable.group(1).strip()
            for token in greppable.group(2).split(","):
                port = token.strip()
                if port.isdigit():
                    results.append(
                        PortResult(
                            address=address,
                            port=port,
                            protocol=protocol,
                            state="open",
                        )
                    )
            continue

        opened = parse_open_port_line(line, protocol=protocol)
        if opened is not None:
            results.append(opened)
            current_address = opened.address.strip()
            continue

        service_line = _NMAP_SERVICE_LINE.match(line)
        if service_line and current_address:
            rest = (service_line.group("rest") or "").strip()
            rest = _NMAP_REASON_PREFIX.sub("", rest, count=1).strip()
            results.append(
                PortResult(
                    address=current_address,
                    port=service_line.group("port"),
                    protocol=service_line.group("protocol").lower(),
                    state=service_line.group("state").lower(),
                    service=service_line.group("service"),
                    version=rest,
                )
            )

    unique: list[PortResult] = []
    index_by_key: dict[tuple[str, str, str], int] = {}
    for result in results:
        key = (result.address, result.port, result.protocol)
        existing_index = index_by_key.get(key)
        if existing_index is not None:
            existing = unique[existing_index]
            if result.service:
                existing.service = result.service
            if result.version:
                existing.version = result.version
            if result.state and not existing.state:
                existing.state = result.state
            continue
        index_by_key[key] = len(unique)
        unique.append(result)

    unique.sort(key=lambda item: (item.address, int(item.port) if item.port.isdigit() else 10**9))
    return unique
