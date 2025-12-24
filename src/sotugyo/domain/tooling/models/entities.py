"""ツール登録と環境定義のデータモデル。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar, Dict, Optional, Tuple

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
    template_id: Optional[str] = None
    rez_packages: Tuple[str, ...] = field(default_factory=tuple)
    rez_variants: Tuple[str, ...] = field(default_factory=tuple)
    rez_environment: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "environment_id": self.environment_id,
            "name": self.name,
            "tool_id": self.tool_id,
            "version_label": self.version_label,
            "template_id": self.template_id,
            "rez_packages": list(self.rez_packages),
            "rez_variants": list(self.rez_variants),
            "rez_environment": dict(self.rez_environment),
            "metadata": dict(self.metadata),
            "created_at": _format_timestamp(self.created_at),
            "updated_at": _format_timestamp(self.updated_at),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolEnvironmentDefinition":
        packages = tuple(
            str(entry).strip()
            for entry in data.get("rez_packages", [])
            if isinstance(entry, str) and entry.strip()
        )
        variants = tuple(
            str(entry).strip()
            for entry in data.get("rez_variants", [])
            if isinstance(entry, str) and entry.strip()
        )
        env_map = {}
        raw_env = data.get("rez_environment")
        if isinstance(raw_env, dict):
            env_map = {
                str(key): str(value)
                for key, value in raw_env.items()
                if isinstance(key, str) and isinstance(value, str)
            }
        metadata = {}
        raw_metadata = data.get("metadata")
        if isinstance(raw_metadata, dict):
            metadata = dict(raw_metadata)
        return cls(
            environment_id=str(data.get("environment_id", "")),
            name=str(data.get("name", "")),
            tool_id=str(data.get("tool_id", "")),
            version_label=str(data.get("version_label", "")),
            template_id=(
                str(data.get("template_id")) if data.get("template_id") is not None else None
            ),
            rez_packages=packages,
            rez_variants=variants,
            rez_environment=env_map,
            metadata=metadata,
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


@dataclass(slots=True, frozen=True)
class RezPackageSpec:
    """Rez パッケージの位置とバージョン情報を表す。"""

    name: str
    version: str | None
    path: Path
