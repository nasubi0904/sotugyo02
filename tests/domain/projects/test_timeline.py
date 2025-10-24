"""タイムラインスナップ設定のテスト。"""

from __future__ import annotations

import math

import importlib.util
from pathlib import Path

TIMELINE_PATH = Path(__file__).resolve().parents[3] / "src" / "sotugyo" / "domain" / "projects" / "timeline.py"
spec = importlib.util.spec_from_file_location("timeline", TIMELINE_PATH)
assert spec and spec.loader
timeline = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = timeline
spec.loader.exec_module(timeline)

TimelineSnapSettings = timeline.TimelineSnapSettings
calculate_snap_position = timeline.calculate_snap_position
calculate_snap_width = timeline.calculate_snap_width


def test_calculate_snap_position_aligns_to_nearest_grid() -> None:
    settings = TimelineSnapSettings(base_unit=100.0, column_units=2, origin_x=50.0)
    assert calculate_snap_position(145.0, settings) == 50.0
    assert calculate_snap_position(251.0, settings) == 250.0


def test_calculate_snap_position_handles_negative_origin() -> None:
    settings = TimelineSnapSettings(base_unit=80.0, column_units=1, origin_x=-40.0)
    assert calculate_snap_position(-5.0, settings) == -40.0


def test_calculate_snap_width_rounds_up_to_column_units() -> None:
    settings = TimelineSnapSettings(base_unit=120.0, column_units=3)
    width = calculate_snap_width(350.0, settings)
    assert math.isclose(width, 360.0)


def test_calculate_snap_width_ignores_invalid_base_unit() -> None:
    settings = TimelineSnapSettings(base_unit=0.0, column_units=0)
    assert calculate_snap_width(200.0, settings) == 200.0
