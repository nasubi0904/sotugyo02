"""プロジェクトディレクトリ構成検証サービス。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .structure import (
    ProjectStructureReport,
    ensure_project_structure,
    validate_project_structure,
)


@dataclass(slots=True)
class ProjectStructureService:
    """構成検証と生成の責務を管理する。"""

    def ensure(self, root: Path) -> ProjectStructureReport:
        """既定構成を満たすよう生成しつつレポートを返す。"""

        return ensure_project_structure(root)

    def validate(self, root: Path) -> ProjectStructureReport:
        """既定構成との差分レポートを返す。"""

        return validate_project_structure(root)
