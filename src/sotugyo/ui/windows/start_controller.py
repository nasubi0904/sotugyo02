"""スタートウィンドウ向けのドメイン調停ロジック。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ...domain.projects import ProjectContext, ProjectRecord, ProjectService, ProjectSettings
from ...domain.projects.structure import ProjectStructureReport
from ...domain.users.settings import UserAccount, UserSettingsManager


@dataclass(slots=True)
class StartWindowController:
    """UI 層からの要求をドメインサービスへ振り分ける。"""

    project_service: ProjectService
    user_manager: UserSettingsManager

    @classmethod
    def create_default(cls) -> "StartWindowController":
        return cls(project_service=ProjectService(), user_manager=UserSettingsManager())

    # プロジェクト操作 ---------------------------------------------------
    def project_records(self) -> list[ProjectRecord]:
        return self.project_service.records()

    def register_project(self, record: ProjectRecord, *, set_last: bool = False) -> None:
        self.project_service.register_project(record, set_last=set_last)

    def remove_project(self, root: Path) -> None:
        self.project_service.remove_project(root)

    def last_project_root(self) -> Optional[Path]:
        return self.project_service.last_project_root()

    def set_last_project(self, root: Path) -> None:
        self.project_service.set_last_project(root)

    def load_project_context(self, root: Path) -> ProjectContext:
        return self.project_service.load_context(root)

    def load_project_settings(self, root: Path) -> ProjectSettings:
        return self.project_service.load_settings(root)

    def save_project_settings(
        self,
        settings: ProjectSettings,
        *,
        register: bool = True,
        set_last: bool = False,
    ) -> None:
        self.project_service.save_settings(
            settings,
            register=register,
            set_last=set_last,
        )

    def ensure_structure(self, root: Path) -> ProjectStructureReport:
        return self.project_service.ensure_structure(root)

    def validate_structure(self, root: Path) -> ProjectStructureReport:
        return self.project_service.validate_structure(root)

    # ユーザー操作 -------------------------------------------------------
    def list_accounts(self) -> list[UserAccount]:
        return self.user_manager.list_accounts()

    def get_account(self, user_id: str) -> Optional[UserAccount]:
        return self.user_manager.get_account(user_id)

    def last_user_id(self) -> Optional[str]:
        return self.user_manager.last_user_id()

    def set_last_user_id(self, user_id: Optional[str]) -> None:
        self.user_manager.set_last_user_id(user_id)
