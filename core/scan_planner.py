"""把地址、端口和攻击类型转换为顺序执行的扫描任务。"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Iterable, Sequence


ATTACK_SNIPER = "sniper"
ATTACK_PITCHFORK = "pitchfork"
ATTACK_TYPES = (ATTACK_SNIPER, ATTACK_PITCHFORK)


@dataclass(frozen=True, slots=True)
class ScanJob:
    """一次 RustScan 调用使用的地址与端口。"""

    address: str
    ports: str = ""
    port_range: str = ""


def build_scan_jobs(
    addresses: Sequence[str],
    *,
    pairs: Sequence[tuple[str, int]] = (),
    imported_ports: Sequence[int] = (),
    port_text: str = "",
    port_range: str = "",
    attack_type: str = ATTACK_SNIPER,
) -> list[ScanJob]:
    """生成扫描任务；pitchfork 按一一对应关系拆分。"""
    clean_addresses = _unique_strings(addresses)
    if pairs:
        pair_addresses = _unique_strings([address for address, _port in pairs])
        pair_ports = _unique_ports(port for _address, port in pairs)
        if attack_type == ATTACK_SNIPER:
            return [
                ScanJob(
                    address=",".join(pair_addresses or clean_addresses),
                    ports=",".join(str(port) for port in pair_ports),
                )
            ]
        return [
            ScanJob(address=address, ports=str(port))
            for address, port in pairs
        ]

    if imported_ports:
        ports_text = ",".join(str(port) for port in imported_ports)
        if attack_type == ATTACK_PITCHFORK:
            return [
                ScanJob(address=address, ports=str(port))
                for address, port in zip(clean_addresses, imported_ports)
            ]
        return [
            ScanJob(
                address=",".join(clean_addresses),
                ports=ports_text,
            )
        ]

    if not clean_addresses:
        return []
    return [
        ScanJob(
            address=",".join(clean_addresses),
            ports=port_text,
            port_range=port_range,
        )
    ]


def _unique_strings(values: Sequence[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = value.strip()
        key = clean.casefold()
        if not clean or key in seen:
            continue
        seen.add(key)
        unique.append(clean)
    return unique


def _unique_ports(values: Iterable[int]) -> list[int]:
    unique: list[int] = []
    seen: set[int] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique
