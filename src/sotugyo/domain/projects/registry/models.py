"""プロジェクトレジストリ用の値オブジェクト。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict

__all__ = ["ProjectRecord"]


@dataclass(slots=True)
class ProjectRecord:
    """プロジェクトの表示名とルートディレクトリを保持する。"""

    name: str
    root: Path

    def to_payload(self) -> Dict[str, str]:
        """JSON 永続化用の辞書へ変換する。"""

        return {"name": self.name, "root": str(self.root)}

    @classmethod
    def from_payload(cls, payload: Dict[str, str]) -> "ProjectRecord":
        """辞書データから値オブジェクトを復元する。"""

        return cls(name=payload.get("name", ""), root=Path(payload.get("root", "")))
