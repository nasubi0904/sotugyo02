"""プロジェクトコンテキスト定義。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .settings import ProjectSettings
from .registry import ProjectRecord


@dataclass(slots=True)
class ProjectContext:
    """プロジェクトルートと設定情報の組み合わせを表現する。"""

    root: Path
    settings: ProjectSettings

    @property
    def record(self) -> ProjectRecord:
        """設定を基にレジストリ登録用レコードを生成する。"""

        return ProjectRecord(name=self.settings.project_name, root=self.root)
