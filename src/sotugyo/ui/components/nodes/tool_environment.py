"""ツール環境ノード。"""

from __future__ import annotations

from typing import ClassVar, Iterable

from sotugyo.qt_compat import ensure_qt_module_alias

ensure_qt_module_alias()
from NodeGraphQt import BaseNode


class ToolEnvironmentNode(BaseNode):
    """登録済みツール環境を表すノード。"""

    __identifier__: ClassVar[str] = "sotugyo.tooling"
    NODE_NAME: ClassVar[str] = "ツール環境"

    def __init__(self) -> None:
        super().__init__()
        self.add_input("前段")
        self.add_output("起動")
        self.set_property("width", 260, push_undo=False)
        self.set_property("height", 180, push_undo=False)
        self.set_color(80, 130, 190)

    @classmethod
    def node_type_identifier(cls) -> str:
        return f"{cls.__identifier__}.{cls.__name__}"

    def sync_input_plugs(self, names: Iterable[str]) -> None:
        existing = set(self.input_ports().keys())
        for name in names:
            cleaned = str(name).strip()
            if not cleaned or cleaned in existing:
                continue
            self.add_input(cleaned)
            existing.add(cleaned)


__all__ = ["ToolEnvironmentNode"]
