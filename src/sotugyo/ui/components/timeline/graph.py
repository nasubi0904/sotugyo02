"""タイムライン描画向け NodeGraph 拡張。"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Callable, Dict, Optional, Tuple

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPen
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsRectItem,
    QGraphicsSimpleTextItem,
)
from NodeGraphQt import NodeGraph

from ....domain.projects.timeline import DEFAULT_TIMELINE_UNIT

LOGGER = logging.getLogger(__name__)


class TimelineNodeGraph(NodeGraph):
    """ノード移動にタイムライン制約を適用するためのグラフ。"""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._timeline_move_handler: Optional[Callable[[dict], None]] = None

    def set_timeline_move_handler(
        self, handler: Optional[Callable[[dict], None]]
    ) -> None:
        self._timeline_move_handler = handler

    def _on_nodes_moved(self, node_data):  # pragma: no cover - NodeGraphQt 依存
        if self._timeline_move_handler is not None:
            try:
                self._timeline_move_handler(node_data)
            except Exception:  # pragma: no cover - Qt 依存の例外
                LOGGER.debug("タイムライン制約の適用に失敗", exc_info=True)
        super()._on_nodes_moved(node_data)


class TimelineGridOverlay(QObject):
    """ノードエディタ上に日付枠線を描画するオーバーレイ。"""

    _WEEKDAY_LABELS = ["月", "火", "水", "木", "金", "土", "日"]

    def __init__(self, view) -> None:
        super().__init__(view)
        self._view = view
        self._scene = getattr(view, "scene", lambda: None)()
        self._column_width = DEFAULT_TIMELINE_UNIT
        self._column_units = 1
        self._origin_x = 0.0
        self._start_date = date.today()
        self._today = date.today()
        self._columns: Dict[
            int, Tuple[QGraphicsRectItem, QGraphicsLineItem, QGraphicsSimpleTextItem]
        ] = {}
        self._last_visible_rect = None
        self._label_font = QFont()
        self._label_font.setPointSize(9)
        self._label_font.setWeight(QFont.Weight.DemiBold)
        viewport = getattr(view, "viewport", None)
        if callable(viewport):
            vp = viewport()
            if vp is not None:
                vp.installEventFilter(self)

    def eventFilter(self, obj, event):  # pragma: no cover - Qt 依存
        if event is not None and event.type() in {QEvent.Paint, QEvent.Resize, QEvent.Wheel}:
            self.update_overlay()
        return False

    def set_column_width(self, width: float) -> None:
        self._column_width = max(1.0, float(width))
        self.update_overlay(force=True)

    def set_column_units(self, units: int) -> None:
        normalized = max(1, int(units))
        if normalized == self._column_units:
            return
        self._column_units = normalized
        self.update_overlay(force=True)

    def set_origin_x(self, value: float) -> None:
        self._origin_x = float(value)
        self.update_overlay(force=True)

    def set_start_date(self, start: date) -> None:
        self._start_date = start
        self._today = date.today()
        self.update_overlay(force=True)

    def update_overlay(self, *, force: bool = False) -> None:
        if self._scene is None or self._column_width <= 0:
            return
        rect = self._visible_scene_rect()
        if rect is None:
            return
        if not force and rect == self._last_visible_rect:
            return
        self._last_visible_rect = rect
        start_index = int((rect.left() - self._origin_x) / self._column_width) - 1
        end_index = int((rect.right() - self._origin_x) / self._column_width) + 2
        self._ensure_columns(range(start_index, end_index))

    def _visible_scene_rect(self):  # pragma: no cover - NodeGraphQt 依存
        view = self._view
        if view is None:
            return None
        viewport = getattr(view, "viewport", None)
        if not callable(viewport):
            return None
        vp = viewport()
        if vp is None:
            return None
        rect = vp.rect()
        map_to_scene = getattr(view, "mapToScene", None)
        if not callable(map_to_scene):
            return None
        top_left = map_to_scene(rect.topLeft())
        bottom_right = map_to_scene(rect.bottomRight())
        if top_left is None or bottom_right is None:
            return None
        scene_rect = type(rect)(top_left, bottom_right)
        return scene_rect.normalized()

    def _ensure_columns(self, indexes) -> None:  # pragma: no cover - NodeGraphQt 依存
        if self._scene is None:
            return
        for index in list(self._columns.keys()):
            if index not in indexes:
                background, line, label = self._columns.pop(index)
                self._scene.removeItem(background)
                self._scene.removeItem(line)
                self._scene.removeItem(label)
        for index in indexes:
            if index in self._columns:
                self._update_column(index)
            else:
                self._create_column(index)

    def _create_column(self, index: int) -> None:  # pragma: no cover - NodeGraphQt 依存
        position = self._origin_x + index * self._column_width
        background = QGraphicsRectItem(position, -10000, self._column_width, 20000)
        background.setPen(QPen(Qt.PenStyle.NoPen))
        background.setBrush(self._background_brush(index))
        background.setZValue(-200)
        background.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

        line = QGraphicsLineItem(position, -10000, position, 10000)
        pen = self._line_pen(index)
        pen.setCosmetic(True)
        line.setPen(pen)
        line.setZValue(-150)
        line.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

        label = QGraphicsSimpleTextItem(self._format_label(index))
        label.setFont(self._label_font)
        label.setBrush(self._label_brush(index))
        label.setPos(position + 12, -54)
        label.setZValue(-50)
        label.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        label.setFlag(
            QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations,
            True,
        )
        if self._scene is not None:
            self._scene.addItem(background)
            self._scene.addItem(line)
            self._scene.addItem(label)
        self._columns[index] = (background, line, label)

    def _update_column(self, index: int) -> None:  # pragma: no cover - NodeGraphQt 依存
        background, line, label = self._columns[index]
        position = self._origin_x + index * self._column_width
        background.setRect(position, -10000, self._column_width, 20000)
        background.setBrush(self._background_brush(index))
        background.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        line.setLine(position, -10000, position, 10000)
        pen = self._line_pen(index)
        pen.setCosmetic(True)
        line.setPen(pen)
        line.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        label.setText(self._format_label(index))
        label.setBrush(self._label_brush(index))
        label.setPos(position + 12, -54)
        label.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    def _format_label(self, index: int) -> str:
        target_date = self._date_for_index(index)
        weekday = self._weekday_label(target_date)
        if self._column_units <= 1:
            return target_date.strftime(f"%Y/%m/%d ({weekday})")
        end_date = target_date + timedelta(days=self._column_units - 1)
        return "{}〜{} ({}始まり)".format(
            target_date.strftime("%Y/%m/%d"),
            end_date.strftime("%m/%d"),
            weekday,
        )

    def _date_for_index(self, index: int) -> date:
        return self._start_date + timedelta(days=index * self._column_units)

    def _weekday_label(self, target_date: date) -> str:
        return self._WEEKDAY_LABELS[target_date.weekday() % len(self._WEEKDAY_LABELS)]

    def _background_brush(self, index: int) -> QBrush:
        target_date = self._date_for_index(index)
        if target_date == self._today:
            color = QColor(68, 104, 182, 120)
        elif target_date.weekday() >= 5:
            color = QColor(128, 78, 78, 100)
        elif index % 2 == 0:
            color = QColor(24, 36, 64, 110)
        else:
            color = QColor(16, 28, 52, 90)
        return QBrush(color)

    def _line_pen(self, index: int) -> QPen:
        target_date = self._date_for_index(index)
        if target_date == self._today:
            color = QColor(113, 178, 255, 220)
            width = 2.0
        elif target_date.weekday() >= 5:
            color = QColor(231, 140, 140, 160)
            width = 1.5
        else:
            color = QColor(118, 146, 212, 160)
            width = 1.2
        pen = QPen(color)
        pen.setWidthF(width)
        return pen

    def _label_brush(self, index: int) -> QBrush:
        target_date = self._date_for_index(index)
        if target_date == self._today:
            color = QColor(140, 192, 255)
        elif target_date.weekday() >= 5:
            color = QColor(255, 196, 160)
        else:
            color = QColor(198, 210, 239)
        return QBrush(color)
