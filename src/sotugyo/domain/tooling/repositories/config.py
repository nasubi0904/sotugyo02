"""ツールおよび環境定義の永続化レイヤー。"""

from __future__ import annotations

from typing import ClassVar, Iterable, List, Tuple

from ..models import RegisteredTool, ToolEnvironmentDefinition


class ToolConfigRepository:
    """マシン依存の設定ファイルからツール情報を読み書きする。"""

    _tools: ClassVar[List[RegisteredTool]] = []
    _environments: ClassVar[List[ToolEnvironmentDefinition]] = []

    # ------------------------------------------------------------------
    # 読み書き
    # ------------------------------------------------------------------
    def load_all(self) -> Tuple[List[RegisteredTool], List[ToolEnvironmentDefinition]]:
        return list(self._tools), list(self._environments)

    def save_all(
        self,
        tools: Iterable[RegisteredTool],
        environments: Iterable[ToolEnvironmentDefinition],
    ) -> None:
        self._tools = list(tools)
        self._environments = list(environments)
