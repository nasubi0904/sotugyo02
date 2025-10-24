from types import SimpleNamespace

import pytest

PySide6 = pytest.importorskip("PySide6")
from PySide6.QtGui import QColor

from sotugyo.ui.components.timeline.graph import (
    GridTileLayer,
    ThemeProvider,
    TimelineGridOverlay,
)


def test_grid_tile_layer_resets_cache_on_theme_change():
    theme = ThemeProvider()
    layer = GridTileLayer(scene=None, theme=theme)
    layer._last_signature = ("cached",)  # type: ignore[attr-defined]

    layer.set_theme(ThemeProvider())

    assert layer._last_signature is None  # type: ignore[attr-defined]


def test_timeline_grid_overlay_background_update_requests_refresh():
    overlay = TimelineGridOverlay(view=None)
    calls = []
    overlay._scheduler = SimpleNamespace(  # type: ignore[assignment]
        request=lambda **kwargs: calls.append(kwargs)
    )

    original_color = overlay.theme.scene_background_color()
    overlay.set_scene_background_color(QColor("#123456"))

    assert overlay.theme.scene_background_color() != original_color
    assert calls and calls[-1].get("force") is True


def test_timeline_grid_overlay_set_theme_propagates_to_layers():
    overlay = TimelineGridOverlay(view=None)
    received = []

    class DummyLayer:
        def set_theme(self, theme):
            received.append(theme)

    new_theme = ThemeProvider()
    overlay._layers = [DummyLayer()]  # type: ignore[assignment]

    overlay.set_theme(new_theme)

    assert received == [new_theme]
