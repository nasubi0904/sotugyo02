"""ツール環境編集用のペイロード定義と解析ヘルパー。"""

from __future__ import annotations

import re
from typing import Iterable, List, Tuple

ENVIRONMENT_FILE_SCHEMA = "sotugyo.tool_environment"
ENVIRONMENT_FILE_VERSION = 1
TOOL_ENV_PAYLOAD_VERSION = 1

NODE_INPUT_TOKEN = "input_dir"
NODE_INPUT_PATTERN = re.compile(r"\{\{\s*input_dir:([^}]+)\}\}")


def normalize_input_plug_name(name: str) -> str | None:
    """ノード入力プラグ名を正規化し、無効なら None を返す。"""

    cleaned = " ".join(name.split()).strip()
    if not cleaned:
        return None
    if len(cleaned) > 64:
        return None
    if any(char in cleaned for char in ("{", "}", ":", "\n", "\r", "\t")):
        return None
    return cleaned


def parse_node_input_segments(text: str) -> Tuple[List[dict], List[str]]:
    """入力プレースホルダを含む文字列をセグメント化する。"""

    segments: List[dict] = []
    invalid: List[str] = []
    last_index = 0

    for match in NODE_INPUT_PATTERN.finditer(text):
        start, end = match.span()
        if start > last_index:
            segments.append({"type": "text", "value": text[last_index:start]})
        raw_name = match.group(1).strip()
        normalized = normalize_input_plug_name(raw_name)
        if normalized is None:
            invalid.append(raw_name)
            segments.append({"type": "text", "value": text[start:end]})
        else:
            segments.append(
                {
                    "type": "node_input",
                    "name": normalized,
                    "path_kind": "directory",
                }
            )
        last_index = end

    if last_index < len(text):
        segments.append({"type": "text", "value": text[last_index:]})

    if not segments:
        segments.append({"type": "text", "value": text})
    return segments, invalid


def collect_node_input_names(segments: Iterable[dict]) -> List[str]:
    """セグメントからノード入力名を収集する。"""

    names: List[str] = []
    for segment in segments:
        if segment.get("type") != "node_input":
            continue
        name = segment.get("name")
        if isinstance(name, str) and name and name not in names:
            names.append(name)
    return names


def build_environment_file_payload(
    *,
    environment_id: str,
    name: str,
    tool_id: str,
    package: str | None,
    version_label: str,
    payload: dict,
) -> dict:
    """環境ファイル用のペイロードを構成する。"""

    return {
        "schema": ENVIRONMENT_FILE_SCHEMA,
        "version": ENVIRONMENT_FILE_VERSION,
        "environment_id": environment_id,
        "name": name,
        "tool": {
            "tool_id": tool_id,
            "package": package,
            "version": version_label,
        },
        "payload": {
            "version": TOOL_ENV_PAYLOAD_VERSION,
            **payload,
        },
    }


def parse_environment_file_payload(data: object) -> dict | None:
    """保存済み環境ファイルのペイロードを検証し、辞書を返す。"""

    if not isinstance(data, dict):
        return None
    if data.get("schema") != ENVIRONMENT_FILE_SCHEMA:
        return None
    if data.get("version") != ENVIRONMENT_FILE_VERSION:
        return None
    return data
