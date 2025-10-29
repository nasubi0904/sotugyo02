"""プロジェクト構造検証結果。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

__all__ = ["ProjectStructureReport"]


@dataclass(slots=True)
class ProjectStructureReport:
    """既定構成との差分を保持するレポート。"""

    missing_directories: List[str]
    missing_files: List[str]

    @property
    def is_valid(self) -> bool:
        return not self.missing_directories and not self.missing_files

    def summary(self) -> str:
        messages: List[str] = []
        if self.missing_directories:
            messages.append(
                "未作成のディレクトリ: " + ", ".join(sorted(self.missing_directories))
            )
        if self.missing_files:
            messages.append("未作成のファイル: " + ", ".join(sorted(self.missing_files)))
        return "\n".join(messages) if messages else "既定構成を満たしています。"
