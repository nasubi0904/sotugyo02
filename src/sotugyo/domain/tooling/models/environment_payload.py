"""ツール環境定義のパス参照を整理する補助。"""

from __future__ import annotations

import re
from typing import Iterable, List

NODE_INPUT_TOKEN_PREFIX = "{{input:"
NODE_INPUT_TOKEN_SUFFIX = "}}"
NODE_INPUT_TOKEN_PATTERN = re.compile(r"\{\{input:([^}]+)\}\}")


def normalize_node_input_name(name: str | None) -> str | None:
    """ノード入力名を正規化する。"""

    if name is None:
        return None
    normalized = str(name).strip()
    if not normalized:
        return None
    if "{" in normalized or "}" in normalized:
        return None
    return normalized


def build_node_input_token(name: str) -> str:
    """ノード入力ディレクトリ参照トークンを生成する。"""

    normalized = normalize_node_input_name(name)
    if normalized is None:
        raise ValueError("入力プラグ名が不正です。")
    return f"{NODE_INPUT_TOKEN_PREFIX}{normalized}{NODE_INPUT_TOKEN_SUFFIX}"


def extract_node_input_names(text: str | None) -> List[str]:
    """文字列内のノード入力トークンを抽出する。"""

    if not text:
        return []
    found: List[str] = []
    for match in NODE_INPUT_TOKEN_PATTERN.finditer(text):
        candidate = normalize_node_input_name(match.group(1))
        if candidate is None:
            continue
        if candidate not in found:
            found.append(candidate)
    return found


def collect_node_input_names(payload: dict) -> List[str]:
    """環境定義ペイロードから入力プラグ名を収集する。"""

    collected: List[str] = []
    raw_inputs = payload.get("node_inputs")
    if isinstance(raw_inputs, Iterable) and not isinstance(raw_inputs, (str, bytes)):
        for entry in raw_inputs:
            normalized = normalize_node_input_name(entry)
            if normalized and normalized not in collected:
                collected.append(normalized)

    for field in ("environment_variables", "launch_arguments"):
        raw_text = payload.get(field)
        if isinstance(raw_text, str):
            for name in extract_node_input_names(raw_text):
                if name not in collected:
                    collected.append(name)

    required_plugins = payload.get("required_plugins")
    if isinstance(required_plugins, list):
        for entry in required_plugins:
            if not isinstance(entry, dict):
                continue
            if entry.get("path_type") != "node":
                continue
            candidate = normalize_node_input_name(entry.get("input_name"))
            if candidate and candidate not in collected:
                collected.append(candidate)

    return collected


__all__ = [
    "NODE_INPUT_TOKEN_PREFIX",
    "NODE_INPUT_TOKEN_SUFFIX",
    "NODE_INPUT_TOKEN_PATTERN",
    "build_node_input_token",
    "collect_node_input_names",
    "extract_node_input_names",
    "normalize_node_input_name",
]
