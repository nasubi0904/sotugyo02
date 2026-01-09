"""ツールおよび環境定義の永続化レイヤー。"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Iterable, List, Tuple

from ....infrastructure.paths.storage import get_machine_config_dir
from ..models import RegisteredTool, ToolEnvironmentDefinition

LOGGER = logging.getLogger(__name__)


class ToolConfigRepository:
    """マシン依存の設定ファイルからツール情報を読み書きする。"""

    def __init__(self, config_path: Path | None = None) -> None:
        config_dir = get_machine_config_dir()
        self._config_path = (
            Path(config_path) if config_path is not None else config_dir / "tool_registry.json"
        )
        self._tools: List[RegisteredTool] = []
        self._environments: List[ToolEnvironmentDefinition] = []

    # ------------------------------------------------------------------
    # 読み書き
    # ------------------------------------------------------------------
    def load_all(self) -> Tuple[List[RegisteredTool], List[ToolEnvironmentDefinition]]:
        payload = self._read_payload()
        tools = [
            RegisteredTool.from_dict(entry)
            for entry in payload.get("tools", [])
            if isinstance(entry, dict)
        ]
        environments = [
            ToolEnvironmentDefinition.from_dict(entry)
            for entry in payload.get("environments", [])
            if isinstance(entry, dict)
        ]
        self._tools = tools
        self._environments = environments
        return list(self._tools), list(self._environments)

    def save_all(
        self,
        tools: Iterable[RegisteredTool],
        environments: Iterable[ToolEnvironmentDefinition],
    ) -> None:
        tool_list = list(tools)
        env_list = list(environments)
        payload = {
            "version": 1,
            "tools": [tool.to_dict() for tool in tool_list],
            "environments": [environment.to_dict() for environment in env_list],
        }
        self._write_payload(payload)
        self._tools = tool_list
        self._environments = env_list

    def _read_payload(self) -> dict:
        if not self._config_path.exists():
            return {}
        try:
            content = self._config_path.read_text(encoding="utf-8")
        except OSError as exc:
            LOGGER.warning(
                "ツール設定ファイルの読み込みに失敗しました: %s",
                self._config_path,
                exc_info=True,
            )
            return {}
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            LOGGER.warning(
                "ツール設定ファイルの解析に失敗しました: %s",
                self._config_path,
                exc_info=True,
            )
            return {}
        if isinstance(payload, dict):
            return payload
        return {}

    def _write_payload(self, payload: dict) -> None:
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._config_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            LOGGER.warning(
                "ツール設定ファイルの保存に失敗しました: %s",
                self._config_path,
                exc_info=True,
            )
