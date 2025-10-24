"""タイムラインスナップ制御。"""

from __future__ import annotations

from dataclasses import replace
from typing import Callable, Iterable, Optional

from ....domain.projects.timeline import (
    TimelineSnapSettings,
    calculate_snap_position,
    calculate_snap_width,
)


class TimelineSnapController:
    """NodeGraph の座標をタイムライン枠にスナップさせる。"""

    def __init__(
        self,
        graph,
        *,
        settings: TimelineSnapSettings | None = None,
        should_snap: Optional[Callable[[object], bool]] = None,
        modified_callback: Optional[Callable[[bool], None]] = None,
    ) -> None:
        self._graph = graph
        self._settings = settings or TimelineSnapSettings()
        self._should_snap = should_snap or (lambda node: True)
        self._modified_callback = modified_callback
        self._processing = False

    @property
    def settings(self) -> TimelineSnapSettings:
        return self._settings

    @property
    def column_width(self) -> float:
        return self._settings.column_width

    def set_origin_x(self, value: float) -> None:
        self._settings = replace(self._settings, origin_x=float(value))

    def set_column_units(self, units: int) -> bool:
        normalized = max(1, int(units))
        if normalized == self._settings.normalized_column_units:
            return False
        self._settings = replace(self._settings, column_units=normalized)
        return True

    def handle_nodes_moved(self, node_data) -> None:
        if self._processing:
            return
        changed = False
        for node_view in node_data.keys():
            node = self._graph.get_node_by_id(getattr(node_view, "id", None))
            if node is None or not self._should_snap(node):
                continue
            if self._snap_node_position(node):
                changed = True
        if changed:
            self._notify_modified()

    def handle_property_changed(self, node, prop_name: str, value: object) -> bool:
        if self._processing or not self._should_snap(node):
            return False
        if prop_name != "width":
            return False
        width = self._to_float(value)
        if width is None:
            return False
        changed = self._snap_node_width(node, width_override=width)
        if changed:
            self._notify_modified()
        return changed

    def snap_nodes(self, nodes: Iterable[object]) -> bool:
        if self._processing:
            return False
        changed = False
        for node in nodes:
            if not self._should_snap(node):
                continue
            if self._snap_node_position(node):
                changed = True
            if self._snap_node_width(node):
                changed = True
        if changed:
            self._notify_modified()
        return changed

    def _snap_node_position(self, node) -> bool:
        pos_getter = getattr(node, "pos", None)
        if not callable(pos_getter):
            return False
        try:
            pos = pos_getter()
        except Exception:  # pragma: no cover - NodeGraphQt 依存
            return False
        if not isinstance(pos, (list, tuple)) or len(pos) < 2:
            return False
        try:
            current_x = float(pos[0])
            current_y = float(pos[1])
        except (TypeError, ValueError):
            return False
        target_x = calculate_snap_position(current_x, self._settings)
        if abs(target_x - current_x) < 0.5:
            return False
        self._apply_node_position(node, target_x, current_y)
        return True

    def _snap_node_width(self, node, *, width_override: float | None = None) -> bool:
        width_value = width_override
        if width_value is None:
            view = getattr(node, "view", None)
            width_value = self._to_float(getattr(view, "width", None))
        if width_value is None:
            return False
        target_width = calculate_snap_width(width_value, self._settings)
        if abs(target_width - width_value) < 0.5:
            return False
        self._apply_node_width(node, target_width)
        return True

    def _apply_node_position(self, node, target_x: float, target_y: float) -> None:
        self._processing = True
        try:
            model = getattr(node, "model", None)
            if model is not None:
                model.set_property("pos", [target_x, target_y])
            view = getattr(node, "view", None)
            if view is not None:
                setattr(view, "xy_pos", [target_x, target_y])
                move = getattr(view, "setPos", None)
                if callable(move):
                    move(target_x, target_y)
        finally:
            self._processing = False

    def _apply_node_width(self, node, target_width: float) -> None:
        self._processing = True
        try:
            model = getattr(node, "model", None)
            if model is not None:
                model.set_property("width", target_width)
            view = getattr(node, "view", None)
            if view is not None:
                setattr(view, "width", target_width)
                redraw = getattr(view, "draw_node", None)
                if callable(redraw):
                    redraw()
                updater = getattr(view, "update", None)
                if callable(updater):
                    updater()
        finally:
            self._processing = False

    @staticmethod
    def _to_float(value: object) -> float | None:
        try:
            return float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None

    def _notify_modified(self) -> None:
        if callable(self._modified_callback):
            self._modified_callback(True)
