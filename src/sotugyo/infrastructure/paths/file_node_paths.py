"""ファイルノード参照のパス定義を扱うユーティリティ。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping
import uuid

FILE_NODE_SCHEME = "file-node://"
FILE_NODE_DIR_SCHEME = "file-node-dir://"

__all__ = [
    "FILE_NODE_DIR_SCHEME",
    "FILE_NODE_SCHEME",
    "FileNodePathSpec",
    "encode_file_node_path",
    "encode_structured_file_node_path",
    "parse_file_node_path",
]


@dataclass(frozen=True)
class FileNodePathSpec:
    """ファイルノード参照を表現する。"""

    node_uuid: str
    kind: str

    def is_directory(self) -> bool:
        return self.kind == "directory"


def parse_file_node_path(value: str | Mapping[str, Any]) -> FileNodePathSpec | None:
    """ファイルノード参照の文字列/構造化形式を解析する。"""

    if isinstance(value, Mapping):
        base = str(value.get("base", "")).strip()
        node_uuid = str(value.get("uuid", "")).strip()
        kind = str(value.get("kind", "file")).strip().lower()
        if base != "file_node" or not node_uuid:
            return None
        normalized_uuid = _normalize_uuid(node_uuid)
        if normalized_uuid is None:
            return None
        if kind not in {"file", "directory"}:
            return None
        return FileNodePathSpec(node_uuid=normalized_uuid, kind=kind)

    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    if trimmed.startswith(FILE_NODE_DIR_SCHEME):
        uuid_text = trimmed[len(FILE_NODE_DIR_SCHEME) :].strip()
        normalized_uuid = _normalize_uuid(uuid_text)
        if normalized_uuid is None:
            return None
        return FileNodePathSpec(node_uuid=normalized_uuid, kind="directory")
    if trimmed.startswith(FILE_NODE_SCHEME):
        uuid_text = trimmed[len(FILE_NODE_SCHEME) :].strip()
        normalized_uuid = _normalize_uuid(uuid_text)
        if normalized_uuid is None:
            return None
        return FileNodePathSpec(node_uuid=normalized_uuid, kind="file")
    return None


def encode_file_node_path(node_uuid: str, *, kind: str = "file") -> str:
    """ファイルノード参照の文字列表現を返す。"""

    normalized_uuid = _normalize_uuid(node_uuid)
    if normalized_uuid is None:
        return ""
    scheme = FILE_NODE_DIR_SCHEME if kind == "directory" else FILE_NODE_SCHEME
    return f"{scheme}{normalized_uuid}"


def encode_structured_file_node_path(
    node_uuid: str, *, kind: str = "file"
) -> Mapping[str, str] | None:
    """ファイルノード参照の構造化表現を返す。"""

    normalized_uuid = _normalize_uuid(node_uuid)
    if normalized_uuid is None:
        return None
    if kind not in {"file", "directory"}:
        return None
    return {"base": "file_node", "uuid": normalized_uuid, "kind": kind}


def _normalize_uuid(value: str) -> str | None:
    try:
        normalized = uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        return None
    return str(normalized)
