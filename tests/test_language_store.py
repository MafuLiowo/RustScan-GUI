"""XML 语言包加载与查询测试。"""

from __future__ import annotations

import re
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from config.settings import LANGUAGE_DIR, PROJECT_ROOT
from services.language_store import LanguageStore


class LanguageStoreTests(unittest.TestCase):
    def test_default_language_is_english(self) -> None:
        store = LanguageStore()

        self.assertEqual(store.current_code, "en")
        self.assertEqual(store.current_language().name, "English")
        self.assertEqual(store.text("menu.file"), "File")

    def test_available_languages_include_simplified_chinese(self) -> None:
        store = LanguageStore()
        languages = {language.code: language for language in store.languages()}

        self.assertEqual(languages["en"].name, "English")
        self.assertEqual(languages["zh_CN"].name, "简体中文")

    def test_switching_language_changes_text(self) -> None:
        store = LanguageStore()
        store.select("zh_CN")

        self.assertEqual(store.text("menu.file"), "文件")
        self.assertEqual(
            store.text("status.selected", name="目标", path="C:/project"),
            "选中：目标  ·  C:/project",
        )

    def test_english_and_chinese_packs_have_the_same_keys(self) -> None:
        english = self._keys(LANGUAGE_DIR / "en.xml")
        chinese = self._keys(LANGUAGE_DIR / "zh_CN.xml")

        self.assertEqual(english, chinese)
        self.assertIn("menu.settings", english)
        self.assertIn("settings.language_label", english)

    def test_all_ui_translation_keys_exist_in_english_pack(self) -> None:
        source = (PROJECT_ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        used_keys = set(re.findall(r'self\._t\("([^"]+)"', source))
        english_keys = self._keys(LANGUAGE_DIR / "en.xml")

        self.assertTrue(used_keys)
        self.assertEqual(used_keys - english_keys, set())

    def test_missing_key_falls_back_to_english(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "en.xml").write_text(
                '<language code="en" name="English">'
                '<text key="menu.file">File</text>'
                "</language>",
                encoding="utf-8",
            )
            (root / "zh_CN.xml").write_text(
                '<language code="zh_CN" name="简体中文">'
                '<text key="menu.file">文件</text>'
                "</language>",
                encoding="utf-8",
            )
            store = LanguageStore(root)
            store.select("zh_CN")

            self.assertEqual(store.text("menu.file"), "文件")
            self.assertEqual(store.text("menu.missing"), "menu.missing")

    @staticmethod
    def _keys(path: Path) -> set[str]:
        root = ET.parse(path).getroot()
        return {
            node.get("key", "")
            for node in root.findall("text")
            if node.get("key")
        }


if __name__ == "__main__":
    unittest.main()
