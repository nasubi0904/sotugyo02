"""ツール環境定義のパス表現ユーティリティ。"""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional

TOOL_ENVIRONMENT_METADATA_KEY = "tool_environment_payload"
TOOL_ENVIRONMENT_SCHEMA_VERSION = 1
NODE_INPUT_PATH_KIND_DIRECTORY = "directory"
TOKEN_TYPE_TEXT = "text"
TOKEN_TYPE_NODE_INPUT = "node_input"
NODE_INPUT_PLACEHOLDER_PATTERN = re.compile(r"\{\{node:([^{}]+)\}\}")


def normalize_node_input_name(name: str) -> Optional[str]:
    normalized = name.strip()
    if not normalized:
        return None
    if "\n" in normalized or "\r" in normalized:
        return None
    if "{" in normalized or "}" in normalized:
        return None
    return normalized


def build_node_input_placeholder(name: str) -> str:
    return f"{{{{node:{name}}}}}"


def tokenize_text(text: str) -> List[Dict[str, str]]:
    tokens: List[Dict[str, str]] = []
    if not text:
        return tokens
    position = 0
    for match in NODE_INPUT_PLACEHOLDER_PATTERN.finditer(text):
        start, end = match.span()
        if start > position:
            tokens.append({"type": TOKEN_TYPE_TEXT, "value": text[position:start]})
        name = normalize_node_input_name(match.group(1))
        if name:
            tokens.append(
                {
                    "type": TOKEN_TYPE_NODE_INPUT,
                    "name": name,
                    "path_kind": NODE_INPUT_PATH_KIND_DIRECTORY,
                }
            )
        else:
            tokens.append({"type": TOKEN_TYPE_TEXT, "value": match.group(0)})
        position = end
    if position < len(text):
        tokens.append({"type": TOKEN_TYPE_TEXT, "value": text[position:]})
    return tokens


def collect_node_input_names(tokens: Iterable[Dict[str, str]]) -> List[str]:
    names: List[str] = []
    for token in tokens:
        if not isinstance(token, dict):
            continue
        if token.get("type") != TOKEN_TYPE_NODE_INPUT:
            continue
        name = token.get("name")
        if isinstance(name, str):
            normalized = normalize_node_input_name(name)
            if normalized and normalized not in names:
                names.append(normalized)
    return names


def normalize_text_payload(value: object) -> Dict[str, object]:
    if isinstance(value, dict):
        raw = value.get("raw")
        raw_text = raw if isinstance(raw, str) else ""
    elif isinstance(value, str):
        raw_text = value
    else:
        raw_text = ""
    return {"raw": raw_text, "tokens": tokenize_text(raw_text)}


def normalize_node_inputs(value: object) -> List[Dict[str, str]]:
    if not isinstance(value, list):
        return []
    normalized: List[Dict[str, str]] = []
    seen: set[str] = set()
    for entry in value:
        name = None
        if isinstance(entry, dict):
            raw_name = entry.get("name")
            if isinstance(raw_name, str):
                name = normalize_node_input_name(raw_name)
        elif isinstance(entry, str):
            name = normalize_node_input_name(entry)
        if not name or name in seen:
            continue
        seen.add(name)
        normalized.append(
            {"name": name, "path_kind": NODE_INPUT_PATH_KIND_DIRECTORY}
        )
    return normalized


def merge_node_inputs(
    base_inputs: Iterable[Dict[str, str]],
    extra_names: Iterable[str],
) -> List[Dict[str, str]]:
    merged: List[Dict[str, str]] = []
    seen: set[str] = set()
    for entry in base_inputs:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if not isinstance(name, str):
            continue
        normalized = normalize_node_input_name(name)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        merged.append(
            {"name": normalized, "path_kind": NODE_INPUT_PATH_KIND_DIRECTORY}
        )
    for name in extra_names:
        normalized = normalize_node_input_name(name)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        merged.append(
            {"name": normalized, "path_kind": NODE_INPUT_PATH_KIND_DIRECTORY}
        )
    return merged


def normalize_relative_path(relative: str) -> Optional[str]:
    normalized = relative.replace("\\", "/").strip()
    if not normalized:
        return None
    if normalized.startswith(("/", "\\")):
        return None
    if ":" in normalized:
        return None
    parts = [part for part in normalized.split("/") if part]
    if any(part == ".." for part in parts):
        return None
    return "/".join(parts)


def normalize_required_plugins(value: object) -> List[Dict[str, str]]:
    if not isinstance(value, list):
        return []
    normalized: List[Dict[str, str]] = []
    for entry in value:
        if not isinstance(entry, dict):
            continue
        path_type = entry.get("path_type")
        name = entry.get("name")
        if isinstance(name, str):
            safe_name = name.strip()
        else:
            safe_name = ""
        if path_type == "absolute":
            raw_path = entry.get("path")
            if not isinstance(raw_path, str) or not raw_path.strip():
                continue
            normalized.append(
                {
                    "name": safe_name or raw_path,
                    "path_type": "absolute",
                    "path": raw_path,
                }
            )
        elif path_type == "known":
            known_id = entry.get("known_id")
            relative_path = entry.get("relative_path")
            if not isinstance(known_id, str) or not isinstance(relative_path, str):
                continue
            normalized_relative = normalize_relative_path(relative_path)
            if normalized_relative is None:
                continue
            normalized.append(
                {
                    "name": safe_name or normalized_relative,
                    "path_type": "known",
                    "known_id": known_id,
                    "relative_path": normalized_relative,
                }
            )
        elif path_type == "package":
            package = entry.get("package")
            relative_path = entry.get("relative_path")
            if not isinstance(package, str) or not isinstance(relative_path, str):
                continue
            normalized_relative = normalize_relative_path(relative_path)
            if normalized_relative is None:
                continue
            normalized.append(
                {
                    "name": safe_name or normalized_relative,
                    "path_type": "package",
                    "package": package,
                    "relative_path": normalized_relative,
                }
            )
        elif path_type == "tool":
            relative_path = entry.get("relative_path")
            if not isinstance(relative_path, str):
                continue
            normalized_relative = normalize_relative_path(relative_path)
            if normalized_relative is None:
                continue
            normalized.append(
                {
                    "name": safe_name or normalized_relative,
                    "path_type": "tool",
                    "relative_path": normalized_relative,
                }
            )
        elif path_type == "node":
            input_name = entry.get("input_name")
            if not isinstance(input_name, str):
                continue
            normalized_name = normalize_node_input_name(input_name)
            if normalized_name is None:
                continue
            normalized.append(
                {
                    "name": safe_name or normalized_name,
                    "path_type": "node",
                    "input_name": normalized_name,
                    "path_kind": NODE_INPUT_PATH_KIND_DIRECTORY,
                }
            )
    return normalized
