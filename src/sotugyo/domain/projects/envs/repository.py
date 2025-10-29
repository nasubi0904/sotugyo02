"""プロジェクト内の Rez パッケージ定義を読み書きするリポジトリ。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

SOFTWARE_DIRECTORY_ENV_KEY = "SOFTWARE_DIR"
ISO_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def _utcnow() -> datetime:
    return datetime.utcnow().replace(microsecond=0)


@dataclass(slots=True)
class ProjectRezPackage:
    """プロジェクトに紐づく Rez パッケージ定義。"""

    environment_id: str
    tool_id: str
    rez_packages: Tuple[str, ...] = field(default_factory=tuple)
    rez_variants: Tuple[str, ...] = field(default_factory=tuple)
    rez_environment: Dict[str, str] = field(default_factory=dict)
    updated_at: datetime = field(default_factory=_utcnow)

    def update_from_node(
        self,
        *,
        tool_id: str,
        packages: Tuple[str, ...],
        variants: Tuple[str, ...],
        environment: Dict[str, str],
    ) -> bool:
        """ノード情報との差分を取り込み、変更があれば更新日時を進める。"""

        changed = False
        if self.tool_id != tool_id:
            self.tool_id = tool_id
            changed = True
        if self.rez_packages != packages:
            self.rez_packages = packages
            changed = True
        if self.rez_variants != variants:
            self.rez_variants = variants
            changed = True
        if self.rez_environment != environment:
            self.rez_environment = dict(environment)
            changed = True
        if changed:
            self.touch()
        return changed

    def update_environment_variable(self, key: str, value: str) -> bool:
        """環境変数を設定し、値が変わった場合は更新日時を進める。"""

        current = self.rez_environment.get(key)
        if current == value:
            return False
        self.rez_environment[key] = value
        self.touch()
        return True

    def touch(self) -> None:
        self.updated_at = _utcnow()

    def to_payload(self) -> Dict[str, object]:
        return {
            "environment_id": self.environment_id,
            "tool_id": self.tool_id,
            "rez_packages": list(self.rez_packages),
            "rez_variants": list(self.rez_variants),
            "rez_environment": dict(self.rez_environment),
            "updated_at": self.updated_at.strftime(ISO_FORMAT),
        }

    @classmethod
    def from_payload(cls, payload: Dict[str, object]) -> "ProjectRezPackage":
        environment_id = str(payload.get("environment_id", ""))
        tool_id = str(payload.get("tool_id", ""))
        packages = tuple(
            str(item).strip()
            for item in payload.get("rez_packages", [])
            if isinstance(item, str) and item.strip()
        )
        variants = tuple(
            str(item).strip()
            for item in payload.get("rez_variants", [])
            if isinstance(item, str) and item.strip()
        )
        env_map_raw = payload.get("rez_environment")
        env_map: Dict[str, str] = {}
        if isinstance(env_map_raw, dict):
            env_map = {
                str(key): str(value)
                for key, value in env_map_raw.items()
                if isinstance(key, str) and isinstance(value, (str, int, float))
            }
        updated_raw = payload.get("updated_at")
        updated_at = _utcnow()
        if isinstance(updated_raw, str):
            try:
                updated_at = datetime.strptime(updated_raw, ISO_FORMAT)
            except ValueError:
                updated_at = _utcnow()
        return cls(
            environment_id=environment_id,
            tool_id=tool_id,
            rez_packages=packages,
            rez_variants=variants,
            rez_environment=env_map,
            updated_at=updated_at,
        )


class ProjectRezPackageRepository:
    """プロジェクトディレクトリ内の Rez パッケージを管理する。"""

    DIRECTORY_NAME = "envs"
    FILE_NAME = "rez_packages.json"

    def __init__(self, project_root: Path) -> None:
        self._project_root = Path(project_root)
        self._storage_dir = self._project_root / "config" / self.DIRECTORY_NAME
        self._storage_path = self._storage_dir / self.FILE_NAME

    def load_all(self) -> List[ProjectRezPackage]:
        if not self._storage_path.exists():
            return []
        try:
            with self._storage_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(payload, list):
            return []
        entries = []
        for item in payload:
            if isinstance(item, dict):
                entries.append(ProjectRezPackage.from_payload(item))
        return entries

    def save_all(self, entries: Iterable[ProjectRezPackage]) -> None:
        serialized = [entry.to_payload() for entry in entries]
        serialized.sort(key=lambda item: item.get("environment_id", ""))
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        with self._storage_path.open("w", encoding="utf-8") as handle:
            json.dump(serialized, handle, ensure_ascii=False, indent=2)

    def resolve_storage_path(self) -> Path:
        """保存先ファイルパスを返す。テスト用の補助メソッド。"""

        return self._storage_path
