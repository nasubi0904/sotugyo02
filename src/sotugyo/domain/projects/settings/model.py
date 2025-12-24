"""プロジェクト設定モデル。"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

PROJECT_SETTINGS_FILENAME = "project_settings.json"

__all__ = ["ProjectSettings", "PROJECT_SETTINGS_FILENAME"]


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


@dataclass(slots=True)
class ProjectSettings:
    """プロジェクトごとの設定情報。"""

    project_name: str
    description: str
    project_root: Path
    auto_fill_user_id: bool = True
    auto_fill_password: bool = False
    last_user_id: Optional[str] = None
    last_user_password: Optional[str] = None

    def to_record(self) -> "ProjectRecord":
        """レジストリへ登録可能なレコードへ変換する。"""

        from ..registry import ProjectRecord

        return ProjectRecord(name=self.project_name, root=self.project_root)

    @property
    def settings_path(self) -> Path:
        return self.project_root / PROJECT_SETTINGS_FILENAME

    def to_payload(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "project_name": self.project_name,
            "description": self.description,
            "auto_fill_user_id": self.auto_fill_user_id,
            "auto_fill_password": self.auto_fill_password,
            "project_root": str(self.project_root),
        }
        payload["auto_fill_credentials"] = self.auto_fill_user_id and self.auto_fill_password
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
        raw_auto_fill_user_id = payload.get("auto_fill_user_id")
        if raw_auto_fill_user_id is None:
            raw_auto_fill_user_id = payload.get("auto_fill_credentials", True)
        auto_fill_user_id = bool(raw_auto_fill_user_id)
        raw_auto_fill_password = payload.get("auto_fill_password")
        if raw_auto_fill_password is None:
            raw_auto_fill_password = payload.get("auto_fill_credentials", False)
        auto_fill_password = bool(raw_auto_fill_password)
        last_user: Dict[str, Any] = payload.get("last_user") or {}
        last_user_id = last_user.get("id") if isinstance(last_user, dict) else None
        last_user_password = None
        if isinstance(last_user, dict):
            last_user_password = _decode_password(last_user.get("password"))
        return cls(
            project_name=project_name,
            description=description,
            project_root=root,
            auto_fill_user_id=auto_fill_user_id,
            auto_fill_password=auto_fill_password,
            last_user_id=last_user_id,
            last_user_password=last_user_password,
        )

    @classmethod
    def default(cls, root: Path) -> "ProjectSettings":
        """ルートディレクトリから既定値を生成する。"""

        return cls(
            project_name=root.name or "新規プロジェクト",
            description="",
            project_root=root,
        )
