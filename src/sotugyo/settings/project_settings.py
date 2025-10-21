"""プロジェクト単位の設定ファイルを扱うユーティリティ。"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

PROJECT_SETTINGS_FILENAME = "project_settings.json"

__all__ = ["ProjectSettings", "load_project_settings", "save_project_settings"]


def _encode_password(password: str | None) -> str | None:
    if password is None:
        return None
    data = password.encode("utf-8")
    return base64.b64encode(data).decode("ascii")


def _decode_password(payload: str | None) -> str | None:
    if not payload:
        return None
    try:
        return base64.b64decode(payload.encode("ascii")).decode("utf-8")
    except (ValueError, OSError, UnicodeDecodeError):
        return None


@dataclass
class ProjectSettings:
    """プロジェクトごとの設定情報。"""

    project_name: str
    description: str
    project_root: Path
    auto_fill_credentials: bool = True
    last_user_id: Optional[str] = None
    last_user_password: Optional[str] = None

    @property
    def settings_path(self) -> Path:
        return self.project_root / PROJECT_SETTINGS_FILENAME

    def to_payload(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "project_name": self.project_name,
            "description": self.description,
            "auto_fill_credentials": self.auto_fill_credentials,
            "project_root": str(self.project_root),
        }
        if self.last_user_id or self.last_user_password:
            payload["last_user"] = {
                "id": self.last_user_id,
                "password": _encode_password(self.last_user_password),
            }
        return payload

    @classmethod
    def from_payload(cls, root: Path, payload: Dict[str, Any]) -> "ProjectSettings":
        project_name = payload.get("project_name") or root.name
        description = payload.get("description", "")
        auto_fill_credentials = bool(payload.get("auto_fill_credentials", True))
        last_user: Dict[str, Any] = payload.get("last_user") or {}
        last_user_id = last_user.get("id") if isinstance(last_user, dict) else None
        last_user_password = None
        if isinstance(last_user, dict):
            last_user_password = _decode_password(last_user.get("password"))
        return cls(
            project_name=project_name,
            description=description,
            project_root=root,
            auto_fill_credentials=auto_fill_credentials,
            last_user_id=last_user_id,
            last_user_password=last_user_password,
        )


def _default_settings(root: Path) -> ProjectSettings:
    return ProjectSettings(project_name=root.name or "新規プロジェクト", description="", project_root=root)


def load_project_settings(root: Path) -> ProjectSettings:
    """プロジェクト設定を読み込む。"""

    settings_path = root / PROJECT_SETTINGS_FILENAME
    if not settings_path.exists():
        return _default_settings(root)
    try:
        with settings_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return _default_settings(root)
    if not isinstance(payload, dict):
        return _default_settings(root)
    return ProjectSettings.from_payload(root, payload)


def save_project_settings(settings: ProjectSettings) -> None:
    """プロジェクト設定を保存する。"""

    settings_path = settings.settings_path
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    with settings_path.open("w", encoding="utf-8") as handle:
        json.dump(settings.to_payload(), handle, ensure_ascii=False, indent=2)
