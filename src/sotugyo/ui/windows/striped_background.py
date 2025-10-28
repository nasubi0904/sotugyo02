"""NodeGraph 用の縞模様背景生成ヘルパー。"""

from __future__ import annotations

from typing import Type

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


def _resolve_stripe_width(node_cls: Type[BaseNode]) -> int:
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
    stripe_width: int,
    *,
    light_color: QColor,
    dark_color: QColor,
    border_color: QColor,
    accent_color: QColor,
) -> QPixmap:
    """縞模様用のタイル画像を生成する。"""

    tile_width = stripe_width * 2
    tile_height = stripe_width
    pixmap = QPixmap(QSize(tile_width, tile_height))
    pixmap.fill(dark_color)

    painter = QPainter(pixmap)
    painter.fillRect(0, 0, stripe_width, tile_height, light_color)

    border_pen = QPen(border_color)
    border_pen.setWidth(1)
    border_pen.setCosmetic(True)
    painter.setPen(border_pen)
    painter.drawLine(stripe_width, 0, stripe_width, tile_height)
    painter.drawLine(0, 0, 0, tile_height)

    accent_pen = QPen(accent_color)
    accent_pen.setWidth(1)
    accent_pen.setCosmetic(True)
    painter.setPen(accent_pen)
    painter.drawLine(stripe_width - 1, 0, stripe_width - 1, tile_height)

    painter.end()
    return pixmap


def apply_striped_background(graph: NodeGraph, node_cls: Type[BaseNode]) -> None:
    """ノードグラフへ縞模様背景とグリッド調整を適用する。"""

    stripe_width = _resolve_stripe_width(node_cls)
    tile = _build_stripe_tile(
        stripe_width,
        light_color=GRAPH_VIEW_STRIPE_LIGHT,
        dark_color=GRAPH_VIEW_STRIPE_DARK,
        border_color=GRAPH_VIEW_STRIPE_BORDER,
        accent_color=GRAPH_VIEW_STRIPE_ACCENT,
    )
    brush = QBrush(tile)

    graph.set_grid_mode(ViewerEnum.GRID_DISPLAY_NONE.value)
    viewer = graph.viewer()
    viewer.setBackgroundBrush(brush)
    graph.scene().setBackgroundBrush(brush)
