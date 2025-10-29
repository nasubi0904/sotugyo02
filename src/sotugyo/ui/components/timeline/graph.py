"""タイムライン表示コンポーネントの簡易実装。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, List, Optional

try:  # pragma: no cover - QtPy が利用できる環境では実際の実装を利用
    from qtpy import QtGui  # type: ignore
except Exception:  # pragma: no cover - テスト環境ではダミーを使用
    @dataclass
    class QColor:  # type: ignore
        """テスト用の簡易 QColor 代替。"""

        name: str

        def __str__(self) -> str:
            return self.name

        def __repr__(self) -> str:
            return f"QColor({self.name!r})"

        def __eq__(self, other: object) -> bool:
            if not isinstance(other, QColor):
                return NotImplemented
            return self.name.lower() == other.name.lower()

else:  # pragma: no cover - QtPy 環境で使用
    QColor = QtGui.QColor


class ThemeProvider:
    """タイムライン描画のテーマ情報。"""

    def __init__(self, scene_background: QColor | None = None) -> None:
        self._scene_background = scene_background or QColor("#1e1e1e")

    def scene_background_color(self) -> QColor:
        """シーン背景色を取得する。"""

        return self._scene_background

    def set_scene_background_color(self, color: QColor) -> None:
        """背景色を更新する。"""

        self._scene_background = color


class GridTileLayer:
    """タイムライン背景タイルの描画設定を保持する。"""

    def __init__(self, scene: Any, theme: ThemeProvider) -> None:
        self.scene = scene
        self.theme = theme
        self._last_signature: Optional[tuple] = None

    def set_theme(self, theme: ThemeProvider) -> None:
        """テーマ変更時に内部キャッシュを破棄する。"""

        if self.theme is not theme:
            self.theme = theme
        self._last_signature = None


class TimelineGridOverlay:
    """タイムライン背景レイヤを統合管理する。"""

    def __init__(self, view: Any, *, theme: ThemeProvider | None = None) -> None:
        self.view = view
        self.theme = theme or ThemeProvider()
        self._layers: List[Any] = []
        self._scheduler: Any = None

    # レイヤ管理 --------------------------------------------------------
    def add_layer(self, layer: Any) -> None:
        """レイヤを追加し、現在のテーマを適用する。"""

        self._layers.append(layer)
        if hasattr(layer, "set_theme"):
            layer.set_theme(self.theme)

    def set_layers(self, layers: Iterable[Any]) -> None:
        """レイヤリストを置き換える。"""

        self._layers = list(layers)
        for layer in self._layers:
            if hasattr(layer, "set_theme"):
                layer.set_theme(self.theme)

    # テーマ操作 --------------------------------------------------------
    def set_theme(self, theme: ThemeProvider) -> None:
        """テーマを置き換え、レイヤへ伝搬する。"""

        self.theme = theme
        for layer in self._layers:
            if hasattr(layer, "set_theme"):
                layer.set_theme(theme)
        self._request_refresh(force=True)

    def set_scene_background_color(self, color: QColor) -> None:
        """背景色を更新し、再描画を要求する。"""

        self.theme.set_scene_background_color(color)
        for layer in self._layers:
            if hasattr(layer, "set_theme"):
                layer.set_theme(self.theme)
        self._request_refresh(force=True)

    # スケジューラ連携 --------------------------------------------------
    def _request_refresh(self, *, force: bool = False) -> None:
        if self._scheduler is not None:
            self._scheduler.request(force=force)
