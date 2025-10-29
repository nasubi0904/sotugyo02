"""プロジェクト設定ファイル操作専用のサービス。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .model import ProjectSettings
from .repository import ProjectSettingsRepository


@dataclass(slots=True)
class ProjectSettingsService:
    """設定ファイルの読み書きに責務を限定する。"""

    repository: ProjectSettingsRepository = field(
        default_factory=ProjectSettingsRepository
    )

    def load(self, root: Path) -> ProjectSettings:
        """指定ルートの設定を読み込む。"""

        return self.repository.load(root)

    def save(self, settings: ProjectSettings) -> None:
        """設定を保存する。"""

        self.repository.save(settings)
