"""日付ノード実装。"""

from __future__ import annotations

from datetime import date
from typing import ClassVar

from sotugyo.qt_compat import ensure_qt_module_alias

ensure_qt_module_alias()
from NodeGraphQt import BaseNode
from NodeGraphQt.constants import NodePropWidgetEnum


class DateNode(BaseNode):
    """タイムライン上の日付を示すシンプルなノード。"""

    __identifier__: ClassVar[str] = "sotugyo.timeline"
    NODE_NAME: ClassVar[str] = "日付ノード"

    def __init__(self) -> None:
        super().__init__()
        self.create_property(
            "date_label",
            self._today_label(),
            widget_type=NodePropWidgetEnum.QLINE_EDIT.value,
            widget_tooltip="表示する日付 (YYYY-MM-DD)",
        )
        self.set_property("width", 200, push_undo=False)
        self.set_property("height", 120, push_undo=False)
        self.set_color(200, 170, 110)

    @classmethod
    def node_type_identifier(cls) -> str:
        return f"{cls.__identifier__}.{cls.__name__}"

    @staticmethod
    def _today_label() -> str:
        return date.today().strftime("%Y-%m-%d")


__all__ = ["DateNode"]
