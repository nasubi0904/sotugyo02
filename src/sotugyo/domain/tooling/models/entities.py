"""ツール登録と環境定義のデータモデル。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar, Dict, Optional

ISO_FORMAT: ClassVar[str] = "%Y-%m-%dT%H:%M:%S"


def _parse_timestamp(value: str | None) -> datetime:
    if not value:
        return datetime.fromtimestamp(0)
    try:
        return datetime.strptime(value, ISO_FORMAT)
    except ValueError:
        return datetime.fromtimestamp(0)


def _format_timestamp(value: datetime | None) -> str:
    if value is None:
        value = datetime.utcnow()
    return value.strftime(ISO_FORMAT)


@dataclass(slots=True)
class RegisteredTool:
    """マシンに登録された実行可能ツール。"""

    tool_id: str
    display_name: str
    executable_path: Path
    template_id: Optional[str] = None
    version: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_id": self.tool_id,
            "display_name": self.display_name,
            "executable_path": str(self.executable_path),
            "template_id": self.template_id,
            "version": self.version,
            "created_at": _format_timestamp(self.created_at),
            "updated_at": _format_timestamp(self.updated_at),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RegisteredTool":
        return cls(
            tool_id=str(data.get("tool_id", "")),
            display_name=str(data.get("display_name", "")),
            executable_path=Path(str(data.get("executable_path", ""))),
            template_id=data.get("template_id") or None,
            version=data.get("version") or None,
            created_at=_parse_timestamp(data.get("created_at")),
            updated_at=_parse_timestamp(data.get("updated_at")),
        )


@dataclass(slots=True)
class ToolEnvironmentDefinition:
    """ツールを利用した環境ノードの定義。"""

    environment_id: str
    name: str
    tool_id: str
    version_label: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "environment_id": self.environment_id,
            "name": self.name,
            "tool_id": self.tool_id,
            "version_label": self.version_label,
            "created_at": _format_timestamp(self.created_at),
            "updated_at": _format_timestamp(self.updated_at),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolEnvironmentDefinition":
        return cls(
            environment_id=str(data.get("environment_id", "")),
            name=str(data.get("name", "")),
            tool_id=str(data.get("tool_id", "")),
            version_label=str(data.get("version_label", "")),
            created_at=_parse_timestamp(data.get("created_at")),
            updated_at=_parse_timestamp(data.get("updated_at")),
        )


@dataclass(slots=True)
class TemplateInstallationCandidate:
    """テンプレートから発見されたインストール候補。"""

    template_id: str
    display_name: str
    executable_path: Path
    version: Optional[str] = None

    def to_entry(self) -> Dict[str, Any]:
        return {
            "template_id": self.template_id,
            "display_name": self.display_name,
            "executable_path": str(self.executable_path),
            "version": self.version,
        }
