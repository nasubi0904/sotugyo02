"""ツール環境ノード。"""

from __future__ import annotations

from typing import ClassVar

from sotugyo.qt_compat import ensure_qt_module_alias

ensure_qt_module_alias()
from NodeGraphQt import BaseNode

from .node_style import NODE_STANDARD_WIDTH


class ToolEnvironmentNode(BaseNode):
    """登録済みツール環境を表すノード。"""

    __identifier__: ClassVar[str] = "sotugyo.tooling"
    NODE_NAME: ClassVar[str] = "ツール環境"

    def __init__(self) -> None:
        super().__init__()
        self.add_input("前段")
        self.add_output("出力")
        self.set_property("width", NODE_STANDARD_WIDTH, push_undo=False)
        self.set_property("height", 180, push_undo=False)
        self.set_color(60, 170, 160)

    @classmethod
    def node_type_identifier(cls) -> str:
        return f"{cls.__identifier__}.{cls.__name__}"


__all__ = ["ToolEnvironmentNode"]
