"""プロジェクトディレクトリ構成検証サービス。"""

from __future__ import annotations

from dataclasses import dataclass
from ..pathing import PathInput, ensure_path
from .operations import ensure_structure, validate_structure
from .report import ProjectStructureReport


@dataclass(slots=True)
class ProjectStructureService:
    """構成検証と生成の責務を管理する。"""

    def ensure(self, root: PathInput) -> ProjectStructureReport:
        """既定構成を満たすよう生成しつつレポートを返す。"""

        return ensure_structure(ensure_path(root))

    def validate(self, root: PathInput) -> ProjectStructureReport:
        """既定構成との差分レポートを返す。"""

        return validate_structure(ensure_path(root))
