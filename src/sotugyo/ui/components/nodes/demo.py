"""デモ用ノード群。"""

from __future__ import annotations

from typing import ClassVar

from sotugyo.qt_compat import ensure_qt_module_alias

ensure_qt_module_alias()
from NodeGraphQt import BaseNode

from .node_style import NODE_STANDARD_WIDTH


class BaseDemoNode(BaseNode):
    """デモ用の基本ノードクラス。"""

    __identifier__: ClassVar[str] = "sotugyo.demo"
    NODE_NAME: ClassVar[str] = "BaseDemoNode"

    def __init__(self) -> None:
        super().__init__()
        self.add_input("入力")
        self.add_output("出力")
        self.set_property("width", NODE_STANDARD_WIDTH, push_undo=False)
        self.set_color(120, 120, 120)


class TaskNode(BaseDemoNode):
    """タスク処理を表すデモノード。"""

    NODE_NAME: ClassVar[str] = "タスクノード"

    def __init__(self) -> None:
        super().__init__()
        self.set_color(110, 190, 120)


class ReviewNode(BaseDemoNode):
    """レビュー工程を表すデモノード。"""

    NODE_NAME: ClassVar[str] = "レビュー ノード"

    def __init__(self) -> None:
        super().__init__()
        self.set_color(170, 120, 210)
