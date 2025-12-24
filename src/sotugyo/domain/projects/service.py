"""プロジェクト関連処理のファサードサービス。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .context import ProjectContext
from .pathing import PathInput, ensure_path
from .registry import ProjectRecord, ProjectRegistry, ProjectRegistryService
from .settings import ProjectSettings, ProjectSettingsService
from .structure import ProjectStructureReport, ProjectStructureService

__all__ = ["ProjectService"]


@dataclass(slots=True)
class ProjectService:
    """個別サービスを集約して UI 層へ単一の窓口を提供する。"""

    registry_service: ProjectRegistryService = field(default_factory=lambda: ProjectRegistryService(ProjectRegistry()))
    settings_service: ProjectSettingsService = field(default_factory=ProjectSettingsService)
    structure_service: ProjectStructureService = field(default_factory=ProjectStructureService)

    # レジストリ操作 -----------------------------------------------------
    def records(self) -> list[ProjectRecord]:
        return self.registry_service.records()

    def register_project(self, record: ProjectRecord, *, set_last: bool = False) -> None:
        self.registry_service.register(record, set_last=set_last)

    def remove_project(self, root: PathInput) -> None:
        self.registry_service.remove(ensure_path(root))

    def last_project_root(self) -> Optional[Path]:
        return self.registry_service.last_project()

    def set_last_project(self, root: PathInput) -> None:
        self.registry_service.set_last(ensure_path(root))

    # 設定ファイル操作 ---------------------------------------------------
    def load_settings(self, root: PathInput) -> ProjectSettings:
        path = ensure_path(root)
        return self.settings_service.load(path)

    def load_context(self, root: PathInput) -> ProjectContext:
        path = ensure_path(root)
        settings = self.load_settings(path)
        return ProjectContext(root=path, settings=settings)

    def save_settings(
        self,
        settings: ProjectSettings,
        *,
        register: bool = True,
        set_last: bool = False,
    ) -> None:
        self.settings_service.save(settings)
        if register:
            self.register_project(settings.to_record(), set_last=set_last)

    # 構成チェック -------------------------------------------------------
    def ensure_structure(self, root: PathInput) -> ProjectStructureReport:
        path = ensure_path(root)
        return self.structure_service.ensure(path)

    def validate_structure(self, root: PathInput) -> ProjectStructureReport:
        path = ensure_path(root)
        return self.structure_service.validate(path)
