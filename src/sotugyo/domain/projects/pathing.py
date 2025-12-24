"""プロジェクトルートの正規化ユーティリティ。"""

from __future__ import annotations

from os import PathLike
from pathlib import Path
from typing import Union

PathInput = Union[Path, str, PathLike[str]]

__all__ = ["PathInput", "ensure_path"]


def ensure_path(value: PathInput) -> Path:
    """パス入力を ``Path`` へ変換する。"""

    if isinstance(value, Path):
        return value
    return Path(value)
