"""TXT/CSV 端口文件导入测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from services.port_file import (
    EmptyPortFileError,
    PortColumnNotFoundError,
    UnsupportedPortFileError,
    load_ports,
    parse_port,
)


class PortFileTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.root = Path(self._temp.name)

    def tearDown(self) -> None:
        self._temp.cleanup()

    def test_port_range_and_validation(self) -> None:
        self.assertEqual(parse_port("0"), 0)
        self.assertEqual(parse_port("65535"), 65535)
        self.assertIsNone(parse_port("65536"))
        self.assertIsNone(parse_port("-1"))
        self.assertIsNone(parse_port("http"))

    def test_txt_reads_unique_ports(self) -> None:
        path = self.root / "ports.txt"
        path.write_text(
            "# ports\n"
            "80\n"
            "443,8080\n"
            "80\n",
            encoding="utf-8",
        )

        self.assertEqual(load_ports(path), [80, 443, 8080])

    def test_csv_reads_port_column(self) -> None:
        path = self.root / "ports.csv"
        path.write_text(
            "name,端口号,note\n"
            "http,80,web\n"
            "https,443,secure\n"
            "invalid,70000,skip\n",
            encoding="utf-8",
        )

        self.assertEqual(load_ports(path), [80, 443])

    def test_csv_without_header_detects_port_column(self) -> None:
        path = self.root / "ports.csv"
        path.write_text(
            "192.168.1.10,80\n"
            "192.168.1.11,443\n",
            encoding="utf-8",
        )

        self.assertEqual(load_ports(path), [80, 443])

    def test_invalid_files_are_rejected(self) -> None:
        empty = self.root / "empty.txt"
        empty.write_text("# no ports\n", encoding="utf-8")
        with self.assertRaises(EmptyPortFileError):
            load_ports(empty)

        unsupported = self.root / "ports.json"
        unsupported.write_text("{}", encoding="utf-8")
        with self.assertRaises(UnsupportedPortFileError):
            load_ports(unsupported)

        no_column = self.root / "no_column.csv"
        no_column.write_text("name,note\nfirst,second\n", encoding="utf-8")
        with self.assertRaises(PortColumnNotFoundError):
            load_ports(no_column)


if __name__ == "__main__":
    unittest.main()
