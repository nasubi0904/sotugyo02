"""タイムライン上の日付列ノード。"""

from __future__ import annotations

import json
import uuid
from typing import ClassVar

from qtpy import QtCore, QtGui

from sotugyo.qt_compat import ensure_qt_module_alias

ensure_qt_module_alias()
from NodeGraphQt import BaseNode
from NodeGraphQt.constants import NodePropWidgetEnum


class DateColumnNode(BaseNode):
    """背景の縦グリッドとして振る舞う日付列ノード。"""

    __identifier__: ClassVar[str] = "sotugyo.timeline"
    NODE_NAME: ClassVar[str] = "日付列"
    DEFAULT_WIDTH_UNITS: ClassVar[float] = 1.0

    def __init__(self) -> None:
        super().__init__()
        self.create_property(
            "date_id",
            "",
            widget_type=NodePropWidgetEnum.QLINE_EDIT.value,
            widget_tooltip="日付列を一意に識別する ID",
        )
        self.create_property(
            "index",
            0,
            widget_type=NodePropWidgetEnum.QSPIN_BOX.value,
            widget_tooltip="タイムライン上の列インデックス (0 ベース)",
        )
        self.create_property(
            "date_label",
            "",
            widget_type=NodePropWidgetEnum.QLINE_EDIT.value,
            widget_tooltip="列ヘッダーに表示するラベル",
        )
        self.create_property(
            "width_units",
            self.DEFAULT_WIDTH_UNITS,
            widget_type=NodePropWidgetEnum.QDOUBLESPIN_BOX.value,
            range=(0.1, 10.0),
            widget_tooltip="列の論理幅 (単位数)",
        )
        self.create_property(
            "attached_nodes",
            "[]",
            widget_type=NodePropWidgetEnum.QTEXT_EDIT.value,
            widget_tooltip="この列にスナップしたノード ID の一覧 (JSON)",
        )
        self.set_property("date_id", str(uuid.uuid4()), push_undo=False)
        self.set_property("index", 0, push_undo=False)
        self.set_property("date_label", "", push_undo=False)
        self.set_property("width_units", self.DEFAULT_WIDTH_UNITS, push_undo=False)
        self.set_property("attached_nodes", "[]", push_undo=False)
        self._apply_base_style()

    @classmethod
    def node_type_identifier(cls) -> str:
        """NodeGraphQt での識別子を返す。"""

        return f"{cls.__identifier__}.{cls.__name__}"

    def update_geometry(self, *, pixels_per_unit: float, scene_height: float) -> None:
        """単位スケールとシーン高さに応じて見た目を更新する。"""

        width_units = self._read_width_units()
        width_px = max(1.0, width_units * pixels_per_unit)
        self.set_property("width", width_px, push_undo=False)
        self.set_property("height", scene_height, push_undo=False)
        self.view.width = width_px
        self.view.height = scene_height
        self.view.draw_node()

    def snap_position_x(self, pixels_per_unit: float) -> float:
        """スナップ対象となる X 座標を返す。"""

        width_px = max(1.0, self._read_width_units() * pixels_per_unit)
        pos_x, _ = self.pos()
        return pos_x + width_px / 2.0

    def _read_width_units(self) -> float:
        try:
            return float(self.get_property("width_units"))
        except Exception:
            return self.DEFAULT_WIDTH_UNITS

    def _apply_base_style(self) -> None:
        self.set_color(232, 240, 250)
        self.set_property("text_color", (70, 80, 90, 255), push_undo=False)
        if hasattr(self.view, "setZValue"):
            self.view.setZValue(-5000)
        gradient = QtGui.QLinearGradient(0, 0, 0, 1)
        gradient.setColorAt(0.0, QtGui.QColor(232, 240, 250, 220))
        gradient.setColorAt(1.0, QtGui.QColor(232, 240, 250, 180))
        self.view.gradient = gradient
        self.view.border_color = QtGui.QColor(190, 200, 210, 80)
        self.view.roundness = 2
        self.view.layout_direction = QtCore.Qt.LeftToRight


def decode_attached_nodes(raw_value: object) -> list[str]:
    """attached_nodes プロパティの値をリストへ変換する。"""

    if isinstance(raw_value, (list, tuple)):
        return [str(entry) for entry in raw_value if str(entry).strip()]
    if not isinstance(raw_value, str):
        return []
    text = raw_value.strip()
    if not text:
        return []
    try:
        loaded = json.loads(text)
        if isinstance(loaded, list):
            return [str(entry) for entry in loaded if str(entry).strip()]
    except json.JSONDecodeError:
        pass
    return [entry.strip() for entry in text.split(",") if entry.strip()]


def encode_attached_nodes(nodes: list[str]) -> str:
    """ノード ID のリストを JSON 文字列へ変換する。"""

    unique = []
    for entry in nodes:
        if entry and entry not in unique:
            unique.append(entry)
    return json.dumps(unique)

