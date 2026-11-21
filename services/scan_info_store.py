"""扫描选项 scan_info.xml 的保存与读取。"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

from config.settings import SCAN_INFO_FILENAME

PORT_MODES = ("ports", "range")


def save_scan_form(
    scan_path: Path | str,
    values: dict[str, object],
    *,
    filename: str = SCAN_INFO_FILENAME,
) -> Path:
    """把界面扫描选项写入扫描目录中的 scan_info.xml。"""
    scan_dir = Path(scan_path)
    if not scan_dir.is_dir():
        raise FileNotFoundError(f"扫描目录不存在：{scan_dir}")

    root = ET.Element(
        "scan_info",
        {
            "version": "1",
            "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        },
    )
    ET.SubElement(root, "address").text = str(values.get("address", ""))

    mode = str(values.get("mode", PORT_MODES[0]))
    if mode not in PORT_MODES:
        mode = PORT_MODES[0]
    ports_node = ET.SubElement(root, "ports", {"mode": mode})
    ports_node.text = str(values.get("ports", ""))

    exclude_ip = ET.SubElement(
        root,
        "exclude_ip",
        {"enabled": _bool_text(values.get("exclude_ip_mode", False))},
    )
    exclude_ip.text = str(values.get("exclude_ips", ""))

    exclude_ports = ET.SubElement(
        root,
        "exclude_ports",
        {"enabled": _bool_text(values.get("exclude_mode", False))},
    )
    exclude_ports.text = str(values.get("exclude_ports", ""))

    ET.SubElement(root, "ignore_config").text = _bool_text(
        values.get("ignore_config", False)
    )
    ET.SubElement(root, "udp_mode").text = _bool_text(values.get("udp_mode", False))
    ET.SubElement(root, "use_nmap").text = _bool_text(values.get("use_nmap", False))
    ET.SubElement(root, "nmap_extra_args").text = str(
        values.get("nmap_extra_args", "")
    )
    script = ET.SubElement(
        root,
        "script",
        {"enabled": _bool_text(values.get("use_script", False))},
    )
    script.text = str(values.get("script_name", ""))

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    path = scan_dir / filename
    tree.write(path, encoding="utf-8", xml_declaration=True)
    return path


def load_scan_form(
    scan_path: Path | str,
    *,
    filename: str = SCAN_INFO_FILENAME,
) -> dict[str, object]:
    """读取 scan_info.xml；缺失或格式无效时返回空配置。"""
    path = Path(scan_path) / filename
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError):
        return {}
    if root.tag != "scan_info":
        return {}

    ports_node = root.find("ports")
    mode = ports_node.get("mode", PORT_MODES[0]) if ports_node is not None else PORT_MODES[0]
    if mode not in PORT_MODES:
        mode = PORT_MODES[0]

    exclude_ip = root.find("exclude_ip")
    exclude_ports = root.find("exclude_ports")
    script = root.find("script")
    return {
        "address": _text(root.find("address")),
        "mode": mode,
        "ports": _text(ports_node),
        "exclude_ip_mode": _enabled(exclude_ip),
        "exclude_ips": _text(exclude_ip),
        "exclude_mode": _enabled(exclude_ports),
        "exclude_ports": _text(exclude_ports),
        "ignore_config": _bool_value(_text(root.find("ignore_config"))),
        "udp_mode": _bool_value(_text(root.find("udp_mode"))),
        "use_nmap": _bool_value(_text(root.find("use_nmap"))),
        "nmap_extra_args": _text(root.find("nmap_extra_args")),
        "use_script": _enabled(script),
        "script_name": _text(script),
    }


def _text(node: ET.Element | None) -> str:
    return node.text if node is not None and node.text else ""


def _enabled(node: ET.Element | None) -> bool:
    return _bool_value(node.get("enabled", "false")) if node is not None else False


def _bool_text(value: object) -> str:
    return "true" if _bool_value(value) else "false"


def _bool_value(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "on"}
    return bool(value)
