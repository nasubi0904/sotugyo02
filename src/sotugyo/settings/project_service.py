"""プロジェクト関連の操作をまとめたサービス。"""

from __future__ import annotations

from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import Optional, Union

from .project_registry import ProjectRecord, ProjectRegistry
from .project_settings import ProjectSettings, load_project_settings, save_project_settings
from .project_structure import (
    ProjectStructureReport,
    ensure_project_structure,
    validate_project_structure,
)

__all__ = ["ProjectContext", "ProjectService"]


@dataclass
class ProjectContext:
    """プロジェクトルートと設定情報の組み合わせ。"""

    root: Path
    settings: ProjectSettings

    @property
    def record(self) -> ProjectRecord:
        """設定からレジストリ登録用のレコードを生成する。"""

        return ProjectRecord(name=self.settings.project_name, root=self.root)


PathInput = Union[Path, str, PathLike[str]]


class ProjectService:
    """プロジェクト設定やレジストリ操作を一元管理するサービス。"""

    def __init__(self, registry: Optional[ProjectRegistry] = None) -> None:
        self._registry = registry or ProjectRegistry()

    # レジストリ操作 -----------------------------------------------------
    def records(self) -> list[ProjectRecord]:
        """現在登録されているプロジェクトレコード一覧を返す。"""

        return self._registry.records()

    def register_project(self, record: ProjectRecord, *, set_last: bool = False) -> None:
        """プロジェクトを登録し、必要に応じて最終選択を更新する。"""

        self._registry.register_project(record)
        if set_last:
            self._registry.set_last_project(record.root)

    def remove_project(self, root: PathInput) -> None:
        """指定ルートのプロジェクト登録を解除する。"""

        self._registry.remove_project(self._ensure_path(root))

    def last_project_root(self) -> Optional[Path]:
        """最後に選択されたプロジェクトルートを返す。"""

        return self._registry.last_project()

    def set_last_project(self, root: PathInput) -> None:
        """最後に選択したプロジェクトルートを更新する。"""

        self._registry.set_last_project(self._ensure_path(root))

    # 設定ファイル操作 ---------------------------------------------------
    def load_settings(self, root: PathInput) -> ProjectSettings:
        """指定ルートの設定を読み込む。"""

        path = self._ensure_path(root)
        return load_project_settings(path)

    def load_context(self, root: PathInput) -> ProjectContext:
        """プロジェクトコンテキストを生成する。"""

        path = self._ensure_path(root)
        settings = self.load_settings(path)
        return ProjectContext(root=path, settings=settings)

    def save_settings(
        self,
        settings: ProjectSettings,
        *,
        register: bool = True,
        set_last: bool = False,
    ) -> None:
        """設定を保存し、必要に応じてレジストリを更新する。"""

        save_project_settings(settings)
        if register:
            self.register_project(_settings_to_record(settings), set_last=set_last)

    # 構成チェック -------------------------------------------------------
    def ensure_structure(self, root: PathInput) -> ProjectStructureReport:
        """既定構成を満たすように生成しつつレポートを返す。"""

        path = self._ensure_path(root)
        return ensure_project_structure(path)

    def validate_structure(self, root: PathInput) -> ProjectStructureReport:
        """既定構成との差分レポートを返す。"""

        path = self._ensure_path(root)
        return validate_project_structure(path)

    @staticmethod
    def _ensure_path(value: PathInput) -> Path:
        if isinstance(value, Path):
            return value
        return Path(value)


def _settings_to_record(settings: ProjectSettings) -> ProjectRecord:
    """`ProjectSettings` から `ProjectRecord` を生成する補助関数。"""

    return ProjectRecord(name=settings.project_name, root=settings.project_root)
