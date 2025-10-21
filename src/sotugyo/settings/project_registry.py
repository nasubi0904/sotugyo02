"""プロジェクト一覧を管理するレジストリ。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .storage_paths import get_app_config_dir

REGISTRY_FILENAME = "projects.json"

__all__ = ["ProjectRecord", "ProjectRegistry"]


@dataclass
class ProjectRecord:
    name: str
    root: Path

    def to_payload(self) -> Dict[str, str]:
        return {"name": self.name, "root": str(self.root)}

    @classmethod
    def from_payload(cls, payload: Dict[str, str]) -> "ProjectRecord":
        return cls(name=payload.get("name", ""), root=Path(payload.get("root", "")))


class ProjectRegistry:
    """プロジェクトの一覧と最終選択状態を保持する。"""

    def __init__(self) -> None:
        self._config_dir = get_app_config_dir()
        self._registry_path = self._config_dir / REGISTRY_FILENAME
        self._records: List[ProjectRecord] = []
        self._last_project: Optional[Path] = None
        self._load()

    # 公開 API ----------------------------------------------------------
    def records(self) -> List[ProjectRecord]:
        return list(self._records)

    def last_project(self) -> Optional[Path]:
        return self._last_project

    def set_last_project(self, root: Path) -> None:
        self._last_project = root
        self._persist()

    def register_project(self, record: ProjectRecord) -> None:
        for existing in self._records:
            if existing.root == record.root:
                existing.name = record.name
                break
        else:
            self._records.append(record)
        self._persist()

    def remove_project(self, root: Path) -> None:
        self._records = [record for record in self._records if record.root != root]
        if self._last_project == root:
            self._last_project = None
        self._persist()

    # 内部処理 ----------------------------------------------------------
    def _load(self) -> None:
        if not self._registry_path.exists():
            return
        try:
            with self._registry_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(payload, dict):
            return
        records_payload = payload.get("records")
        if isinstance(records_payload, list):
            self._records = [
                ProjectRecord.from_payload(item)
                for item in records_payload
                if isinstance(item, dict)
            ]
        last_project = payload.get("last_project")
        if isinstance(last_project, str) and last_project:
            self._last_project = Path(last_project)

    def _persist(self) -> None:
        self._config_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "records": [record.to_payload() for record in self._records],
            "last_project": str(self._last_project) if self._last_project else None,
        }
        with self._registry_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
