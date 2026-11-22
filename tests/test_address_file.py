"""TXT/CSV 地址文件导入测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from services.address_file import (
    AddressColumnNotFoundError,
    EmptyAddressFileError,
    UnsupportedAddressFileError,
    load_addresses,
)


class AddressFileTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.root = Path(self._temp.name)

    def tearDown(self) -> None:
        self._temp.cleanup()

    def test_txt_supports_newlines_comments_and_duplicates(self) -> None:
        path = self.root / "targets.txt"
        path.write_text(
            "# scan targets\n"
            "192.168.1.10\n"
            "192.168.1.10\n"
            "example.com\n"
            "10.0.0.0/24\n",
            encoding="utf-8",
        )

        self.assertEqual(
            load_addresses(path),
            ["192.168.1.10", "example.com", "10.0.0.0/24"],
        )

    def test_csv_reads_ip_and_domain_columns(self) -> None:
        path = self.root / "targets.csv"
        path.write_text(
            "name,IP address,Domain,port\n"
            "first,192.168.1.10,one.example.com,80\n"
            "second,192.168.1.11,two.example.com,443\n",
            encoding="utf-8",
        )

        self.assertEqual(
            load_addresses(path),
            [
                "192.168.1.10",
                "one.example.com",
                "192.168.1.11",
                "two.example.com",
            ],
        )

    def test_csv_supports_chinese_headers_and_semicolon_delimiter(self) -> None:
        path = self.root / "targets.csv"
        path.write_text(
            "IP地址;域名;端口\n"
            "192.168.1.20;example.com;80\n",
            encoding="utf-8",
        )

        self.assertEqual(
            load_addresses(path),
            ["192.168.1.20", "example.com"],
        )

    def test_csv_without_header_detects_address_column(self) -> None:
        path = self.root / "targets.csv"
        path.write_text(
            "192.168.1.30,80\n"
            "192.168.1.31,443\n",
            encoding="utf-8",
        )

        self.assertEqual(
            load_addresses(path),
            ["192.168.1.30", "192.168.1.31"],
        )

    def test_empty_and_unsupported_files_are_rejected(self) -> None:
        empty = self.root / "empty.txt"
        empty.write_text("# no targets\n", encoding="utf-8")
        with self.assertRaises(EmptyAddressFileError):
            load_addresses(empty)

        unsupported = self.root / "targets.json"
        unsupported.write_text("{}", encoding="utf-8")
        with self.assertRaises(UnsupportedAddressFileError):
            load_addresses(unsupported)

    def test_csv_without_address_column_is_rejected(self) -> None:
        path = self.root / "targets.csv"
        path.write_text(
            "name,port\n"
            "first,80\n",
            encoding="utf-8",
        )

        with self.assertRaises(AddressColumnNotFoundError):
            load_addresses(path)


if __name__ == "__main__":
    unittest.main()
