"""タイムライン描画向け NodeGraph 拡張。"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Callable, Dict, Iterable, Optional, Tuple, Union

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
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QImage,
    QPainter,
    QPen,
    QPixmap,
    QTransform,
)
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsSimpleTextItem,
)
from NodeGraphQt import NodeGraph

from ....domain.projects.timeline import DEFAULT_TIMELINE_UNIT, TimelineAxis

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
class _LabelItem:
    label: QGraphicsSimpleTextItem


@dataclass
class LayerUpdateContext:
    """レイヤ更新に必要な最小限情報。"""

    date_mapper: "DateMapper"
    visible_scene_rect: QRectF
    viewport_rect: QRect
    top_scene_y: float
    left_scene_x: float
    axis_unit_px: float
    transform: QTransform
    theme: "ThemeProvider"
    today: date
    view: Optional[object]


class DateMapper:
    """時間軸の唯一の情報源。"""

    def __init__(
        self,
        *,
        start_date: Optional[date] = None,
        column_width: float = DEFAULT_TIMELINE_UNIT,
        column_units: int = 1,
        origin_x: float = 0.0,
        orientation: TimelineAxis = TimelineAxis.HORIZONTAL,
    ) -> None:
        self._start_date = start_date or date.today()
        self._column_width = max(1.0, float(column_width))
        self._column_units = max(1, int(column_units))
        self._origin = float(origin_x)
        self._orientation = (
            orientation if isinstance(orientation, TimelineAxis) else TimelineAxis(orientation)
        )

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
        return self._origin

    @property
    def origin_y(self) -> float:
        return self._origin

    @property
    def orientation(self) -> TimelineAxis:
        return self._orientation

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
        if math.isclose(normalized, self._origin):
            return False
        self._origin = normalized
        return True

    def set_origin_y(self, value: float) -> bool:
        return self.set_origin_x(value)

    def set_orientation(self, value: TimelineAxis) -> bool:
        normalized = value if isinstance(value, TimelineAxis) else TimelineAxis(value)
        if normalized == self._orientation:
            return False
        self._orientation = normalized
        return True

    def date_to_index(self, value: date) -> float:
        delta_days = (value - self._start_date).days
        return delta_days / self._column_units

    def index_to_date(self, index: int) -> date:
        return self._start_date + timedelta(days=index * self._column_units)

    def index_to_x(self, index: float) -> float:
        return self._origin + index * self._column_width

    def index_to_y(self, index: float) -> float:
        return self.index_to_x(index)

    def date_to_x(self, value: date) -> float:
        return self.index_to_x(self.date_to_index(value))

    def date_to_y(self, value: date) -> float:
        return self.index_to_y(self.date_to_index(value))

    def x_to_index(self, value: float) -> float:
        return (float(value) - self._origin) / self._column_width

    def y_to_index(self, value: float) -> float:
        return self.x_to_index(value)

    def x_to_date(self, value: float) -> date:
        index = self.x_to_index(value)
        nearest_index = int(round(index))
        return self.index_to_date(nearest_index)

    def y_to_date(self, value: float) -> date:
        return self.x_to_date(value)

    def index_at_x(self, value: float) -> float:
        return self.x_to_index(value)

    def date_at_index(self, index: int) -> date:
        return self.index_to_date(index)

    def date_at_x(self, value: float) -> date:
        return self.x_to_date(value)

    def index_at_y(self, value: float) -> float:
        return self.y_to_index(value)

    def date_at_y(self, value: float) -> date:
        return self.y_to_date(value)


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
        self._scene_background_color = QColor(14, 20, 36)

    @property
    def label_font(self) -> QFont:
        return self._label_font

    def scene_background_color(self) -> QColor:
        return QColor(self._scene_background_color)

    def scene_background_brush(self) -> QBrush:
        return QBrush(self.scene_background_color())

    def set_scene_background_color(
        self, color: Union[QColor, Tuple[int, int, int], Tuple[int, int, int, int]]
    ) -> None:
        self._scene_background_color = QColor(color)

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

    def set_theme(self, theme: ThemeProvider) -> None:
        self._theme = theme
        self._on_theme_changed()

    def _on_theme_changed(self) -> None:
        return


class GridTileLayer(_BaseLayer):
    """列単位の背景パターンと縦グリッド線を描画する。"""

    PADDING = 2

    def __init__(self, scene, theme: ThemeProvider) -> None:
        super().__init__(scene, theme)
        self._last_signature: Optional[tuple] = None

    def _on_theme_changed(self) -> None:
        self._last_signature = None

    def clear_cache(self) -> None:
        self._last_signature = None

    def update(self, context: LayerUpdateContext) -> None:  # pragma: no cover - NodeGraphQt 依存
        if context.visible_scene_rect is None or context.viewport_rect is None:
            return
        view = getattr(context, "view", None)
        if view is None:
            return
        if self._scene is not None:
            try:
                self._scene.setBackgroundBrush(self._theme.scene_background_brush())
            except Exception:
                pass
        pixmap = self._render_background_pixmap(context, view)
        if pixmap is None:
            try:
                view.setBackgroundBrush(self._theme.scene_background_brush())
            except Exception:
                LOGGER.debug("背景ブラシのリセットに失敗", exc_info=True)
            return
        try:
            view.setBackgroundBrush(QBrush(pixmap))
        except Exception:
            LOGGER.debug("背景ブラシの設定に失敗", exc_info=True)

    def _iter_required_indexes(self, context: LayerUpdateContext) -> Iterable[int]:
        mapper = context.date_mapper
        rect = context.visible_scene_rect
        if mapper.orientation == TimelineAxis.HORIZONTAL:
            min_index = math.floor(mapper.index_at_x(rect.left()))
            max_index = math.ceil(mapper.index_at_x(rect.right()))
        else:
            min_index = math.floor(mapper.index_at_y(rect.top()))
            max_index = math.ceil(mapper.index_at_y(rect.bottom()))
        start = int(min_index) - self.PADDING
        end = int(max_index) + self.PADDING
        return range(start, end + 1)

    def _render_background_pixmap(self, context: LayerUpdateContext, view) -> Optional[QPixmap]:
        viewport_rect = context.viewport_rect
        width = max(1, viewport_rect.width())
        height = max(1, viewport_rect.height())
        indexes = list(self._iter_required_indexes(context))
        mapper = context.date_mapper
        rect = context.visible_scene_rect
        signature = (
            indexes[0] if indexes else None,
            indexes[-1] if indexes else None,
            round(rect.left(), 3),
            round(rect.right(), 3),
            round(rect.top(), 3),
            round(rect.bottom(), 3),
            round(mapper.column_width, 3),
            mapper.column_units,
            mapper.start_date.toordinal(),
            context.today.toordinal(),
            width,
            height,
            round(context.transform.m11(), 5),
            round(context.transform.m22(), 5),
            mapper.orientation.value,
        )
        if signature == self._last_signature:
            return None
        self._last_signature = signature

        image = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
        image.fill(self._theme.scene_background_color())

        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        full_rect = QRect(0, 0, width, height)
        if mapper.orientation == TimelineAxis.HORIZONTAL:
            scene_top = rect.top()
            for index in indexes:
                left_scene = mapper.index_to_x(index)
                right_scene = mapper.index_to_x(index + 1)
                left_point = view.mapFromScene(QPointF(left_scene, scene_top))
                right_point = view.mapFromScene(QPointF(right_scene, scene_top))
                left_x = left_point.x()
                right_x = right_point.x()
                if right_x < left_x:
                    left_x, right_x = right_x, left_x
                column_left = int(math.floor(left_x))
                column_right = int(math.ceil(right_x))
                column_width = max(1, column_right - column_left)
                target_date = mapper.date_at_index(index)
                is_weekend = target_date.weekday() >= 5
                is_today = target_date == context.today
                fill_rect = QRect(column_left, 0, column_width, height).intersected(full_rect)
                if not fill_rect.isEmpty():
                    painter.fillRect(
                        fill_rect,
                        self._theme.background_brush(
                            is_today=is_today,
                            is_weekend=is_weekend,
                            is_even=index % 2 == 0,
                        ),
                    )
                line_x = max(0, min(width - 1, column_left))
                painter.setPen(
                    self._theme.grid_pen(is_today=is_today, is_weekend=is_weekend)
                )
                painter.drawLine(line_x, 0, line_x, height)

            if indexes:
                last_index = indexes[-1] + 1
                right_scene = mapper.index_to_x(last_index)
                right_point = view.mapFromScene(QPointF(right_scene, scene_top))
                line_x = int(round(right_point.x()))
                if 0 <= line_x <= width:
                    painter.setPen(
                        self._theme.grid_pen(is_today=False, is_weekend=False)
                    )
                    painter.drawLine(line_x, 0, line_x, height)
        else:
            scene_left = rect.left()
            for index in indexes:
                top_scene = mapper.index_to_y(index)
                bottom_scene = mapper.index_to_y(index + 1)
                top_point = view.mapFromScene(QPointF(scene_left, top_scene))
                bottom_point = view.mapFromScene(QPointF(scene_left, bottom_scene))
                top_y = top_point.y()
                bottom_y = bottom_point.y()
                if bottom_y < top_y:
                    top_y, bottom_y = bottom_y, top_y
                row_top = int(math.floor(top_y))
                row_bottom = int(math.ceil(bottom_y))
                row_height = max(1, row_bottom - row_top)
                target_date = mapper.date_at_index(index)
                is_weekend = target_date.weekday() >= 5
                is_today = target_date == context.today
                fill_rect = QRect(0, row_top, width, row_height).intersected(full_rect)
                if not fill_rect.isEmpty():
                    painter.fillRect(
                        fill_rect,
                        self._theme.background_brush(
                            is_today=is_today,
                            is_weekend=is_weekend,
                            is_even=index % 2 == 0,
                        ),
                    )
                line_y = max(0, min(height - 1, row_top))
                painter.setPen(
                    self._theme.grid_pen(is_today=is_today, is_weekend=is_weekend)
                )
                painter.drawLine(0, line_y, width, line_y)

            if indexes:
                last_index = indexes[-1] + 1
                bottom_scene = mapper.index_to_y(last_index)
                bottom_point = view.mapFromScene(QPointF(scene_left, bottom_scene))
                line_y = int(round(bottom_point.y()))
                if 0 <= line_y <= height:
                    painter.setPen(
                        self._theme.grid_pen(is_today=False, is_weekend=False)
                    )
                    painter.drawLine(0, line_y, width, line_y)

        painter.end()
        return QPixmap.fromImage(image)


class AxisLabelLayer(_BaseLayer):
    """列ヘッダーのラベルを管理する。"""

    MIN_LABEL_SPACING = 80  # ピクセル

    def __init__(self, scene, theme: ThemeProvider, formatter: LabelFormatter) -> None:
        super().__init__(scene, theme)
        self._formatter = formatter
        self._labels: Dict[int, _LabelItem] = {}

    def _on_theme_changed(self) -> None:
        for label_item in self._labels.values():
            label_item.label.setFont(self._theme.label_font)

    def update(self, context: LayerUpdateContext) -> None:  # pragma: no cover - NodeGraphQt 依存
        if self._scene is None:
            return
        if context.visible_scene_rect is None or context.viewport_rect is None:
            return
        axis_unit_px = max(1.0, context.axis_unit_px)
        step = max(1, int(math.ceil(self.MIN_LABEL_SPACING / axis_unit_px)))
        mapper = context.date_mapper
        rect = context.visible_scene_rect
        if mapper.orientation == TimelineAxis.HORIZONTAL:
            raw_start = int(math.floor(mapper.index_at_x(rect.left()))) - 1
            end_index = int(math.ceil(mapper.index_at_x(rect.right()))) + 1
        else:
            raw_start = int(math.floor(mapper.index_at_y(rect.top()))) - 1
            end_index = int(math.ceil(mapper.index_at_y(rect.bottom()))) + 1
        if step > 1:
            adjusted_start = raw_start - (raw_start % step)
        else:
            adjusted_start = raw_start
        indexes = list(range(adjusted_start, end_index + 1, step))
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
        if mapper.orientation == TimelineAxis.HORIZONTAL:
            x = mapper.index_to_x(index)
            label_item.setPos(x, context.top_scene_y)
        else:
            y = mapper.index_to_y(index)
            bounding = label_item.boundingRect()
            offset_y = bounding.height() / 2.0
            label_item.setPos(context.left_scene_x, y - offset_y)


class MarkerLayer(_BaseLayer):
    """今日ラインなどの強調表示。"""

    def __init__(self, scene, theme: ThemeProvider) -> None:
        super().__init__(scene, theme)
        self._line: Optional[QGraphicsLineItem] = None

    def _on_theme_changed(self) -> None:
        if self._line is not None:
            self._line.setPen(self._theme.today_marker_pen())

    def update(self, context: LayerUpdateContext) -> None:  # pragma: no cover - NodeGraphQt 依存
        if self._scene is None or context.visible_scene_rect is None:
            return
        mapper = context.date_mapper
        rect = context.visible_scene_rect
        if mapper.orientation == TimelineAxis.HORIZONTAL:
            today_pos = mapper.date_to_x(context.today)
            line_args = (today_pos, rect.top(), today_pos, rect.bottom())
        else:
            today_pos = mapper.date_to_y(context.today)
            line_args = (rect.left(), today_pos, rect.right(), today_pos)
        if self._line is None:
            self._line = QGraphicsLineItem(*line_args)
            self._line.setPen(self._theme.today_marker_pen())
            self._line.setZValue(10)
            self._line.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            self._scene.addItem(self._line)
        else:
            self._line.setLine(*line_args)
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

    def __init__(self, view, *, axis: TimelineAxis = TimelineAxis.HORIZONTAL) -> None:
        super().__init__(view)
        self._view = None
        self._scene = None
        self._date_mapper = DateMapper(orientation=axis)
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
        if self._scene is not None:
            try:
                self._scene.setBackgroundBrush(self._theme.scene_background_brush())
            except Exception:
                LOGGER.debug("シーン背景ブラシの初期化に失敗", exc_info=True)
        self._visible_rect_provider.set_view(view)
        self._scheduler.request(geometry=True, axis=True)

    @property
    def theme(self) -> ThemeProvider:
        return self._theme

    def set_theme(self, theme: ThemeProvider) -> None:
        self._theme = theme
        self._apply_theme()

    @property
    def axis(self) -> TimelineAxis:
        return self._date_mapper.orientation

    def set_axis_orientation(self, axis: TimelineAxis) -> None:
        if self._date_mapper.set_orientation(axis):
            if self._grid_layer is not None:
                self._grid_layer.clear_cache()
            self._scheduler.request(force=True)

    def set_scene_background_color(
        self, color: Union[QColor, Tuple[int, int, int], Tuple[int, int, int, int]]
    ) -> None:
        self._theme.set_scene_background_color(color)
        self._apply_theme()

    def set_start_date(self, start: date) -> None:
        if self._date_mapper.set_start_date(start):
            self._today = date.today()
            self._scheduler.request(axis=True)

    def set_origin_x(self, value: float) -> None:
        if self._date_mapper.set_origin_x(value):
            self._scheduler.request(axis=True)

    def set_origin_y(self, value: float) -> None:
        self.set_origin_x(value)

    def set_column_width(self, width: float) -> None:
        if self._date_mapper.set_column_width(width):
            self._scheduler.request(axis=True)

    def set_column_units(self, units: int) -> None:
        """列単位数を設定する。

        互換性維持のため、従来の ``set_units`` をラップする。
        """
        self.set_units(units)

    def set_units(self, units: int) -> None:
        if self._date_mapper.set_column_units(units):
            self._scheduler.request(axis=True)

    def update(self, force: bool = False) -> None:
        if force:
            self._scheduler.request(force=True)
        else:
            self._scheduler.request(geometry=True)

    def get_snap_coordinate(self, value: Union[date, int, float]) -> float:
        mapper = self._date_mapper
        if isinstance(value, date):
            return (
                mapper.date_to_x(value)
                if mapper.orientation == TimelineAxis.HORIZONTAL
                else mapper.date_to_y(value)
            )
        numeric = float(value)
        return (
            mapper.index_to_x(numeric)
            if mapper.orientation == TimelineAxis.HORIZONTAL
            else mapper.index_to_y(numeric)
        )

    def get_snap_x(self, value: Union[date, int, float]) -> float:
        return self.get_snap_coordinate(value)

    def get_snap_y(self, value: Union[date, int, float]) -> float:
        return self.get_snap_coordinate(value)

    def get_snap_date(self, value: float) -> date:
        mapper = self._date_mapper
        return (
            mapper.date_at_x(value)
            if mapper.orientation == TimelineAxis.HORIZONTAL
            else mapper.date_at_y(value)
        )

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
        if self._date_mapper.orientation == TimelineAxis.HORIZONTAL:
            axis_unit_px = abs(transform.m11()) * self._date_mapper.column_width
        else:
            axis_unit_px = abs(transform.m22()) * self._date_mapper.column_width
        if hasattr(self._view, "mapToScene"):
            top_scene_point = self._view.mapToScene(QPoint(0, self.LABEL_VIEW_MARGIN))
            left_scene_point = self._view.mapToScene(QPoint(self.LABEL_VIEW_MARGIN, 0))
        else:
            top_scene_point = QPointF(visible_rect.left(), visible_rect.top())
            left_scene_point = QPointF(visible_rect.left(), visible_rect.top())
        self._today = date.today()
        context = LayerUpdateContext(
            date_mapper=self._date_mapper,
            visible_scene_rect=visible_rect,
            viewport_rect=viewport_rect,
            top_scene_y=top_scene_point.y(),
            left_scene_x=left_scene_point.x(),
            axis_unit_px=axis_unit_px,
            transform=transform,
            theme=self._theme,
            today=self._today,
            view=self._view,
        )
        for layer in self._layers:
            layer.update(context)
        self._last_scene_rect = visible_rect
        self._last_viewport_rect = viewport_rect

    def _apply_theme(self) -> None:
        if self._scene is not None:
            try:
                self._scene.setBackgroundBrush(self._theme.scene_background_brush())
            except Exception:
                LOGGER.debug("シーン背景ブラシの再設定に失敗", exc_info=True)
        for layer in self._layers:
            if layer is not None:
                layer.set_theme(self._theme)
        self._scheduler.request(force=True)


__all__ = [
    "TimelineNodeGraph",
    "TimelineGridOverlay",
    "DateMapper",
]
