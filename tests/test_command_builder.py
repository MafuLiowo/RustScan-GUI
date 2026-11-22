"""RustScan 命令行参数构建测试。"""

from __future__ import annotations

import unittest

from core.command_builder import build_rustscan_args
from models.scan_options import ScanOptions


class CommandBuilderTests(unittest.TestCase):
    def test_builds_all_supported_options(self) -> None:
        options = ScanOptions(
            address="10.0.0.0/24",
            ports="80,443",
            exclude_addresses="10.0.0.8",
            exclude_ports="22,3389",
            ignore_config=True,
            udp=True,
        )

        self.assertEqual(
            build_rustscan_args(options),
            [
                "-a",
                "10.0.0.0/24",
                "-p",
                "80,443",
                "-x",
                "10.0.0.8",
                "-e",
                "22,3389",
                "-n",
                "--udp",
                "-g",
                "--no-banner",
            ],
        )

    def test_builds_port_range(self) -> None:
        options = ScanOptions(address="127.0.0.1", port_range="80-8080")

        self.assertEqual(
            build_rustscan_args(options),
            ["-a", "127.0.0.1", "-r", "80-8080", "-g", "--no-banner"],
        )

    def test_defaults_omit_optional_arguments(self) -> None:
        options = ScanOptions(address="127.0.0.1")

        self.assertEqual(
            build_rustscan_args(options),
            ["-a", "127.0.0.1", "-g", "--no-banner"],
        )

    def test_use_nmap_omits_greppable_and_enables_service_detection(self) -> None:
        options = ScanOptions(address="127.0.0.1", ports="80", use_nmap=True)

        self.assertEqual(
            build_rustscan_args(options),
            [
                "-a",
                "127.0.0.1",
                "-p",
                "80",
                "--no-banner",
                "--",
                "-sV",
            ],
        )

    def test_appends_extra_nmap_arguments_after_double_dash(self) -> None:
        options = ScanOptions(
            address="127.0.0.1",
            ports="80",
            use_nmap=True,
            nmap_extra_args=r'-sC --script-args="a b" --script C:\tools\http.nse',
        )

        self.assertEqual(
            build_rustscan_args(options),
            [
                "-a",
                "127.0.0.1",
                "-p",
                "80",
                "--no-banner",
                "--",
                "-sV",
                "-sC",
                "--script-args=a b",
                "--script",
                r"C:\tools\http.nse",
            ],
        )

    def test_extra_nmap_arguments_are_sent_when_version_detection_is_disabled(self) -> None:
        options = ScanOptions(
            address="127.0.0.1",
            use_nmap=False,
            nmap_extra_args="-sC",
        )

        self.assertEqual(
            build_rustscan_args(options),
            ["-a", "127.0.0.1", "--no-banner", "--", "-sC"],
        )

    def test_uses_selected_script_through_nmap(self) -> None:
        script_path = r"C:\Program Files\Nmap\scripts\http.nse"
        options = ScanOptions(
            address="127.0.0.1",
            ports="80",
            use_script=True,
            script_path=script_path,
        )

        self.assertEqual(
            build_rustscan_args(options),
            [
                "-a",
                "127.0.0.1",
                "-p",
                "80",
                "--no-banner",
                "--",
                "--script",
                f'"{script_path}"',
            ],
        )


if __name__ == "__main__":
    unittest.main()
