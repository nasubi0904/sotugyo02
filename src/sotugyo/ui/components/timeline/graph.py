"""タイムライン描画向け NodeGraph 拡張。"""

from __future__ import annotations

import logging
from datetime import date
from typing import Callable, Dict, Optional, Tuple

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QGraphicsLineItem, QGraphicsSimpleTextItem
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

    def __init__(self, view) -> None:
        super().__init__(view)
        self._view = view
        self._scene = getattr(view, "scene", lambda: None)()
        self._column_width = DEFAULT_TIMELINE_UNIT
        self._origin_x = 0.0
        self._start_date = date.today()
        self._columns: Dict[int, Tuple[QGraphicsLineItem, QGraphicsSimpleTextItem]] = {}
        self._last_visible_rect = None
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

    def set_origin_x(self, value: float) -> None:
        self._origin_x = float(value)
        self.update_overlay(force=True)

    def set_start_date(self, start: date) -> None:
        self._start_date = start
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
                line, label = self._columns.pop(index)
                self._scene.removeItem(line)
                self._scene.removeItem(label)
        for index in indexes:
            if index in self._columns:
                self._update_column(index)
            else:
                self._create_column(index)

    def _create_column(self, index: int) -> None:  # pragma: no cover - NodeGraphQt 依存
        position = self._origin_x + index * self._column_width
        line = QGraphicsLineItem(position, -10000, position, 10000)
        label = QGraphicsSimpleTextItem(self._format_label(index))
        label.setPos(position + 6, -36)
        if self._scene is not None:
            self._scene.addItem(line)
            self._scene.addItem(label)
        self._columns[index] = (line, label)

    def _update_column(self, index: int) -> None:  # pragma: no cover - NodeGraphQt 依存
        line, label = self._columns[index]
        position = self._origin_x + index * self._column_width
        line.setLine(position, -10000, position, 10000)
        label.setText(self._format_label(index))
        label.setPos(position + 6, -36)

    def _format_label(self, index: int) -> str:
        target_date = self._start_date + date.resolution * index
        return target_date.strftime("%m/%d")
