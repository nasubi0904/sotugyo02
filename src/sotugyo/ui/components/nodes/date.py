"""日付ノード実装。"""

from __future__ import annotations

from datetime import date
from typing import ClassVar

from qtpy import QtCore

from sotugyo.qt_compat import ensure_qt_module_alias

ensure_qt_module_alias()
from NodeGraphQt import BackdropNode
from NodeGraphQt.constants import NodePropWidgetEnum, Z_VAL_BACKDROP
from NodeGraphQt.nodes.backdrop_node import BackdropNodeItem


class DateNodeItem(BackdropNodeItem):
    """日付ノード専用のバックドロップアイテム。"""

    DEFAULT_SNAP_GRID: ClassVar[float] = 32.0
    _snap_grid_size: float = DEFAULT_SNAP_GRID
    _is_snapping: bool

    def __init__(self, name: str = "backdrop", text: str = "", parent=None):
        self._is_snapping = False
        self._snap_grid_size = self.DEFAULT_SNAP_GRID
        super().__init__(name, text, parent)

    def on_sizer_pos_changed(self, pos: QtCore.QPointF) -> None:
        width = self._snap_value(pos.x() + self._sizer.size)
        height = self._snap_value(pos.y() + self._sizer.size)
        snapped_pos = QtCore.QPointF(width - self._sizer.size, height - self._sizer.size)
        if self._is_snapping:
            self._width = width
            self._height = height
            self.update()
            return

        if (
            QtCore.qFuzzyCompare(pos.x() + 1.0, snapped_pos.x() + 1.0)
            and QtCore.qFuzzyCompare(pos.y() + 1.0, snapped_pos.y() + 1.0)
        ):
            self._width = width
            self._height = height
            self.update()
            return

        self._is_snapping = True
        try:
            self._sizer.set_pos(snapped_pos.x(), snapped_pos.y())
        finally:
            self._is_snapping = False
        self._width = width
        self._height = height
        self.update()

    def set_snap_grid_size(self, grid_size: float) -> None:
        self._snap_grid_size = float(grid_size) if grid_size > 0 else 0.0

    def _snap_value(self, value: float) -> float:
        snap_grid = getattr(self, "_snap_grid_size", self.DEFAULT_SNAP_GRID)
        if snap_grid <= 0:
            return value
        return round(value / snap_grid) * snap_grid


class DateNode(BackdropNode):
    """タイムライン上の日付を示すシンプルなバックドロップノード。"""

    __identifier__: ClassVar[str] = "sotugyo.timeline"
    NODE_NAME: ClassVar[str] = "日付ノード"

    def __init__(self) -> None:
        super().__init__(DateNodeItem)
        self.create_property(
            "date_label",
            self._today_label(),
            widget_type=NodePropWidgetEnum.QLINE_EDIT.value,
            widget_tooltip="表示する日付 (YYYY-MM-DD)",
        )
        self.set_property("width", 200, push_undo=False)
        self.set_property("height", 120, push_undo=False)
        self.set_color(200, 170, 110)
        self.view.setZValue(Z_VAL_BACKDROP - 1)

    @classmethod
    def node_type_identifier(cls) -> str:
        return f"{cls.__identifier__}.{cls.__name__}"

    def set_snap_grid_size(self, grid_size: float) -> None:
        if hasattr(self.view, "set_snap_grid_size"):
            self.view.set_snap_grid_size(grid_size)

    @staticmethod
    def _today_label() -> str:
        return date.today().strftime("%Y-%m-%d")


__all__ = ["DateNode"]
