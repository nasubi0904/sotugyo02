"""ツール環境ペイロードの符号定義とユーティリティ。"""

from __future__ import annotations

import re
from typing import Iterable, Mapping, Sequence

INPUT_TOKEN_PATTERN = re.compile(r"\{\{input:([^{}]+)\}\}")

__all__ = [
    "INPUT_TOKEN_PATTERN",
    "collect_input_token_names",
    "contains_input_token",
    "normalize_input_name",
    "normalize_input_plugs",
    "extract_input_plug_names",
]


def normalize_input_name(value: str) -> str:
    """入力プラグ名を安全な形式へ正規化する。"""

    cleaned = str(value).strip()
    if not cleaned:
        return ""
    if any(token in cleaned for token in ("{{", "}}")):
        return ""
    cleaned = cleaned.replace("\n", " ").replace("\r", " ").strip()
    return cleaned


def collect_input_token_names(text: str) -> Sequence[str]:
    """入力トークンからプラグ名を抽出する。"""

    if not text:
        return ()
    names: list[str] = []
    for match in INPUT_TOKEN_PATTERN.findall(text):
        normalized = normalize_input_name(match)
        if not normalized or normalized in names:
            continue
        names.append(normalized)
    return tuple(names)


def contains_input_token(text: str) -> bool:
    """入力トークンを含むか判定する。"""

    if not text:
        return False
    return bool(INPUT_TOKEN_PATTERN.search(text))


def normalize_input_plugs(raw: Iterable[Mapping[str, object]]) -> list[dict[str, str]]:
    """入力プラグ一覧を正規化する。"""

    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for entry in raw:
        if not isinstance(entry, Mapping):
            continue
        name = normalize_input_name(entry.get("name", ""))
        if not name or name in seen:
            continue
        seen.add(name)
        normalized.append({"name": name, "path_kind": "directory"})
    return normalized


def extract_input_plug_names(payload: Mapping[str, object] | None) -> Sequence[str]:
    """ペイロードから入力プラグ名を抽出する。"""

    if not isinstance(payload, Mapping):
        return ()
    raw = payload.get("input_plugs")
    if not isinstance(raw, Iterable):
        return ()
    names = [entry["name"] for entry in normalize_input_plugs(raw)]
    return tuple(names)
