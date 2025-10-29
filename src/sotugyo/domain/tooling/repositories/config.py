"""ツールおよび環境定義の永続化レイヤー。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List, Tuple

from ....infrastructure.paths.storage import get_machine_config_dir
from ..models import RegisteredTool, ToolEnvironmentDefinition

DEFAULT_DATA = {"version": 1, "tools": [], "environments": []}


class ToolConfigRepository:
    """マシン依存の設定ファイルからツール情報を読み書きする。"""

    FILE_NAME = "tooling_registry.json"

    def __init__(self, storage_dir: Path | None = None) -> None:
        base_dir = storage_dir or get_machine_config_dir()
        self._storage_dir = Path(base_dir)
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._storage_path = self._storage_dir / self.FILE_NAME

    # ------------------------------------------------------------------
    # 読み書き
    # ------------------------------------------------------------------
    def load_all(self) -> Tuple[List[RegisteredTool], List[ToolEnvironmentDefinition]]:
        data = self._read_raw()
        tool_entries = data.get("tools", [])
        env_entries = data.get("environments", [])
        tools = [
            RegisteredTool.from_dict(entry)
            for entry in tool_entries
            if isinstance(entry, dict)
        ]
        environments = [
            ToolEnvironmentDefinition.from_dict(entry)
            for entry in env_entries
            if isinstance(entry, dict)
        ]
        return tools, environments

    def save_all(
        self,
        tools: Iterable[RegisteredTool],
        environments: Iterable[ToolEnvironmentDefinition],
    ) -> None:
        data = {
            "version": DEFAULT_DATA["version"],
            "tools": [tool.to_dict() for tool in tools],
            "environments": [env.to_dict() for env in environments],
        }
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        with self._storage_path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------
    # 内部ユーティリティ
    # ------------------------------------------------------------------
    def _read_raw(self) -> dict:
        if not self._storage_path.exists():
            return dict(DEFAULT_DATA)
        try:
            with self._storage_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return dict(DEFAULT_DATA)
        if not isinstance(data, dict):
            return dict(DEFAULT_DATA)
        return data
