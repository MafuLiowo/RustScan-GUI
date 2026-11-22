"""扫描结果的 XML 保存与读取。

约定：每个扫描文件夹可以保存多个 .xml 结果文件，默认写入 result.xml。
读取时同时兼容本应用的 <scan_results> 格式与 Nmap/RustScan 的 <nmaprun> 格式。
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from config.settings import SCAN_INFO_FILENAME
from models.result import PortResult

DEFAULT_RESULT_FILENAME = "result.xml"
_JOB_TARGET_RE = re.compile(
    r"^\s*(\d+)\s*(?:组扫描任务|scan\s+jobs?)\s*$",
    re.IGNORECASE,
)


@dataclass(slots=True)
class ResultDocument:
    """一个 XML 结果文件及其解析出的端口记录。"""

    path: Path
    target: str
    results: list[PortResult]
    error: str | None = None
    job_count: int | None = None


def save_results(
    scan_path: Path | str,
    results: Iterable[PortResult],
    *,
    target: str = "",
    filename: str = DEFAULT_RESULT_FILENAME,
    job_count: int | None = None,
) -> Path:
    """把端口结果写入扫描文件夹中的 XML 文件。"""
    scan_dir = Path(scan_path)
    scan_dir.mkdir(parents=True, exist_ok=True)

    attributes = {
        "target": target,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    if job_count is not None and job_count > 1:
        attributes["job_count"] = str(job_count)
    root = ET.Element("scan_results", attributes)
    for result in results:
        ET.SubElement(
            root,
            "result",
            {
                "address": str(result.address),
                "port": str(result.port),
                "protocol": str(result.protocol),
                "state": str(result.state),
                "service": str(result.service),
                "version": str(result.version),
            },
        )

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    path = scan_dir / filename
    tree.write(path, encoding="utf-8", xml_declaration=True)
    return path


def load_result_documents(scan_path: Path | str) -> list[ResultDocument]:
    """读取扫描文件夹内全部 XML 结果，按修改时间从新到旧排序。"""
    scan_dir = Path(scan_path)
    if not scan_dir.is_dir():
        return []

    files: list[tuple[float, Path]] = []
    try:
        entries = list(scan_dir.iterdir())
    except OSError:
        return []

    for entry in entries:
        if not entry.is_file() or entry.suffix.lower() != ".xml":
            continue
        if entry.name.casefold() == SCAN_INFO_FILENAME.casefold():
            continue
        try:
            modified = entry.stat().st_mtime
        except OSError:
            modified = 0.0
        files.append((modified, entry))

    files.sort(key=lambda pair: pair[0], reverse=True)
    return [_parse_file(path) for _, path in files]


def _parse_file(path: Path) -> ResultDocument:
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as exc:
        return ResultDocument(path=path, target="", results=[], error=str(exc))

    if root.tag == "nmaprun":
        results = _parse_nmap(root)
    else:
        results = _parse_generic(root)

    results.sort(key=_sort_key)
    return ResultDocument(
        path=path,
        target=_target_name(root, results),
        results=results,
        job_count=_job_count(root),
    )


def _parse_nmap(root: ET.Element) -> list[PortResult]:
    results: list[PortResult] = []
    for host in root.findall("host"):
        address = ""
        for node in host.findall("address"):
            if node.get("addrtype") in (None, "ipv4", "ipv6"):
                address = node.get("addr") or ""
                break
        if not address:
            node = host.find("address")
            if node is not None:
                address = node.get("addr") or ""

        for port in host.findall("./ports/port"):
            state_node = port.find("state")
            service_node = port.find("service")
            state = state_node.get("state", "") if state_node is not None else ""
            service = service_node.get("name", "") if service_node is not None else ""
            product = service_node.get("product", "") if service_node is not None else ""
            version = service_node.get("version", "") if service_node is not None else ""
            extra = service_node.get("extrainfo", "") if service_node is not None else ""
            details = " ".join(part for part in (product, version) if part) or extra
            results.append(
                PortResult(
                    address=address,
                    port=port.get("portid", ""),
                    protocol=port.get("protocol", ""),
                    state=state,
                    service=service,
                    version=details,
                )
            )
    return results


def _parse_generic(root: ET.Element) -> list[PortResult]:
    results: list[PortResult] = []
    for node in root.iter():
        if node.tag not in {"result", "port"}:
            continue

        state_node = node.find("state")
        service_node = node.find("service")
        address = node.get("address") or node.get("host") or node.get("addr") or ""
        port = node.get("port") or node.get("portid") or ""
        protocol = node.get("protocol") or ""
        state = node.get("state") or ""
        service = node.get("service") or ""
        version = node.get("version") or ""

        if state_node is not None:
            state = state or state_node.get("state", "")
        if service_node is not None:
            service = service or service_node.get("name", "")
            product = service_node.get("product", "")
            svc_version = service_node.get("version", "")
            version = version or " ".join(part for part in (product, svc_version) if part)

        if address or port:
            results.append(
                PortResult(
                    address=address,
                    port=port,
                    protocol=protocol,
                    state=state,
                    service=service,
                    version=version,
                )
            )
    return results


def _sort_key(result: PortResult) -> tuple[str, int, str]:
    try:
        port = int(result.port)
    except (TypeError, ValueError):
        port = 10**9
    return (result.address, port, result.protocol)


def _target_name(root: ET.Element, results: list[PortResult]) -> str:
    target = root.get("target") or root.get("address") or ""
    if target:
        return target
    addresses = {result.address for result in results if result.address}
    if len(addresses) == 1:
        return next(iter(addresses))
    if len(addresses) > 1:
        return f"{len(addresses)} 个主机"
    return ""


def _job_count(root: ET.Element) -> int | None:
    value = root.get("job_count")
    if value:
        try:
            count = int(value)
        except ValueError:
            count = 0
        if count > 1:
            return count

    target = root.get("target") or ""
    match = _JOB_TARGET_RE.match(target)
    if match:
        return int(match.group(1))
    return None
