"""プロジェクト配下の相対パスを扱うユーティリティ。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

PROJECT_PATH_SCHEME = "project://"

__all__ = [
    "PROJECT_PATH_SCHEME",
    "ProjectPathSpec",
    "encode_project_relative_path",
    "encode_structured_absolute_path",
    "encode_structured_project_path",
    "is_project_relative_path",
    "normalize_project_relative_path",
    "parse_project_path",
    "resolve_project_relative_path",
    "safe_basename",
]


@dataclass(frozen=True)
class ProjectPathSpec:
    """プロジェクト内外のパス定義を保持する。"""

    base: str
    path: str

    def is_project(self) -> bool:
        return self.base == "project"

    def is_absolute(self) -> bool:
        return self.base == "absolute"


def normalize_project_relative_path(raw_path: str) -> str:
    """プロジェクト配下の相対パスとして扱える文字列へ正規化する。"""

    if not raw_path:
        return ""
    trimmed = raw_path.strip()
    if trimmed.startswith(PROJECT_PATH_SCHEME):
        trimmed = trimmed[len(PROJECT_PATH_SCHEME) :]
    if not trimmed:
        return ""
    normalized = trimmed.replace("\\", "/")
    posix_path = PurePosixPath(normalized)
    if posix_path.is_absolute():
        return ""
    if posix_path.parts and posix_path.parts[0].endswith(":"):
        return ""
    if any(part == ".." for part in posix_path.parts):
        return ""
    cleaned = posix_path.as_posix()
    if cleaned in ("", "."):
        return ""
    return cleaned


def parse_project_path(value: str | Mapping[str, Any]) -> ProjectPathSpec | None:
    """文字列または構造化パスから ProjectPathSpec を返す。"""

    if isinstance(value, Mapping):
        base = str(value.get("base", "")).strip()
        path_value = str(value.get("path", "")).strip()
        if not base or not path_value:
            return None
        if base == "project":
            normalized = normalize_project_relative_path(path_value)
            if not normalized:
                return None
            return ProjectPathSpec(base="project", path=normalized)
        if base == "absolute":
            return ProjectPathSpec(base="absolute", path=path_value)
        return None

    if not isinstance(value, str):
        return None
    normalized = normalize_project_relative_path(value)
    if not normalized:
        return None
    return ProjectPathSpec(base="project", path=normalized)


def resolve_project_relative_path(project_root: Path, raw_path: str) -> Path | None:
    """プロジェクト相対パスを実パスへ解決する。"""

    normalized = normalize_project_relative_path(raw_path)
    if not normalized:
        return None
    root = project_root.resolve(strict=False)
    target = (root / normalized).resolve(strict=False)
    try:
        target.relative_to(root)
    except ValueError:
        return None
    return target


def is_project_relative_path(project_root: Path, raw_path: str) -> bool:
    """プロジェクト配下の相対パスかを判定する。"""

    return resolve_project_relative_path(project_root, raw_path) is not None


def encode_project_relative_path(project_root: Path, path: Path) -> str:
    """プロジェクト相対パスを project:// 形式で返す。"""

    root = project_root.resolve(strict=False)
    try:
        relative = path.resolve(strict=False).relative_to(root)
    except ValueError:
        return ""
    return f"{PROJECT_PATH_SCHEME}{relative.as_posix()}"


def encode_structured_project_path(project_root: Path, path: Path) -> Mapping[str, str] | None:
    """プロジェクト相対パスの構造化表現を返す。"""

    root = project_root.resolve(strict=False)
    try:
        relative = path.resolve(strict=False).relative_to(root)
    except ValueError:
        return None
    return {"base": "project", "path": relative.as_posix()}


def encode_structured_absolute_path(path: Path) -> Mapping[str, str]:
    """絶対パスの構造化表現を返す。"""

    return {"base": "absolute", "path": str(path)}


def safe_basename(raw_path: str) -> str:
    """パス文字列の末尾要素を安全に取得する。"""

    if not raw_path:
        return ""
    cleaned = raw_path.strip()
    if cleaned.startswith(PROJECT_PATH_SCHEME):
        cleaned = cleaned[len(PROJECT_PATH_SCHEME) :]
    parts = [part for part in cleaned.replace("\\", "/").split("/") if part]
    if not parts:
        return ""
    return parts[-1]
