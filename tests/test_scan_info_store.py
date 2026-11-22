"""扫描选项 scan_info.xml 存取测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from services.scan_info_store import load_scan_form, save_scan_form


class ScanInfoStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.scan_dir = Path(self._temp.name) / "项目" / "扫描"
        self.scan_dir.mkdir(parents=True)

    def tearDown(self) -> None:
        self._temp.cleanup()

    def test_save_and_load_round_trip(self) -> None:
        values = {
            "address": "192.168.1.0/24",
            "address_file_mode": True,
            "address_file": "C:/targets.csv",
            "mode": "range",
            "ports": "1-2048",
            "attack_type": "pitchfork",
            "exclude_ip_mode": True,
            "exclude_ips": "192.168.1.9",
            "exclude_mode": True,
            "exclude_ports": "22,3389",
            "ignore_config": True,
            "udp_mode": True,
            "use_nmap": True,
            "nmap_extra_args": "-sC -sV",
            "use_script": True,
            "script_name": "test.nse",
        }

        path = save_scan_form(self.scan_dir, values)

        self.assertEqual(path.name, "scan_info.xml")
        self.assertEqual(load_scan_form(self.scan_dir), values)

    def test_missing_or_invalid_file_returns_empty_values(self) -> None:
        self.assertEqual(load_scan_form(self.scan_dir), {})

        (self.scan_dir / "scan_info.xml").write_text(
            "<scan_info>",
            encoding="utf-8",
        )

        self.assertEqual(load_scan_form(self.scan_dir), {})

    def test_file_port_mode_and_attack_type_round_trip(self) -> None:
        values = {
            "address": "",
            "address_file_mode": True,
            "address_file": "C:/targets.csv",
            "mode": "file",
            "ports": "C:/targets.csv",
            "attack_type": "pitchfork",
            "exclude_ip_mode": False,
            "exclude_ips": "",
            "exclude_mode": False,
            "exclude_ports": "",
            "ignore_config": False,
            "udp_mode": False,
            "use_nmap": False,
            "nmap_extra_args": "",
            "use_script": False,
            "script_name": "",
        }

        save_scan_form(self.scan_dir, values)
        loaded = load_scan_form(self.scan_dir)

        self.assertEqual(loaded["mode"], "file")
        self.assertEqual(loaded["ports"], "C:/targets.csv")
        self.assertEqual(loaded["attack_type"], "pitchfork")


if __name__ == "__main__":
    unittest.main()
