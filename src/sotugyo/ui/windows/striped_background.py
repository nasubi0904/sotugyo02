"""NodeGraph 用の縞模様背景生成ヘルパー。"""

from __future__ import annotations

from typing import Iterable, Sequence, Type

from PySide6.QtCore import QSize
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QPixmap

from NodeGraphQt import NodeGraph
from NodeGraphQt.constants import ViewerEnum
from NodeGraphQt.nodes.base_node import BaseNode

from ..style import (
    GRAPH_VIEW_STRIPE_ACCENT,
    GRAPH_VIEW_STRIPE_BORDER,
    GRAPH_VIEW_STRIPE_DARK,
    GRAPH_VIEW_STRIPE_LIGHT,
)
from .stripe_overlay import StripeDragController

# 背景タイル生成時の最大幅（px）。視覚上の必要十分な範囲に抑え、Qt が巨大
# QPixmap を確保しようとしてメモリを圧迫するのを防ぐ。
_MAX_STRIPE_TILE_WIDTH = 4096
# ビューサイズに応じた可変上限を設け、ウィンドウサイズに見合った調整幅を
# 確保する。
_VIEWER_WIDTH_MULTIPLIER = 2


def resolve_stripe_width(node_cls: Type[BaseNode]) -> int:
    """基準ノードのビュー幅から縞幅を取得する。"""

    node = node_cls()
    try:
        width = int(round(node.view.width))
    except AttributeError:
        width = 160
    finally:
        del node
    return max(width, 32)


def _build_stripe_tile(
    stripe_widths: Sequence[int],
    *,
    stripe_height: int,
    light_color: QColor,
    dark_color: QColor,
    border_color: QColor,
    accent_color: QColor,
) -> QPixmap:
    """縞模様用のタイル画像を生成する。"""

    sanitized_widths: list[int] = []
    for width in stripe_widths:
        value = int(width)
        if value <= 0:
            continue
        sanitized_widths.append(max(value, 2))
    if not sanitized_widths:
        raise ValueError("stripe_widths must contain at least one positive value.")

    tile_width = sum(sanitized_widths)
    tile_height = max(int(stripe_height), 1)
    pixmap = QPixmap(QSize(tile_width, tile_height))

    # 8% 明るく／12% 暗くした変種を用意し、隣接する縞のコントラストを
    # 穏やかに保ちながら視認性を向上させる。
    light_stripe_color = light_color.lighter(108)
    dark_stripe_color = dark_color.darker(112)

    pixmap.fill(dark_stripe_color)

    painter = QPainter(pixmap)

    border_pen = QPen(border_color)
    border_pen.setWidth(1)
    border_pen.setCosmetic(True)

    accent_pen = QPen(accent_color)
    accent_pen.setWidth(1)
    accent_pen.setCosmetic(True)

    offset = 0
    painter.setPen(border_pen)
    painter.drawLine(0, 0, 0, tile_height)
    for index, width in enumerate(sanitized_widths):
        stripe_color = light_stripe_color if index % 2 == 0 else dark_stripe_color
        painter.fillRect(offset, 0, width, tile_height, stripe_color)
        offset += width
        painter.setPen(border_pen)
        painter.drawLine(offset, 0, offset, tile_height)
        if index % 2 == 0:
            accent_x = max(offset - 1, 0)
            painter.setPen(accent_pen)
            painter.drawLine(accent_x, 0, accent_x, tile_height)

    painter.end()
    return pixmap


class StripedBackgroundPattern:
    """縞幅のシーケンスを保持しブラシ生成を担うヘルパー。"""

    def __init__(self, stripe_widths: Iterable[int], *, stripe_height: int | None = None) -> None:
        widths = [max(int(width), 2) for width in stripe_widths if int(width) > 0]
        if not widths:
            raise ValueError("stripe_widths must contain at least one positive integer.")
        self._widths = widths
        height = int(stripe_height) if stripe_height is not None else widths[0]
        self._height = max(height, 2)

    @property
    def widths(self) -> tuple[int, ...]:
        """現在の縞幅シーケンスを返す。"""

        return tuple(self._widths)

    @property
    def height(self) -> int:
        """縞タイルの高さを返す。"""

        return self._height

    def total_width(self) -> int:
        """タイル全体の幅を返す。"""

        return sum(self._widths)

    def width_at(self, index: int) -> int:
        """指定インデックスの縞幅を取得する。"""

        return self._widths[index]

    def build_brush(self) -> QBrush:
        """現在の設定から背景ブラシを生成する。"""

        tile = _build_stripe_tile(
            self._widths,
            stripe_height=self._height,
            light_color=GRAPH_VIEW_STRIPE_LIGHT,
            dark_color=GRAPH_VIEW_STRIPE_DARK,
            border_color=GRAPH_VIEW_STRIPE_BORDER,
            accent_color=GRAPH_VIEW_STRIPE_ACCENT,
        )
        return QBrush(tile)


def apply_stripe_pattern(graph: NodeGraph, pattern: StripedBackgroundPattern) -> QBrush:
    """縞模様パターンから生成したブラシをグラフへ適用する。"""

    brush = pattern.build_brush()
    graph.set_grid_mode(ViewerEnum.GRID_DISPLAY_NONE.value)
    viewer = graph.viewer()
    viewer.setBackgroundBrush(brush)
    graph.scene().setBackgroundBrush(brush)
    return brush


def apply_striped_background(graph: NodeGraph, node_cls: Type[BaseNode]) -> StripedBackgroundPattern:
    """基準ノード幅から単一縞パターンを生成して適用する。"""

    stripe_width = resolve_stripe_width(node_cls)
    pattern = StripedBackgroundPattern([stripe_width], stripe_height=stripe_width)
    apply_stripe_pattern(graph, pattern)
    return pattern


def enable_stripe_dragging(
    graph: NodeGraph,
    node_cls: Type[BaseNode],
    pattern: StripedBackgroundPattern,
) -> StripeDragController:
    """縞幅をドラッグで変更できるようにハンドルを設定する。"""

    base_width = resolve_stripe_width(node_cls)
    scene = graph.scene()
    initial_factor = 1
    if pattern.widths:
        initial_factor = max(int(round(pattern.widths[0] / base_width)), 1)
    controller = StripeDragController(
        scene,
        base_width=base_width,
        stripe_height=pattern.height,
        initial_factor=initial_factor,
    )

    def _apply_factor(factor: int) -> None:
        requested_factor = max(int(factor), 1)
        viewer = graph.viewer()
        viewer_size = viewer.size()
        max_dimension = max(viewer_size.width(), viewer_size.height())
        if max_dimension <= 0:
            max_dimension = base_width
        dynamic_limit = max_dimension * _VIEWER_WIDTH_MULTIPLIER
        max_width = max(base_width, min(dynamic_limit, _MAX_STRIPE_TILE_WIDTH))
        max_factor = max(max_width // base_width, 1)
        clamped_factor = min(requested_factor, max_factor)
        width = base_width * clamped_factor
        if clamped_factor != requested_factor:
            controller.set_factor(clamped_factor)
        new_pattern = StripedBackgroundPattern([width])
        apply_stripe_pattern(graph, new_pattern)
        controller.set_stripe_height(new_pattern.height)

    controller.factor_changed.connect(_apply_factor)
    return controller
