"""デモ用ノード群。"""

from __future__ import annotations

from typing import ClassVar

from sotugyo.qt_compat import ensure_qt_module_alias

ensure_qt_module_alias()
from NodeGraphQt import BaseNode
from .constants import STANDARD_NODE_WIDTH


class BaseDemoNode(BaseNode):
    """デモ用の基本ノードクラス。"""

    __identifier__: ClassVar[str] = "sotugyo.demo"
    NODE_NAME: ClassVar[str] = "BaseDemoNode"

    def __init__(self) -> None:
        super().__init__()
        self.add_input("入力")
        self.add_output("出力")
        self.set_property("width", STANDARD_NODE_WIDTH, push_undo=False)


class TaskNode(BaseDemoNode):
    """タスク処理を表すデモノード。"""

    NODE_NAME: ClassVar[str] = "タスクノード"

    def __init__(self) -> None:
        super().__init__()
        self.set_color(92, 176, 110)


class ReviewNode(BaseDemoNode):
    """レビュー工程を表すデモノード。"""

    NODE_NAME: ClassVar[str] = "レビュー ノード"

    def __init__(self) -> None:
        super().__init__()
        self.set_color(180, 130, 220)
