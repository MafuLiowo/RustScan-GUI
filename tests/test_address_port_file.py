"""地址文件中可选端口列与地址端口配对测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from services.address_port_file import load_address_file


class AddressPortFileTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.root = Path(self._temp.name)

    def tearDown(self) -> None:
        self._temp.cleanup()

    def test_address_only_file_has_no_ports(self) -> None:
        path = self.root / "targets.csv"
        path.write_text("ip,note\n192.168.1.10,a\n", encoding="utf-8")

        data = load_address_file(path)

        self.assertEqual(data.addresses, ("192.168.1.10",))
        self.assertFalse(data.has_ports)
        self.assertEqual(data.pairs, ())

    def test_address_and_port_columns_are_paired(self) -> None:
        path = self.root / "targets.csv"
        path.write_text(
            "域名,端口\n"
            "one.example.com,80\n"
            "two.example.com,443\n",
            encoding="utf-8",
        )

        data = load_address_file(path)

        self.assertEqual(data.addresses, ("one.example.com", "two.example.com"))
        self.assertEqual(data.ports, (80, 443))
        self.assertEqual(
            data.pairs,
            (("one.example.com", 80), ("two.example.com", 443)),
        )

    def test_invalid_address_and_its_port_are_skipped(self) -> None:
        path = self.root / "targets.csv"
        path.write_text(
            "ip,port\n"
            "192.168.1.10,80\n"
            "not an address,443\n"
            "192.168.1.11,70000\n"
            "192.168.1.12,8080\n",
            encoding="utf-8",
        )

        data = load_address_file(path)

        self.assertEqual(data.addresses, ("192.168.1.10", "192.168.1.12"))
        self.assertEqual(data.ports, (80, 8080))
        self.assertEqual(
            data.pairs,
            (("192.168.1.10", 80), ("192.168.1.12", 8080)),
        )

    def test_txt_address_port_pairs(self) -> None:
        path = self.root / "targets.txt"
        path.write_text(
            "one.example.com 80\n"
            "192.168.1.10,443\n",
            encoding="utf-8",
        )

        data = load_address_file(path)

        self.assertEqual(
            data.pairs,
            (("one.example.com", 80), ("192.168.1.10", 443)),
        )


if __name__ == "__main__":
    unittest.main()
