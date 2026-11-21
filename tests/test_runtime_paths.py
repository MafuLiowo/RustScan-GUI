"""单文件运行目录释放逻辑测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import utils.paths as paths


class RuntimePathsTests(unittest.TestCase):
    def test_releases_bundled_runtime_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app_dir = root / "app"
            bundle_dir = root / "bundle"
            bundled_bin = bundle_dir / "bin" / "rustscan.exe"
            bundled_language = bundle_dir / "language"
            bundled_bin.parent.mkdir(parents=True)
            bundled_language.mkdir(parents=True)
            bundled_bin.write_bytes(b"rustscan binary")
            (bundled_language / "en.xml").write_text(
                "<language />",
                encoding="utf-8",
            )

            bin_dir = app_dir / "bin"
            language_dir = app_dir / "language"
            with patch.multiple(
                paths,
                BIN_DIR=bin_dir,
                LANGUAGE_DIR=language_dir,
                LOGS_DIR=app_dir / "logs",
                PROJECTS_DIR=app_dir / "project",
                SCRIPTS_DIR=app_dir / "script",
                RUSTSCAN_EXECUTABLE=bin_dir / "rustscan.exe",
                BUNDLED_RUSTSCAN_EXECUTABLE=bundled_bin,
                BUNDLED_LANGUAGE_DIR=bundled_language,
            ):
                paths.ensure_runtime_dirs()

                self.assertEqual(
                    (bin_dir / "rustscan.exe").read_bytes(),
                    b"rustscan binary",
                )
                self.assertEqual(
                    (language_dir / "en.xml").read_text(encoding="utf-8"),
                    "<language />",
                )
                for name in ("bin", "language", "logs", "project", "script"):
                    self.assertTrue((app_dir / name).is_dir())

                (bin_dir / "rustscan.exe").write_bytes(b"old binary!!")
                paths.ensure_runtime_dirs()

            self.assertEqual(
                (bin_dir / "rustscan.exe").read_bytes(),
                b"rustscan binary",
            )


if __name__ == "__main__":
    unittest.main()
