"""タイムライン描画向け NodeGraph 拡張。"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Callable, Dict, Iterable, Optional, Union

from PySide6.QtCore import (
    QEvent,
    QObject,
    QPoint,
    QPointF,
    QRect,
    QRectF,
    Qt,
    QTimer,
)
from PySide6.QtGui import QBrush, QColor, QFont, QPen, QTransform
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


@dataclass
class _GridColumnItems:
    background: QGraphicsRectItem
    line: QGraphicsLineItem


@dataclass
class _LabelItem:
    label: QGraphicsSimpleTextItem


@dataclass
class LayerUpdateContext:
    """レイヤ更新に必要な最小限情報。"""

    date_mapper: "DateMapper"
    visible_scene_rect: QRectF
    viewport_rect: QRect
    top_scene_y: float
    column_width_px: float
    transform: QTransform
    theme: "ThemeProvider"
    today: date


class DateMapper:
    """時間軸の唯一の情報源。"""

    def __init__(
        self,
        *,
        start_date: Optional[date] = None,
        column_width: float = DEFAULT_TIMELINE_UNIT,
        column_units: int = 1,
        origin_x: float = 0.0,
    ) -> None:
        self._start_date = start_date or date.today()
        self._column_width = max(1.0, float(column_width))
        self._column_units = max(1, int(column_units))
        self._origin_x = float(origin_x)

    @property
    def start_date(self) -> date:
        return self._start_date

    @property
    def column_width(self) -> float:
        return self._column_width

    @property
    def column_units(self) -> int:
        return self._column_units

    @property
    def origin_x(self) -> float:
        return self._origin_x

    def set_start_date(self, value: date) -> bool:
        if value == self._start_date:
            return False
        self._start_date = value
        return True

    def set_column_width(self, value: float) -> bool:
        normalized = max(1.0, float(value))
        if math.isclose(normalized, self._column_width):
            return False
        self._column_width = normalized
        return True

    def set_column_units(self, value: int) -> bool:
        normalized = max(1, int(value))
        if normalized == self._column_units:
            return False
        self._column_units = normalized
        return True

    def set_origin_x(self, value: float) -> bool:
        normalized = float(value)
        if math.isclose(normalized, self._origin_x):
            return False
        self._origin_x = normalized
        return True

    def date_to_index(self, value: date) -> float:
        delta_days = (value - self._start_date).days
        return delta_days / self._column_units

    def index_to_date(self, index: int) -> date:
        return self._start_date + timedelta(days=index * self._column_units)

    def index_to_x(self, index: float) -> float:
        return self._origin_x + index * self._column_width

    def date_to_x(self, value: date) -> float:
        return self.index_to_x(self.date_to_index(value))

    def x_to_index(self, value: float) -> float:
        return (float(value) - self._origin_x) / self._column_width

    def x_to_date(self, value: float) -> date:
        index = self.x_to_index(value)
        nearest_index = int(round(index))
        return self.index_to_date(nearest_index)

    def index_at_x(self, value: float) -> float:
        return self.x_to_index(value)

    def date_at_index(self, index: int) -> date:
        return self.index_to_date(index)

    def date_at_x(self, value: float) -> date:
        return self.x_to_date(value)


class VisibleRectProvider(QObject):
    """ビューポートの可視矩形を一元提供する。"""

    def __init__(self, on_change: Callable[[], None], parent: Optional[QObject] = None):
        super().__init__(parent)
        self._view = None
        self._viewport = None
        self._hbar = None
        self._vbar = None
        self._on_change = on_change
        self._transform_connected = False

    def set_view(self, view) -> None:  # pragma: no cover - NodeGraphQt 依存
        if self._viewport is not None:
            self._viewport.removeEventFilter(self)
        if self._hbar is not None:
            try:
                self._hbar.valueChanged.disconnect(self._emit_change)
            except Exception:
                pass
        if self._vbar is not None:
            try:
                self._vbar.valueChanged.disconnect(self._emit_change)
            except Exception:
                pass
        if self._view is not None and self._transform_connected:
            try:
                self._view.transformChanged.disconnect(self._emit_change)
            except Exception:
                pass
        self._view = view
        self._viewport = None
        self._hbar = None
        self._vbar = None
        self._transform_connected = False
        if view is None:
            return
        viewport = getattr(view, "viewport", None)
        if callable(viewport):
            vp = viewport()
            if vp is not None:
                vp.installEventFilter(self)
                self._viewport = vp
        hbar = getattr(view, "horizontalScrollBar", None)
        if callable(hbar):
            self._hbar = hbar()
            if self._hbar is not None:
                self._hbar.valueChanged.connect(self._emit_change)
        vbar = getattr(view, "verticalScrollBar", None)
        if callable(vbar):
            self._vbar = vbar()
            if self._vbar is not None:
                self._vbar.valueChanged.connect(self._emit_change)
        if hasattr(view, "transformChanged"):
            try:
                view.transformChanged.connect(self._emit_change)
                self._transform_connected = True
            except Exception:
                self._transform_connected = False
        self._emit_change()

    def eventFilter(self, obj, event):  # pragma: no cover - Qt 依存
        if event is None:
            return False
        if event.type() in {
            QEvent.Resize,
            QEvent.Wheel,
            QEvent.MouseMove,
            QEvent.Scroll,
        }:
            self._emit_change()
        return False

    def _emit_change(self) -> None:
        if callable(self._on_change):
            self._on_change()

    def scene_rect(self) -> Optional[QRectF]:  # pragma: no cover - NodeGraphQt 依存
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
        scene_rect = QRectF(top_left, bottom_right)
        return scene_rect.normalized()

    def viewport_rect(self) -> Optional[QRect]:  # pragma: no cover - NodeGraphQt 依存
        if self._viewport is None:
            return None
        return self._viewport.rect()


class ThemeProvider:
    """タイムライン描画に用いるテーマ定義。"""

    def __init__(self) -> None:
        self._label_font = QFont()
        self._label_font.setPointSize(9)
        self._label_font.setWeight(QFont.Weight.DemiBold)

    @property
    def label_font(self) -> QFont:
        return self._label_font

    def background_brush(self, *, is_today: bool, is_weekend: bool, is_even: bool) -> QBrush:
        if is_today:
            color = QColor(68, 104, 182, 120)
        elif is_weekend:
            color = QColor(128, 78, 78, 100)
        elif is_even:
            color = QColor(24, 36, 64, 110)
        else:
            color = QColor(16, 28, 52, 90)
        return QBrush(color)

    def grid_pen(self, *, is_today: bool, is_weekend: bool) -> QPen:
        if is_today:
            color = QColor(113, 178, 255, 220)
            width = 2.0
        elif is_weekend:
            color = QColor(231, 140, 140, 160)
            width = 1.5
        else:
            color = QColor(118, 146, 212, 160)
            width = 1.2
        pen = QPen(color)
        pen.setWidthF(width)
        pen.setCosmetic(True)
        return pen

    def label_brush(self, *, is_today: bool, is_weekend: bool) -> QBrush:
        if is_today:
            color = QColor(140, 192, 255)
        elif is_weekend:
            color = QColor(255, 196, 160)
        else:
            color = QColor(198, 210, 239)
        return QBrush(color)

    def today_marker_pen(self) -> QPen:
        pen = QPen(QColor(210, 234, 255, 200))
        pen.setWidthF(2.0)
        pen.setCosmetic(True)
        return pen


class LabelFormatter:
    """ズーム率に応じたラベル文字列を生成する。"""

    WEEKDAY_LABELS = ["月", "火", "水", "木", "金", "土", "日"]

    def format(self, *, target_date: date, units: int) -> str:
        weekday = self.WEEKDAY_LABELS[target_date.weekday() % len(self.WEEKDAY_LABELS)]
        if units <= 1:
            return target_date.strftime(f"%Y/%m/%d ({weekday})")
        end_date = target_date + timedelta(days=units - 1)
        return "{}〜{} ({}始まり)".format(
            target_date.strftime("%Y/%m/%d"),
            end_date.strftime("%m/%d"),
            weekday,
        )


class UpdateScheduler(QObject):
    """短時間の多発イベントを集約するスケジューラ。"""

    def __init__(self, callback: Callable[[bool, bool], None], parent: Optional[QObject] = None):
        super().__init__(parent)
        self._callback = callback
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_timeout)
        self._dirty_geometry = False
        self._dirty_axis = False

    def request(self, *, geometry: bool = False, axis: bool = False, force: bool = False) -> None:
        if force:
            if self._timer.isActive():
                self._timer.stop()
            self._dispatch(True, True)
            self._dirty_geometry = False
            self._dirty_axis = False
            return
        if axis:
            self._dirty_axis = True
            self._dirty_geometry = True
        else:
            self._dirty_geometry = self._dirty_geometry or geometry
        if not self._timer.isActive():
            self._timer.start(0)

    def _on_timeout(self) -> None:
        geometry = self._dirty_geometry
        axis = self._dirty_axis
        self._dirty_geometry = False
        self._dirty_axis = False
        self._dispatch(geometry, axis)

    def _dispatch(self, geometry: bool, axis: bool) -> None:
        try:
            self._callback(geometry, axis)
        except Exception:  # pragma: no cover - Qt 依存
            LOGGER.debug("タイムライン更新の実行に失敗", exc_info=True)


class _BaseLayer:
    """レイヤ共通の振る舞いを定義する基底クラス。"""

    def __init__(self, scene, theme: ThemeProvider) -> None:
        self._scene = scene
        self._theme = theme

    def update(self, context: LayerUpdateContext) -> None:
        raise NotImplementedError


class GridTileLayer(_BaseLayer):
    """列単位の背景タイルと縦グリッド線を描画する。"""

    PADDING = 2

    def __init__(self, scene, theme: ThemeProvider) -> None:
        super().__init__(scene, theme)
        self._columns: Dict[int, _GridColumnItems] = {}

    def update(self, context: LayerUpdateContext) -> None:  # pragma: no cover - NodeGraphQt 依存
        if self._scene is None or context.visible_scene_rect is None:
            return
        indexes = list(self._iter_required_indexes(context))
        current_keys = set(self._columns.keys())
        required_keys = set(indexes)
        for index in current_keys - required_keys:
            column = self._columns.pop(index)
            self._scene.removeItem(column.background)
            self._scene.removeItem(column.line)
        for index in indexes:
            if index in self._columns:
                self._update_column(index, context)
            else:
                self._create_column(index, context)

    def _iter_required_indexes(self, context: LayerUpdateContext) -> Iterable[int]:
        mapper = context.date_mapper
        rect = context.visible_scene_rect
        left_index = math.floor(mapper.index_at_x(rect.left()))
        right_index = math.ceil(mapper.index_at_x(rect.right()))
        start = int(left_index) - self.PADDING
        end = int(right_index) + self.PADDING
        return range(start, end + 1)

    def _create_column(self, index: int, context: LayerUpdateContext) -> None:
        mapper = context.date_mapper
        left = mapper.index_to_x(index)
        right = mapper.index_to_x(index + 1)
        width = right - left
        rect = context.visible_scene_rect
        background = QGraphicsRectItem(left, rect.top(), width, rect.height())
        background.setPen(QPen(Qt.PenStyle.NoPen))
        target_date = mapper.date_at_index(index)
        is_weekend = target_date.weekday() >= 5
        is_today = target_date == context.today
        brush = self._theme.background_brush(
            is_today=is_today,
            is_weekend=is_weekend,
            is_even=index % 2 == 0,
        )
        background.setBrush(brush)
        background.setZValue(-200)
        background.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

        line = QGraphicsLineItem(left, rect.top(), left, rect.bottom())
        line_pen = self._theme.grid_pen(is_today=is_today, is_weekend=is_weekend)
        line.setPen(line_pen)
        line.setZValue(-150)
        line.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

        self._scene.addItem(background)
        self._scene.addItem(line)
        self._columns[index] = _GridColumnItems(background=background, line=line)

    def _update_column(self, index: int, context: LayerUpdateContext) -> None:
        mapper = context.date_mapper
        column = self._columns[index]
        left = mapper.index_to_x(index)
        right = mapper.index_to_x(index + 1)
        width = right - left
        rect = context.visible_scene_rect
        column.background.setRect(left, rect.top(), width, rect.height())
        target_date = mapper.date_at_index(index)
        is_weekend = target_date.weekday() >= 5
        is_today = target_date == context.today
        column.background.setBrush(
            self._theme.background_brush(
                is_today=is_today,
                is_weekend=is_weekend,
                is_even=index % 2 == 0,
            )
        )
        column.line.setLine(left, rect.top(), left, rect.bottom())
        column.line.setPen(
            self._theme.grid_pen(is_today=is_today, is_weekend=is_weekend)
        )


class AxisLabelLayer(_BaseLayer):
    """列ヘッダーのラベルを管理する。"""

    MIN_LABEL_SPACING = 80  # ピクセル

    def __init__(self, scene, theme: ThemeProvider, formatter: LabelFormatter) -> None:
        super().__init__(scene, theme)
        self._formatter = formatter
        self._labels: Dict[int, _LabelItem] = {}

    def update(self, context: LayerUpdateContext) -> None:  # pragma: no cover - NodeGraphQt 依存
        if self._scene is None:
            return
        if context.visible_scene_rect is None or context.viewport_rect is None:
            return
        column_width_px = max(1.0, context.column_width_px)
        step = max(1, int(math.ceil(self.MIN_LABEL_SPACING / column_width_px)))
        mapper = context.date_mapper
        rect = context.visible_scene_rect
        raw_start = int(math.floor(mapper.index_at_x(rect.left()))) - 1
        if step > 1:
            adjusted_start = raw_start - (raw_start % step)
        else:
            adjusted_start = raw_start
        end = int(math.ceil(mapper.index_at_x(rect.right()))) + 1
        indexes = list(range(adjusted_start, end + 1, step))
        current_keys = set(self._labels.keys())
        required_keys = set(indexes)
        for index in current_keys - required_keys:
            label_item = self._labels.pop(index)
            self._scene.removeItem(label_item.label)
        for index in indexes:
            if index in self._labels:
                self._update_label(index, context)
            else:
                self._create_label(index, context)

    def _create_label(self, index: int, context: LayerUpdateContext) -> None:
        mapper = context.date_mapper
        label_item = QGraphicsSimpleTextItem()
        label_item.setFont(self._theme.label_font)
        label_item.setFlag(
            QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations,
            True,
        )
        label_item.setZValue(100)
        label_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self._scene.addItem(label_item)
        self._labels[index] = _LabelItem(label=label_item)
        self._update_label(index, context)

    def _update_label(self, index: int, context: LayerUpdateContext) -> None:
        mapper = context.date_mapper
        label_item = self._labels[index].label
        target_date = mapper.date_at_index(index)
        is_weekend = target_date.weekday() >= 5
        is_today = target_date == context.today
        label_item.setText(
            self._formatter.format(target_date=target_date, units=mapper.column_units)
        )
        label_item.setBrush(
            self._theme.label_brush(is_today=is_today, is_weekend=is_weekend)
        )
        x = mapper.index_to_x(index)
        label_item.setPos(x, context.top_scene_y)


class MarkerLayer(_BaseLayer):
    """今日ラインなどの強調表示。"""

    def __init__(self, scene, theme: ThemeProvider) -> None:
        super().__init__(scene, theme)
        self._line: Optional[QGraphicsLineItem] = None

    def update(self, context: LayerUpdateContext) -> None:  # pragma: no cover - NodeGraphQt 依存
        if self._scene is None or context.visible_scene_rect is None:
            return
        mapper = context.date_mapper
        today_x = mapper.date_to_x(context.today)
        rect = context.visible_scene_rect
        if self._line is None:
            self._line = QGraphicsLineItem(today_x, rect.top(), today_x, rect.bottom())
            self._line.setPen(self._theme.today_marker_pen())
            self._line.setZValue(10)
            self._line.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            self._scene.addItem(self._line)
        else:
            self._line.setLine(today_x, rect.top(), today_x, rect.bottom())
            self._line.setPen(self._theme.today_marker_pen())


class SnapGuideLayer(_BaseLayer):
    """スナップ補助線。将来的な拡張用のプレースホルダ。"""

    def update(self, context: LayerUpdateContext) -> None:  # pragma: no cover - 未実装
        return


class TimelineGridOverlay(QObject):
    """ノードエディタ上にタイムラインの軸情報を描画する。

    start_date を変更した場合は列境界もシーン上で移動する（補正なし）という
    ポリシーを採用する。
    """

    LABEL_VIEW_MARGIN = 6  # ピクセル

    def __init__(self, view) -> None:
        super().__init__(view)
        self._view = None
        self._scene = None
        self._date_mapper = DateMapper()
        self._theme = ThemeProvider()
        self._formatter = LabelFormatter()
        self._grid_layer: Optional[GridTileLayer] = None
        self._label_layer: Optional[AxisLabelLayer] = None
        self._marker_layer: Optional[MarkerLayer] = None
        self._snap_layer: Optional[SnapGuideLayer] = None
        self._layers = []
        self._today = date.today()
        self._last_scene_rect: Optional[QRectF] = None
        self._last_viewport_rect: Optional[QRect] = None
        self._visible_rect_provider = VisibleRectProvider(self._on_view_changed, self)
        self._scheduler = UpdateScheduler(self._on_scheduled_update, self)
        if view is not None:
            self.set_view(view)

    # --- 公開 API ------------------------------------------------------------
    def set_view(self, view) -> None:  # pragma: no cover - NodeGraphQt 依存
        self._view = view
        self._scene = getattr(view, "scene", lambda: None)()
        self._grid_layer = GridTileLayer(self._scene, self._theme)
        self._label_layer = AxisLabelLayer(self._scene, self._theme, self._formatter)
        self._marker_layer = MarkerLayer(self._scene, self._theme)
        self._snap_layer = SnapGuideLayer(self._scene, self._theme)
        self._layers = [
            self._grid_layer,
            self._marker_layer,
            self._label_layer,
            self._snap_layer,
        ]
        self._visible_rect_provider.set_view(view)
        self._scheduler.request(geometry=True, axis=True)

    def set_start_date(self, start: date) -> None:
        if self._date_mapper.set_start_date(start):
            self._today = date.today()
            self._scheduler.request(axis=True)

    def set_origin_x(self, value: float) -> None:
        if self._date_mapper.set_origin_x(value):
            self._scheduler.request(axis=True)

    def set_column_width(self, width: float) -> None:
        if self._date_mapper.set_column_width(width):
            self._scheduler.request(axis=True)

    def set_units(self, units: int) -> None:
        if self._date_mapper.set_column_units(units):
            self._scheduler.request(axis=True)

    def update(self, force: bool = False) -> None:
        if force:
            self._scheduler.request(force=True)
        else:
            self._scheduler.request(geometry=True)

    def get_snap_x(self, value: Union[date, int, float]) -> float:
        if isinstance(value, date):
            return self._date_mapper.date_to_x(value)
        return self._date_mapper.index_to_x(float(value))

    def get_snap_date(self, x: float) -> date:
        return self._date_mapper.date_at_x(x)

    # --- 内部処理 -----------------------------------------------------------
    def _on_view_changed(self) -> None:
        self._scheduler.request(geometry=True)

    def _on_scheduled_update(self, geometry_changed: bool, axis_changed: bool) -> None:
        if self._view is None:
            return
        visible_rect = self._visible_rect_provider.scene_rect()
        viewport_rect = self._visible_rect_provider.viewport_rect()
        if visible_rect is None or viewport_rect is None:
            return
        if (
            not axis_changed
            and not geometry_changed
            and self._last_scene_rect is not None
            and self._last_viewport_rect is not None
            and visible_rect == self._last_scene_rect
            and viewport_rect == self._last_viewport_rect
        ):
            return
        transform = self._view.transform() if hasattr(self._view, "transform") else QTransform()
        column_width_px = abs(transform.m11()) * self._date_mapper.column_width
        top_scene_point = (
            self._view.mapToScene(QPoint(0, self.LABEL_VIEW_MARGIN))
            if hasattr(self._view, "mapToScene")
            else QPointF(0.0, visible_rect.top())
        )
        self._today = date.today()
        context = LayerUpdateContext(
            date_mapper=self._date_mapper,
            visible_scene_rect=visible_rect,
            viewport_rect=viewport_rect,
            top_scene_y=top_scene_point.y(),
            column_width_px=column_width_px,
            transform=transform,
            theme=self._theme,
            today=self._today,
        )
        for layer in self._layers:
            layer.update(context)
        self._last_scene_rect = visible_rect
        self._last_viewport_rect = viewport_rect


__all__ = [
    "TimelineNodeGraph",
    "TimelineGridOverlay",
    "DateMapper",
]
