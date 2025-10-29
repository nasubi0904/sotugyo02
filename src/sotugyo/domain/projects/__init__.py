"""プロジェクトジャンルのドメインモデルとサービス。"""

from __future__ import annotations

from .context import ProjectContext
from .registry import ProjectRecord, ProjectRegistry, ProjectRegistryService
from .service import ProjectService
from .settings import (
    PROJECT_SETTINGS_FILENAME,
    ProjectSettings,
    ProjectSettingsRepository,
    ProjectSettingsService,
)
from .structure import (
    DEFAULT_DIRECTORIES,
    DEFAULT_FILES,
    DEFAULT_FILE_CONTENT,
    ProjectStructureReport,
    ProjectStructureService,
    ensure_structure,
    validate_structure,
)

__all__ = [
    "DEFAULT_DIRECTORIES",
    "DEFAULT_FILES",
    "DEFAULT_FILE_CONTENT",
    "PROJECT_SETTINGS_FILENAME",
    "ProjectContext",
    "ProjectRecord",
    "ProjectRegistry",
    "ProjectRegistryService",
    "ProjectService",
    "ProjectSettings",
    "ProjectSettingsRepository",
    "ProjectSettingsService",
    "ProjectStructureReport",
    "ProjectStructureService",
    "ensure_structure",
    "validate_structure",
]
