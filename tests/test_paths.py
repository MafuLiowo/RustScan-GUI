"""应用路径解析测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from utils.paths import resolve_nmap


class PathResolutionTests(unittest.TestCase):
    def test_configured_nmap_path_takes_precedence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            executable = Path(temp) / "nmap.exe"
            executable.write_text("", encoding="utf-8")

            self.assertEqual(resolve_nmap(executable), executable)

    def test_configured_nmap_directory_resolves_executable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "Nmap"
            folder.mkdir()
            executable = folder / "nmap.exe"
            executable.write_text("", encoding="utf-8")

            self.assertEqual(resolve_nmap(folder), executable)


if __name__ == "__main__":
    unittest.main()
