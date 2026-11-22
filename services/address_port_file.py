"""读取地址文件，并识别同一文件中的可选端口列。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from services.address_file import (
    AddressColumnNotFoundError,
    EmptyAddressFileError,
    UnsupportedAddressFileError,
    _HEADER_ALIASES,
    _canonical_address,
    _decode,
    _detect_address_columns,
    _normalize_header,
    _read_csv_rows,
)
from services.port_file import (
    PORT_HEADER_ALIASES,
    detect_port_columns,
    parse_port,
)


@dataclass(frozen=True, slots=True)
class AddressFileData:
    """地址文件中的目标、端口及其一一对应关系。"""

    addresses: tuple[str, ...]
    ports: tuple[int, ...]
    pairs: tuple[tuple[str, int], ...]

    @property
    def has_ports(self) -> bool:
        return bool(self.ports)


def load_address_file(path: Path | str) -> AddressFileData:
    """读取地址文件；地址和端口列同时存在时返回配对结果。"""
    file_path = Path(path)
    suffix = file_path.suffix.lower()
    if suffix not in {".txt", ".csv"}:
        raise UnsupportedAddressFileError("only .txt and .csv files are supported")

    text = _decode(file_path.read_bytes())
    data = (
        _parse_txt(text)
        if suffix == ".txt"
        else _parse_csv(text)
    )
    if not data.addresses:
        raise EmptyAddressFileError("no IP addresses or domains were found")
    return data


def _parse_txt(text: str) -> AddressFileData:
    addresses: list[str] = []
    ports: list[int] = []
    pairs: list[tuple[str, int]] = []
    seen_addresses: set[str] = set()
    seen_ports: set[int] = set()
    seen_pairs: set[tuple[str, int]] = set()

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        tokens = [token for token in re.split(r"[\s,;]+", line) if token]
        if len(tokens) == 2:
            address = _canonical_address(tokens[0])
            port = parse_port(tokens[1])
            if address is not None and port is not None:
                _append_address(addresses, seen_addresses, address)
                _append_port(ports, seen_ports, port)
                _append_pair(pairs, seen_pairs, address, port)
                continue
        for token in tokens:
            address = _canonical_address(token)
            if address is not None:
                _append_address(addresses, seen_addresses, address)

    return AddressFileData(
        addresses=tuple(addresses),
        ports=tuple(ports),
        pairs=tuple(pairs),
    )


def _parse_csv(text: str) -> AddressFileData:
    rows = [
        row
        for row in _read_csv_rows(text)
        if any(cell.strip() for cell in row)
    ]
    if not rows:
        return AddressFileData((), (), ())

    address_indices = {
        index
        for index, cell in enumerate(rows[0])
        if _normalize_header(cell) in _HEADER_ALIASES
    }
    port_indices = {
        index
        for index, cell in enumerate(rows[0])
        if _normalize_header(cell) in PORT_HEADER_ALIASES
    }
    if address_indices:
        data_rows = rows[1:]
    else:
        address_indices = set(_detect_address_columns(rows))
        port_indices = set(
            detect_port_columns(rows, exclude=address_indices)
        )
        data_rows = rows
        if not address_indices:
            raise AddressColumnNotFoundError("no IP or domain column was found")

    addresses: list[str] = []
    ports: list[int] = []
    pairs: list[tuple[str, int]] = []
    seen_addresses: set[str] = set()
    seen_ports: set[int] = set()
    seen_pairs: set[tuple[str, int]] = set()

    for row in data_rows:
        row_addresses = [
            address
            for index in sorted(address_indices)
            if index < len(row)
            if (address := _canonical_address(row[index])) is not None
        ]
        row_ports = [
            port
            for index in sorted(port_indices)
            if index < len(row)
            if (port := parse_port(row[index])) is not None
        ]
        if not row_addresses:
            continue
        if port_indices and not row_ports:
            continue

        for address in row_addresses:
            _append_address(addresses, seen_addresses, address)
        for port in row_ports:
            _append_port(ports, seen_ports, port)
        if row_ports:
            for address, port in _pair_row_addresses(row_addresses, row_ports):
                _append_pair(pairs, seen_pairs, address, port)

    return AddressFileData(
        addresses=tuple(addresses),
        ports=tuple(ports),
        pairs=tuple(pairs),
    )


def _pair_row_addresses(
    addresses: list[str],
    ports: list[int],
) -> list[tuple[str, int]]:
    if len(addresses) == len(ports):
        return list(zip(addresses, ports))
    if len(addresses) == 1:
        return [(addresses[0], port) for port in ports]
    if len(ports) == 1:
        return [(address, ports[0]) for address in addresses]
    return list(zip(addresses, ports))


def _append_address(
    addresses: list[str],
    seen: set[str],
    address: str,
) -> None:
    key = address.casefold()
    if key in seen:
        return
    seen.add(key)
    addresses.append(address)


def _append_port(ports: list[int], seen: set[int], port: int) -> None:
    if port in seen:
        return
    seen.add(port)
    ports.append(port)


def _append_pair(
    pairs: list[tuple[str, int]],
    seen: set[tuple[str, int]],
    address: str,
    port: int,
) -> None:
    key = (address.casefold(), port)
    if key in seen:
        return
    seen.add(key)
    pairs.append((address, port))
