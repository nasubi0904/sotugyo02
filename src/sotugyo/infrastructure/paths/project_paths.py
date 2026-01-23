"""プロジェクト配下の相対パスを扱うユーティリティ。"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

PROJECT_PATH_SCHEME = "project://"

__all__ = [
    "PROJECT_PATH_SCHEME",
    "encode_project_relative_path",
    "is_project_relative_path",
    "normalize_project_relative_path",
    "resolve_project_relative_path",
]


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
