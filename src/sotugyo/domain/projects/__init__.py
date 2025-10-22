"""プロジェクトジャンルのドメインモデルとサービス。"""

from __future__ import annotations

from .registry import ProjectRecord, ProjectRegistry
from .service import ProjectContext, ProjectService
from .settings import ProjectSettings, load_project_settings, save_project_settings
from .structure import (
    DEFAULT_DIRECTORIES,
    DEFAULT_FILES,
    ProjectStructureReport,
    ensure_project_structure,
    validate_project_structure,
)

__all__ = [
    "DEFAULT_DIRECTORIES",
    "DEFAULT_FILES",
    "ProjectContext",
    "ProjectRecord",
    "ProjectRegistry",
    "ProjectService",
    "ProjectSettings",
    "ProjectStructureReport",
    "ensure_project_structure",
    "load_project_settings",
    "save_project_settings",
    "validate_project_structure",
]
