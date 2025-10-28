"""プロジェクトジャンルのドメインモデルとサービス。"""

from __future__ import annotations

from .context import ProjectContext
from .registry import ProjectRecord, ProjectRegistry
from .registry_service import ProjectRegistryService
from .service import ProjectService
from .settings import ProjectSettings, load_project_settings, save_project_settings
from .settings_service import ProjectSettingsService
from .structure import (
    DEFAULT_DIRECTORIES,
    DEFAULT_FILES,
    ProjectStructureReport,
    ensure_project_structure,
    validate_project_structure,
)
from .structure_service import ProjectStructureService

__all__ = [
    "DEFAULT_DIRECTORIES",
    "DEFAULT_FILES",
    "ProjectContext",
    "ProjectRecord",
    "ProjectRegistry",
    "ProjectRegistryService",
    "ProjectService",
    "ProjectSettings",
    "ProjectSettingsService",
    "ProjectStructureReport",
    "ProjectStructureService",
    "ensure_project_structure",
    "load_project_settings",
    "save_project_settings",
    "validate_project_structure",
]
