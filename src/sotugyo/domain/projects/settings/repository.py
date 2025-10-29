"""プロジェクト設定ファイルの読み書きを担当するリポジトリ。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .model import PROJECT_SETTINGS_FILENAME, ProjectSettings

__all__ = ["ProjectSettingsRepository"]


@dataclass(slots=True)
class ProjectSettingsRepository:
    """設定ファイルを JSON として永続化する。"""

    def load(self, root: Path) -> ProjectSettings:
        settings_path = root / PROJECT_SETTINGS_FILENAME
        if not settings_path.exists():
            return ProjectSettings.default(root)
        try:
            with settings_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return ProjectSettings.default(root)
        if not isinstance(payload, dict):
            return ProjectSettings.default(root)
        return ProjectSettings.from_payload(root, payload)

    def save(self, settings: ProjectSettings) -> None:
        settings_path = settings.settings_path
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        with settings_path.open("w", encoding="utf-8") as handle:
            json.dump(settings.to_payload(), handle, ensure_ascii=False, indent=2)
