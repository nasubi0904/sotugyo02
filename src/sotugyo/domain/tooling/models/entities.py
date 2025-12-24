"""ツール登録と環境定義のデータモデル。"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar, Dict, Iterable, Optional, Tuple

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


def _normalize_key(values: Iterable[str]) -> Tuple[str, ...]:
    entries = [
        entry.strip()
        for entry in values
        if isinstance(entry, str) and entry.strip()
    ]
    return tuple(sorted(set(entries)))


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

    rez_packages: Tuple[str, ...] = field(default_factory=tuple)
    rez_variants: Tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rez_packages": list(self.rez_packages),
            "rez_variants": list(self.rez_variants),
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
        return cls(
            rez_packages=packages,
            rez_variants=variants,
        )

    def package_key(self) -> Tuple[str, ...]:
        return _normalize_key(self.rez_packages)

    def variant_key(self) -> Tuple[str, ...]:
        return _normalize_key(self.rez_variants)

    def package_key_label(self) -> str:
        payload = {
            "packages": list(self.package_key()),
            "variants": list(self.variant_key()),
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)

    def display_label(self) -> str:
        packages = " ".join(self.package_key())
        variants = ", ".join(self.variant_key())
        if variants:
            return f"{packages} [{variants}]"
        return packages or "Rez 環境"


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
