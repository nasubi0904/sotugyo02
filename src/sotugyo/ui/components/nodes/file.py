"""ファイルノードの実装。"""

from __future__ import annotations

from typing import ClassVar

from sotugyo.qt_compat import ensure_qt_module_alias

ensure_qt_module_alias()
from NodeGraphQt import BaseNode


class FileNode(BaseNode):
    """ワークフローでファイルを参照するノード。"""

    __identifier__: ClassVar[str] = "sotugyo.workflow"
    NODE_NAME: ClassVar[str] = "ファイルノード"

    def __init__(self) -> None:
        super().__init__()
        self.add_input("入力", multi_input=True)
        self.add_output("出力", multi_output=True)
        self.set_color(96, 165, 250)

    @classmethod
    def node_type_identifier(cls) -> str:
        return f"{cls.__identifier__}.{cls.__name__}"


__all__ = ["FileNode"]
