"""プロジェクト設定ファイル操作専用のサービス。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .settings import ProjectSettings, load_project_settings, save_project_settings


@dataclass(slots=True)
class ProjectSettingsService:
    """設定ファイルの読み書きに責務を限定する。"""

    def load(self, root: Path) -> ProjectSettings:
        """指定ルートの設定を読み込む。"""

        return load_project_settings(root)

    def save(self, settings: ProjectSettings) -> None:
        """設定を保存する。"""

        save_project_settings(settings)
