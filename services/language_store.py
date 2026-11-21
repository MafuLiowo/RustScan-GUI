"""XML 语言包加载与文本查询。"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from config.settings import DEFAULT_LANGUAGE, LANGUAGE_DIR


class LanguageStoreError(Exception):
    """语言包目录或默认语言不可用。"""


@dataclass(frozen=True, slots=True)
class LanguageInfo:
    """可供设置页选择的语言。"""

    code: str
    name: str
    path: Path


@dataclass(frozen=True, slots=True)
class LanguagePack:
    """一个 XML 语言包及其键值文本。"""

    info: LanguageInfo
    texts: dict[str, str]


class LanguageStore:
    """从 language/*.xml 加载语言，并按当前语言返回界面文字。"""

    def __init__(
        self,
        root: Path | str | None = None,
        *,
        default_code: str = DEFAULT_LANGUAGE,
    ) -> None:
        self.root = Path(root) if root is not None else LANGUAGE_DIR
        self.default_code = default_code
        self._packs = self._load_packs()
        if not self._packs:
            raise LanguageStoreError(f"未找到可用的 XML 语言包：{self.root}")
        if default_code not in self._packs:
            raise LanguageStoreError(f"缺少默认语言包：{default_code}")
        self.current_code = default_code

    def languages(self) -> list[LanguageInfo]:
        infos = [pack.info for pack in self._packs.values()]
        return sorted(
            infos,
            key=lambda info: (info.code != self.default_code, info.code.lower()),
        )

    def select(self, code: str) -> LanguageInfo:
        pack = self._packs.get(code)
        if pack is None:
            raise KeyError(f"未知语言：{code}")
        self.current_code = code
        return pack.info

    def current_language(self) -> LanguageInfo:
        return self._packs[self.current_code].info

    def text(self, key: str, **values: object) -> str:
        template = self._packs[self.current_code].texts.get(key)
        if template is None:
            template = self._packs[self.default_code].texts.get(key, key)
        try:
            return template.format(**values) if values else template
        except (KeyError, IndexError, ValueError):
            return template

    def _load_packs(self) -> dict[str, LanguagePack]:
        packs: dict[str, LanguagePack] = {}
        if not self.root.is_dir():
            return packs

        for path in sorted(self.root.glob("*.xml")):
            try:
                root = ET.parse(path).getroot()
            except (ET.ParseError, OSError):
                continue
            if root.tag != "language":
                continue

            code = (root.get("code") or path.stem).strip()
            name = (root.get("name") or code).strip()
            texts = {
                key: (node.text or "").strip()
                for node in root.findall("text")
                if (key := (node.get("key") or "").strip())
            }
            if not code or not texts:
                continue
            packs[code] = LanguagePack(
                info=LanguageInfo(code=code, name=name, path=path),
                texts=texts,
            )
        return packs
