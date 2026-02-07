"""デモ用ノード群。"""

from __future__ import annotations

from typing import ClassVar

from sotugyo.qt_compat import ensure_qt_module_alias

ensure_qt_module_alias()
from NodeGraphQt import BaseNode

from .node_metrics import DEFAULT_NODE_WIDTH


class BaseDemoNode(BaseNode):
    """デモ用の基本ノードクラス。"""

    __identifier__: ClassVar[str] = "sotugyo.demo"
    NODE_NAME: ClassVar[str] = "BaseDemoNode"
    NODE_COLOR: ClassVar[tuple[int, int, int] | None] = None

    def __init__(self) -> None:
        super().__init__()
        self.add_input("入力")
        self.add_output("出力")
        self.set_property("width", DEFAULT_NODE_WIDTH, push_undo=False)
        if self.NODE_COLOR is not None:
            self.set_color(*self.NODE_COLOR)


class TaskNode(BaseDemoNode):
    """タスク処理を表すデモノード。"""

    NODE_NAME: ClassVar[str] = "タスクノード"
    NODE_COLOR: ClassVar[tuple[int, int, int] | None] = (99, 102, 241)


class ReviewNode(BaseDemoNode):
    """レビュー工程を表すデモノード。"""

    NODE_NAME: ClassVar[str] = "レビュー ノード"
    NODE_COLOR: ClassVar[tuple[int, int, int] | None] = (16, 185, 129)
