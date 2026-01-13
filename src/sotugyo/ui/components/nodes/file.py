"""ファイルノード。"""

from __future__ import annotations

from typing import ClassVar

from sotugyo.qt_compat import ensure_qt_module_alias

ensure_qt_module_alias()
from NodeGraphQt import BaseNode


class FileNode(BaseNode):
    """ワークフロー上でファイルを示すノード。"""

    __identifier__: ClassVar[str] = "sotugyo.workflow"
    NODE_NAME: ClassVar[str] = "ファイルノード"
    FILE_PATH_KEY: ClassVar[str] = "file_path"

    def __init__(self) -> None:
        super().__init__()
        self.add_input("入力")
        self.add_output("出力")
        self.set_property("width", 240, push_undo=False)
        self.set_property("height", 140, push_undo=False)
        self.set_color(120, 160, 120)
        self._ensure_custom_file_path()

    def _ensure_custom_file_path(self) -> None:
        model = getattr(self, "model", None)
        if model is None:
            return
        props = getattr(model, "custom_properties", None)
        if callable(props):
            props = props()
        if isinstance(props, dict):
            props.setdefault(self.FILE_PATH_KEY, "")

    @classmethod
    def node_type_identifier(cls) -> str:
        return f"{cls.__identifier__}.{cls.__name__}"


__all__ = ["FileNode"]
