"""从 TXT/CSV 文件读取 0-65535 范围内的端口。"""

from __future__ import annotations

import math
from pathlib import Path

from services.address_file import _decode, _normalize_header, _read_csv_rows


class PortFileError(ValueError):
    """端口文件无法用于扫描。"""


class UnsupportedPortFileError(PortFileError):
    """端口文件扩展名不受支持。"""


class EmptyPortFileError(PortFileError):
    """端口文件中没有有效端口。"""


class PortColumnNotFoundError(PortFileError):
    """CSV 中未找到端口列。"""


PORT_HEADER_ALIASES = {
    "port",
    "ports",
    "portnumber",
    "portnumbers",
    "端口",
    "端口号",
}


def parse_port(value: str) -> int | None:
    """把单元格转换为合法端口；无效或越界时返回 None。"""
    token = value.strip().strip("\"'")
    if not token.isdigit():
        return None
    port = int(token)
    return port if 0 <= port <= 65535 else None


def load_ports(path: Path | str) -> list[int]:
    """读取端口文件并返回去重后的端口列表。"""
    file_path = Path(path)
    suffix = file_path.suffix.lower()
    if suffix not in {".txt", ".csv"}:
        raise UnsupportedPortFileError("only .txt and .csv files are supported")

    text = _decode(file_path.read_bytes())
    ports = (
        _ports_from_txt(text)
        if suffix == ".txt"
        else _ports_from_csv(text)
    )
    if not ports:
        raise EmptyPortFileError("no valid ports were found")
    return ports


def detect_port_columns(
    rows: list[list[str]],
    *,
    exclude: set[int] | None = None,
) -> list[int]:
    """在无表头 CSV 中检测端口列。"""
    excluded = exclude or set()
    width = max((len(row) for row in rows), default=0)
    candidates: list[int] = []
    for index in range(width):
        if index in excluded:
            continue
        values = [
            row[index].strip()
            for row in rows
            if index < len(row) and row[index].strip()
        ]
        if not values:
            continue
        valid = sum(parse_port(value) is not None for value in values)
        if valid and valid >= math.ceil(len(values) * 0.6):
            candidates.append(index)
    return candidates


def _ports_from_txt(text: str) -> list[int]:
    ports: list[int] = []
    seen: set[int] = set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        for token in line.replace(",", " ").replace(";", " ").split():
            port = parse_port(token)
            if port is not None and port not in seen:
                seen.add(port)
                ports.append(port)
    return ports


def _ports_from_csv(text: str) -> list[int]:
    rows = [
        row
        for row in _read_csv_rows(text)
        if any(cell.strip() for cell in row)
    ]
    if not rows:
        return []

    header_indices = {
        index
        for index, cell in enumerate(rows[0])
        if _normalize_header(cell) in PORT_HEADER_ALIASES
    }
    if header_indices:
        data_rows = rows[1:]
    else:
        header_indices = set(detect_port_columns(rows))
        data_rows = rows
        if not header_indices:
            raise PortColumnNotFoundError("no port column was found")

    ports: list[int] = []
    seen: set[int] = set()
    for row in data_rows:
        for index in sorted(header_indices):
            if index >= len(row):
                continue
            port = parse_port(row[index])
            if port is not None and port not in seen:
                seen.add(port)
                ports.append(port)
    return ports
