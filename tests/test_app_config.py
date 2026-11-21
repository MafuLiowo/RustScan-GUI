"""config.ini 语言配置读写测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from config.settings import DEFAULT_NMAP_PATH
from services.app_config import (
    read_display_mode,
    read_language,
    read_nmap_path,
    write_display_mode,
    write_language,
    write_nmap_path,
)


class AppConfigTests(unittest.TestCase):
    def test_missing_config_defaults_to_english(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(read_language(Path(temp) / "config.ini"), "en")

    def test_write_language_uses_requested_format(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "config.ini"

            write_language(path, "zh_CN")

            self.assertEqual(path.read_text(encoding="utf-8"), 'language = "zh_CN"\n')
            self.assertEqual(read_language(path), "zh_CN")

    def test_invalid_config_defaults_to_english(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "config.ini"
            path.write_text("not a language setting\n", encoding="utf-8")

            self.assertEqual(read_language(path), "en")

    def test_missing_display_mode_defaults_to_dark(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(read_display_mode(Path(temp) / "config.ini"), "dark")

    def test_display_mode_is_written_and_preserves_language(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "config.ini"

            write_language(path, "zh_CN")
            write_display_mode(path, "light")

            self.assertEqual(
                path.read_text(encoding="utf-8"),
                'language = "zh_CN"\ndisplay_mode = "light"\n',
            )
            self.assertEqual(read_language(path), "zh_CN")
            self.assertEqual(read_display_mode(path), "light")

            write_language(path, "en")

            self.assertEqual(
                path.read_text(encoding="utf-8"),
                'language = "en"\ndisplay_mode = "light"\n',
            )
            self.assertEqual(read_display_mode(path), "light")

    def test_invalid_display_mode_defaults_to_dark(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "config.ini"
            path.write_text('display_mode = "sepia"\n', encoding="utf-8")

            self.assertEqual(read_display_mode(path), "dark")

    def test_missing_nmap_path_defaults_to_common_windows_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "config.ini"

            self.assertEqual(read_nmap_path(path), DEFAULT_NMAP_PATH)

    def test_nmap_path_is_written_and_preserves_existing_settings(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "config.ini"
            nmap_path = r"C:\Tools\Nmap\nmap.exe"

            write_language(path, "zh_CN")
            write_display_mode(path, "light")
            write_nmap_path(path, nmap_path)

            self.assertEqual(
                path.read_text(encoding="utf-8"),
                'language = "zh_CN"\n'
                'display_mode = "light"\n'
                f'nmap_path = "{nmap_path}"\n',
            )
            self.assertEqual(read_language(path), "zh_CN")
            self.assertEqual(read_display_mode(path), "light")
            self.assertEqual(read_nmap_path(path), nmap_path)


if __name__ == "__main__":
    unittest.main()
