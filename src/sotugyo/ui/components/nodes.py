"""ノードエディタで利用するカスタムノード定義。"""

from __future__ import annotations

from typing import ClassVar

from NodeGraphQt import BaseNode


class BaseDemoNode(BaseNode):
    """デモ用の基本ノードクラス。

    単一の入力ポートと出力ポートを提供し、
    ノード同士の接続や切断をシンプルに試せる構成にする。
    """

    __identifier__: ClassVar[str] = "sotugyo.demo"
    NODE_NAME: ClassVar[str] = "BaseDemoNode"

    def __init__(self) -> None:
        super().__init__()
        self.add_input("入力")
        self.add_output("出力")


class TaskNode(BaseDemoNode):
    """タスク処理を表すデモノード。"""

    NODE_NAME: ClassVar[str] = "タスクノード"


class ReviewNode(BaseDemoNode):
    """レビュー工程を表すデモノード。"""

    NODE_NAME: ClassVar[str] = "レビュー ノード"
