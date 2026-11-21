"""把扫描选项转换为 rustscan 命令行参数。"""

from __future__ import annotations

from models.scan_options import ScanOptions


def build_rustscan_args(options: ScanOptions, *, greppable: bool = True) -> list[str]:
    """构建 rustscan 参数；默认使用 greppable 模式以便程序解析。"""
    args = ["-a", options.address]
    uses_nmap = options.use_nmap or bool(options.use_script and options.script_path)

    if options.ports:
        args.extend(["-p", options.ports])
    if options.port_range:
        args.extend(["-r", options.port_range])
    if options.exclude_addresses:
        args.extend(["-x", options.exclude_addresses])
    if options.exclude_ports:
        args.extend(["-e", options.exclude_ports])
    if options.ignore_config:
        args.append("-n")
    if options.udp:
        args.append("--udp")
    if greppable and not uses_nmap:
        args.append("-g")
    args.append("--no-banner")
    if uses_nmap:
        args.append("--")
        if options.use_nmap:
            args.append("-sV")
        if options.use_script and options.script_path:
            args.extend(["--script", _format_script_path(options.script_path)])
        if options.use_nmap:
            args.extend(_split_nmap_args(options.nmap_extra_args))
    return args


def _format_script_path(value: str) -> str:
    """RustScan 会把额外参数拼成命令字符串，含空格的路径需要保留引号。"""
    if any(char.isspace() for char in value):
        return f'"{value}"'
    return value


def _split_nmap_args(value: str) -> list[str]:
    """按命令行习惯拆分额外参数，同时保留 Windows 路径中的反斜杠。"""
    tokens: list[str] = []
    current: list[str] = []
    quote = ""
    index = 0
    while index < len(value):
        char = value[index]
        if quote:
            if char == quote:
                quote = ""
            elif (
                char == "\\"
                and index + 1 < len(value)
                and value[index + 1] in {quote, "\\"}
            ):
                current.append(value[index + 1])
                index += 1
            else:
                current.append(char)
        elif char in {'"', "'"}:
            quote = char
        elif char.isspace():
            if current:
                tokens.append("".join(current))
                current.clear()
        elif (
            char == "\\"
            and index + 1 < len(value)
            and value[index + 1] in {'"', "'", "\\"}
        ):
            current.append(value[index + 1])
            index += 1
        else:
            current.append(char)
        index += 1
    if current:
        tokens.append("".join(current))
    return tokens
