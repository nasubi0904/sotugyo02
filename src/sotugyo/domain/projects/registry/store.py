"""プロジェクト一覧を管理するレジストリ。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from ....infrastructure.paths import get_app_config_dir
from .models import ProjectRecord

REGISTRY_FILENAME = "projects.json"

__all__ = ["ProjectRegistry"]


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
        index = self._find_record_index(record.root)
        if index is None:
            self._records.append(record)
        else:
            self._records[index] = record
        self._persist()

    def remove_project(self, root: Path) -> None:
        self._records = [record for record in self._records if record.root != root]
        self._clear_last_project_if_matches(root)
        self._persist()

    # 内部処理 ----------------------------------------------------------
    def _load(self) -> None:
        payload = self._load_payload()
        if not payload:
            return
        self._records = self._parse_records(payload.get("records"))
        self._last_project = self._parse_last_project(payload.get("last_project"))

    def _persist(self) -> None:
        self._config_dir.mkdir(parents=True, exist_ok=True)
        payload = self._build_payload()
        with self._registry_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)

    def _find_record_index(self, root: Path) -> Optional[int]:
        for index, record in enumerate(self._records):
            if record.root == root:
                return index
        return None

    def _clear_last_project_if_matches(self, root: Path) -> None:
        if self._last_project == root:
            self._last_project = None

    def _load_payload(self) -> Optional[dict]:
        if not self._registry_path.exists():
            return None
        try:
            with self._registry_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        return payload

    @staticmethod
    def _parse_records(records_payload: object) -> List[ProjectRecord]:
        if not isinstance(records_payload, list):
            return []
        records: List[ProjectRecord] = []
        for item in records_payload:
            if isinstance(item, dict):
                records.append(ProjectRecord.from_payload(item))
        return records

    @staticmethod
    def _parse_last_project(last_project: object) -> Optional[Path]:
        if isinstance(last_project, str) and last_project:
            return Path(last_project)
        return None

    def _build_payload(self) -> dict:
        return {
            "records": [record.to_payload() for record in self._records],
            "last_project": str(self._last_project) if self._last_project else None,
        }
