"""縞模様背景のドラッグ調整用ハンドルとコントローラ。"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QObject, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsRectItem, QGraphicsScene


class StripeBoundaryHandle(QGraphicsRectItem):
    """縞幅を調整するためのグラフィカルハンドル。"""

    HANDLE_WIDTH = 8.0

    def __init__(
        self,
        base_width: int,
        *,
        stripe_height: float,
        parent: Optional[QGraphicsItem] = None,
    ) -> None:
        super().__init__(parent)
        self._base_width = max(int(base_width), 1)
        self._stripe_height = max(float(stripe_height), 1.0)
        self._current_factor = 1
        self._callback: Optional[Callable[[int], None]] = None
        self._updating_position = False

        half_width = self.HANDLE_WIDTH / 2.0
        self.setRect(QRectF(-half_width, -self._stripe_height / 2.0, self.HANDLE_WIDTH, self._stripe_height))

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.setCursor(Qt.SizeHorCursor)
        self.setZValue(1000.0)

        pen = QPen(QColor(255, 255, 255, 220))
        pen.setCosmetic(True)
        self.setPen(pen)
        self.setBrush(QBrush(QColor(255, 255, 255, 80)))

    def base_width(self) -> int:
        """基準となる縞幅を返す。"""

        return self._base_width

    def current_factor(self) -> int:
        """現在の倍率を返す。"""

        return self._current_factor

    def set_height(self, stripe_height: float) -> None:
        """ハンドルの描画高さを更新する。"""

        sanitized = max(float(stripe_height), 1.0)
        if abs(self._stripe_height - sanitized) < 1e-3:
            return
        self._stripe_height = sanitized
        self.prepareGeometryChange()
        half_width = self.HANDLE_WIDTH / 2.0
        self.setRect(QRectF(-half_width, -self._stripe_height / 2.0, self.HANDLE_WIDTH, self._stripe_height))

    def set_factor_changed_callback(self, callback: Optional[Callable[[int], None]]) -> None:
        """倍率変更時に呼び出すコールバックを登録する。"""

        self._callback = callback

    def set_factor(self, factor: int) -> None:
        """倍率を外部から設定し位置を更新する。"""

        normalized = max(int(factor), 1)
        if normalized == self._current_factor and not self._updating_position:
            return
        target_x = float(self._base_width * normalized)
        self._updating_position = True
        try:
            self._current_factor = normalized
            super().setPos(QPointF(target_x, 0.0))
        finally:
            self._updating_position = False

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):  # type: ignore[override]
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and isinstance(value, QPointF):
            raw_x = max(float(value.x()), float(self._base_width))
            factor = max(1, round(raw_x / self._base_width))
            aligned_x = float(self._base_width * factor)
            new_position = QPointF(aligned_x, 0.0)
            previous_factor = self._current_factor
            self._current_factor = factor
            if (
                not self._updating_position
                and self._callback is not None
                and factor != previous_factor
            ):
                self._callback(factor)
            return super().itemChange(change, new_position)
        return super().itemChange(change, value)


class StripeDragController(QObject):
    """縞幅調整ハンドルを管理し倍率変更を通知するコントローラ。"""

    factor_changed = Signal(int)

    def __init__(
        self,
        scene: QGraphicsScene,
        *,
        base_width: int,
        stripe_height: int,
        initial_factor: int = 1,
    ) -> None:
        super().__init__(scene)
        self._scene = scene
        self._base_width = max(int(base_width), 1)
        self._stripe_height = max(int(stripe_height), 1)
        self._current_factor = max(int(initial_factor), 1)
        self._handles: list[StripeBoundaryHandle] = []

        self._create_handle()

    def _create_handle(self) -> None:
        handle = StripeBoundaryHandle(self._base_width, stripe_height=float(self._stripe_height))
        self._scene.addItem(handle)
        handle.set_factor(self._current_factor)
        handle.set_factor_changed_callback(self._on_handle_factor_changed)
        self._handles.append(handle)

    def _on_handle_factor_changed(self, factor: int) -> None:
        if factor == self._current_factor:
            return
        self._current_factor = factor
        self.factor_changed.emit(factor)

    def current_factor(self) -> int:
        """現在の倍率を返す。"""

        return self._current_factor

    def handles(self) -> tuple[StripeBoundaryHandle, ...]:
        """管理下のハンドル一覧を返す。"""

        return tuple(self._handles)

    def base_width(self) -> int:
        """基準縞幅を返す。"""

        return self._base_width

    def stripe_height(self) -> int:
        """縞タイル高さを返す。"""

        return self._stripe_height

    def set_stripe_height(self, stripe_height: int) -> None:
        """縞タイル高さの更新に合わせてハンドルを調整する。"""

        sanitized = max(int(stripe_height), 1)
        if sanitized == self._stripe_height:
            return
        self._stripe_height = sanitized
        for handle in self._handles:
            handle.set_height(float(self._stripe_height))

    def dispose(self) -> None:
        """ハンドルをシーンから除去し後始末を行う。"""

        for handle in self._handles:
            handle.set_factor_changed_callback(None)
            if handle.scene() is self._scene:
                self._scene.removeItem(handle)
        self._handles.clear()
        self.deleteLater()
