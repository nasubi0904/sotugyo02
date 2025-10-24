"""ノード移動時のスナップ制御。"""

from __future__ import annotations

from typing import Iterable, List, Optional, Sequence
from weakref import WeakSet

from PySide6.QtCore import QObject, QPointF, QEvent, QRectF, Qt
from PySide6.QtWidgets import QGraphicsScene, QGraphicsSceneMouseEvent

try:  # pragma: no cover - 実行環境に NodeGraphQt が存在しない場合の保険
    from NodeGraphQt import NodeGraph
except Exception:  # pragma: no cover - Fallback for 型チェック
    NodeGraph = object  # type: ignore[misc, assignment]


class NodeSnapController(QObject):
    """ノードを他ノードの端に吸着させる制御を担う。"""

    def __init__(self, graph: NodeGraph, *, threshold: float = 10.0) -> None:
        super().__init__()
        self._graph = graph
        self._threshold = max(0.0, float(threshold))
        self._enabled = True
        self._tracked_nodes: "WeakSet[object]" = WeakSet()

        self._scene: Optional[QGraphicsScene] = None
        widget = getattr(self._graph, "widget", None)
        scene_getter = getattr(widget, "scene", None)
        if callable(scene_getter):
            self._scene = scene_getter()
        if isinstance(self._scene, QGraphicsScene):
            self._scene.installEventFilter(self)

    # ------------------------------------------------------------------
    # 公開 API
    # ------------------------------------------------------------------
    def set_enabled(self, enabled: bool) -> None:
        """スナップ処理の有効／無効を切り替える。"""

        self._enabled = bool(enabled)

    def is_enabled(self) -> bool:
        """現在のスナップ有効状態を返す。"""

        return self._enabled

    def register_node(self, node: object) -> None:
        """監視対象ノードを登録する。"""

        if node is None:
            return
        self._tracked_nodes.add(node)

    def unregister_nodes(self, nodes: Iterable[object]) -> None:
        """監視対象からノード群を除外する。"""

        for node in nodes:
            if node in self._tracked_nodes:
                try:
                    self._tracked_nodes.remove(node)
                except KeyError:  # pragma: no cover - WeakSet のレース保護
                    continue

    def sync_graph_nodes(self) -> None:
        """NodeGraph が保持するノードを全て監視対象に同期する。"""

        nodes_getter = getattr(self._graph, "all_nodes", None)
        if callable(nodes_getter):
            try:
                for node in nodes_getter():
                    self.register_node(node)
            except Exception:  # pragma: no cover - NodeGraphQt 依存の例外
                return

    # ------------------------------------------------------------------
    # Qt イベントフック
    # ------------------------------------------------------------------
    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt 規約
        if not self._enabled or not isinstance(event, QGraphicsSceneMouseEvent):
            return super().eventFilter(obj, event)

        if obj is self._scene and event.type() == QEvent.GraphicsSceneMouseRelease:
            if event.button() == Qt.LeftButton:
                self._apply_snap_to_selection()

        return super().eventFilter(obj, event)

    # ------------------------------------------------------------------
    # 内部処理
    # ------------------------------------------------------------------
    def _apply_snap_to_selection(self) -> None:
        nodes = self._selected_nodes()
        if not nodes:
            return

        for node in nodes:
            self._snap_node(node)

    def _selected_nodes(self) -> Sequence[object]:
        selector = getattr(self._graph, "selected_nodes", None)
        if not callable(selector):
            return []
        try:
            return tuple(selector())
        except Exception:  # pragma: no cover - NodeGraphQt 依存の例外
            return []

    def _iter_snap_candidates(self, moving_node: object) -> List[object]:
        candidates: List[object] = []
        candidates.extend(node for node in self._tracked_nodes if node is not None)
        nodes_getter = getattr(self._graph, "all_nodes", None)
        if callable(nodes_getter):
            try:
                for node in nodes_getter():
                    if node is not None and node not in candidates:
                        candidates.append(node)
            except Exception:  # pragma: no cover - NodeGraphQt 依存の例外
                pass
        return [node for node in candidates if node is not moving_node]

    def _snap_node(self, node: object) -> None:
        bounds = self._node_bounds(node)
        if bounds is None:
            return

        width = bounds.width()
        height = bounds.height()
        original_x = bounds.left()
        original_y = bounds.top()

        best_x = original_x
        best_y = original_y
        best_dx = self._threshold + 1.0
        best_dy = self._threshold + 1.0

        for other in self._iter_snap_candidates(node):
            other_bounds = self._node_bounds(other)
            if other_bounds is None:
                continue

            best_x, best_dx = self._evaluate_horizontal_snap(
                bounds,
                width,
                other_bounds,
                best_x,
                best_dx,
            )
            best_y, best_dy = self._evaluate_vertical_snap(
                bounds,
                height,
                other_bounds,
                best_y,
                best_dy,
            )

        if best_x == original_x and best_y == original_y:
            return

        setter = getattr(node, "set_pos", None)
        if not callable(setter):
            return
        try:
            setter(best_x, best_y)
        except Exception:  # pragma: no cover - NodeGraphQt 依存の例外
            return

    def _evaluate_horizontal_snap(
        self,
        bounds: QRectF,
        width: float,
        other: QRectF,
        best_x: float,
        best_delta: float,
    ) -> tuple[float, float]:
        left = bounds.left()
        right = bounds.right()

        candidates = [
            (abs(left - other.left()), other.left()),
            (abs(left - other.right()), other.right()),
            (abs(right - other.left()), other.left() - width),
            (abs(right - other.right()), other.right() - width),
        ]

        for delta, x in candidates:
            if delta < best_delta and delta <= self._threshold:
                best_x = x
                best_delta = delta
        return best_x, best_delta

    def _evaluate_vertical_snap(
        self,
        bounds: QRectF,
        height: float,
        other: QRectF,
        best_y: float,
        best_delta: float,
    ) -> tuple[float, float]:
        top = bounds.top()
        bottom = bounds.bottom()

        candidates = [
            (abs(top - other.top()), other.top()),
            (abs(top - other.bottom()), other.bottom()),
            (abs(bottom - other.top()), other.top() - height),
            (abs(bottom - other.bottom()), other.bottom() - height),
        ]

        for delta, y in candidates:
            if delta < best_delta and delta <= self._threshold:
                best_y = y
                best_delta = delta
        return best_y, best_delta

    def _node_bounds(self, node: object) -> Optional[QRectF]:
        pos_getter = getattr(node, "pos", None)
        if not callable(pos_getter):
            return None
        try:
            pos = pos_getter()
        except Exception:  # pragma: no cover - NodeGraphQt 依存の例外
            return None

        if isinstance(pos, QPointF):
            x = float(pos.x())
            y = float(pos.y())
        else:
            try:
                x, y = map(float, pos)
            except Exception:  # pragma: no cover - 想定外フォーマット
                return None

        view = getattr(node, "view", None)
        width = self._extract_dimension(view, "width")
        height = self._extract_dimension(view, "height")
        if width <= 0.0 or height <= 0.0:
            rect_getter = getattr(view, "boundingRect", None)
            if callable(rect_getter):
                rect = rect_getter()
                width = float(rect.width())
                height = float(rect.height())

        if width <= 0.0 or height <= 0.0:
            return None

        return QRectF(x, y, width, height)

    @staticmethod
    def _extract_dimension(view: object, attribute: str) -> float:
        if view is None:
            return 0.0
        value = getattr(view, attribute, 0.0)
        try:
            return float(value)
        except Exception:  # pragma: no cover - 想定外フォーマット
            return 0.0
