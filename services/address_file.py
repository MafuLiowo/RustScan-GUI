"""从 TXT/CSV 地址文件读取 IP、CIDR 或域名。"""

from __future__ import annotations

import csv
import io
import ipaddress
import math
import re
from pathlib import Path


class AddressFileError(ValueError):
    """地址文件无法用于扫描。"""


class UnsupportedAddressFileError(AddressFileError):
    """地址文件扩展名不受支持。"""


class EmptyAddressFileError(AddressFileError):
    """地址文件中没有有效地址。"""


class AddressColumnNotFoundError(AddressFileError):
    """CSV 中未找到 IP 或域名列。"""


_HEADER_ALIASES = {
    "ip",
    "ipaddress",
    "ipaddr",
    "address",
    "host",
    "hostname",
    "domain",
    "domainname",
    "target",
    "targetaddress",
    "ipdomain",
    "iphost",
    "ipordomain",
    "iporhost",
    "hostorip",
    "主机",
    "主机名",
    "域名",
    "地址",
    "ip地址",
    "目标",
    "目标地址",
    "扫描地址",
}
_HEADER_SEPARATORS = re.compile(r"[\s_\-/]+")
_HOST_LABEL = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
_HOSTNAME = re.compile(rf"^(?:{_HOST_LABEL}\.)+{_HOST_LABEL}\.?$")
_TXT_SEPARATORS = re.compile(r"[\s,;]+")


def load_addresses(path: Path | str) -> list[str]:
    """读取地址文件并返回去重后的目标列表。"""
    file_path = Path(path)
    suffix = file_path.suffix.lower()
    if suffix not in {".txt", ".csv"}:
        raise UnsupportedAddressFileError("only .txt and .csv files are supported")

    text = _decode(file_path.read_bytes())
    addresses = (
        _addresses_from_txt(text)
        if suffix == ".txt"
        else _addresses_from_csv(text)
    )
    if not addresses:
        raise EmptyAddressFileError("no IP addresses or domains were found")
    return addresses


def _decode(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


def _addresses_from_txt(text: str) -> list[str]:
    addresses: list[str] = []
    seen: set[str] = set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        for token in _TXT_SEPARATORS.split(line):
            address = _canonical_address(token)
            if address is not None:
                _append_unique(addresses, seen, address)
    return addresses


def _addresses_from_csv(text: str) -> list[str]:
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
        if _normalize_header(cell) in _HEADER_ALIASES
    }
    if header_indices:
        data_rows = rows[1:]
    else:
        header_indices = set(_detect_address_columns(rows))
        data_rows = rows
        if not header_indices:
            raise AddressColumnNotFoundError("no IP or domain column was found")

    addresses: list[str] = []
    seen: set[str] = set()
    for row in data_rows:
        for index in sorted(header_indices):
            if index >= len(row):
                continue
            address = _canonical_address(row[index])
            if address is not None:
                _append_unique(addresses, seen, address)
    return addresses


def _read_csv_rows(text: str) -> list[list[str]]:
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    return list(csv.reader(io.StringIO(text), dialect))


def _detect_address_columns(rows: list[list[str]]) -> list[int]:
    width = max((len(row) for row in rows), default=0)
    candidates: list[int] = []
    for index in range(width):
        values = [
            row[index].strip()
            for row in rows
            if index < len(row) and row[index].strip()
        ]
        if not values:
            continue
        valid = sum(_canonical_address(value) is not None for value in values)
        if valid and valid >= math.ceil(len(values) * 0.6):
            candidates.append(index)
    return candidates


def _normalize_header(value: str) -> str:
    return _HEADER_SEPARATORS.sub("", value.strip().lower())


def _canonical_address(value: str) -> str | None:
    token = value.strip().strip("\"'")
    if not token:
        return None
    try:
        if "/" in token:
            ipaddress.ip_network(token, strict=False)
        else:
            ipaddress.ip_address(token)
        return token
    except ValueError:
        pass
    if token.lower() == "localhost" or _HOSTNAME.fullmatch(token):
        return token.rstrip(".")
    return None


def _append_unique(addresses: list[str], seen: set[str], address: str) -> None:
    key = address.casefold()
    if key in seen:
        return
    seen.add(key)
    addresses.append(address)
