"""script/ 目录脚本存储测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from services.script_store import (
    InvalidScriptNameError,
    ScriptExistsError,
    ScriptStore,
)


class ScriptStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.store = ScriptStore(Path(self._temp.name) / "script")

    def tearDown(self) -> None:
        self._temp.cleanup()

    def test_write_list_and_read_script(self) -> None:
        self.store.write_script("demo.nse", "print('hello')")
        self.store.write_script("alpha.txt", "alpha")

        self.assertEqual(self.store.list_scripts(), ["alpha.txt", "demo.nse"])
        self.assertEqual(self.store.read_script("demo.nse"), "print('hello')")

    def test_duplicate_script_name_is_rejected(self) -> None:
        self.store.write_script("demo.nse", "print('hello')")

        with self.assertRaises(ScriptExistsError):
            self.store.write_script("demo.nse", "other")

    def test_invalid_script_names_are_rejected(self) -> None:
        for name in ("", "..", "../escape", "bad/name", "CON"):
            with self.subTest(name=name):
                with self.assertRaises(InvalidScriptNameError):
                    self.store.write_script(name, "content")


if __name__ == "__main__":
    unittest.main()
