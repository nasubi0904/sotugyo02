"""タイムライン関連のドメインロジック。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

__all__ = [
    "DEFAULT_TIMELINE_UNIT",
    "TimelineAxis",
    "TimelineSnapSettings",
    "calculate_snap_position",
    "calculate_snap_width",
]


class TimelineAxis(str, Enum):
    """タイムラインの進行方向を表す。"""

    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"

DEFAULT_TIMELINE_UNIT: float = 320.0


@dataclass(frozen=True)
class TimelineSnapSettings:
    """タイムライン上のスナップ挙動を定義する設定。"""

    base_unit: float = DEFAULT_TIMELINE_UNIT
    column_units: int = 1
    origin_x: float = 0.0
    axis: TimelineAxis = TimelineAxis.HORIZONTAL

    def __post_init__(self) -> None:
        axis = self.axis
        if isinstance(axis, TimelineAxis):
            normalized = axis
        else:
            try:
                normalized = TimelineAxis(str(axis))
            except ValueError:
                normalized = TimelineAxis.HORIZONTAL
        object.__setattr__(self, "axis", normalized)

    @property
    def column_width(self) -> float:
        """1 枠分の幅を返す。"""

        return self.normalized_base_unit * self.normalized_column_units

    @property
    def normalized_base_unit(self) -> float:
        """無効値を考慮した基準幅。"""

        return max(1.0, float(self.base_unit))

    @property
    def normalized_column_units(self) -> int:
        """無効値を考慮した列単位。"""

        return max(1, int(self.column_units))


def calculate_snap_position(value: float, settings: TimelineSnapSettings) -> float:
    """指定座標を最も近いグリッド位置にスナップする。"""

    width = settings.column_width
    if width <= 0:
        return float(value)
    origin = float(settings.origin_x)
    relative = (float(value) - origin) / width
    index = round(relative)
    return origin + index * width


def calculate_snap_width(width: float, settings: TimelineSnapSettings) -> float:
    """ノード幅を列幅の倍数に補正する。"""

    column_width = settings.column_width
    if column_width <= 0:
        return float(width)
    units = max(1, round(float(width) / column_width))
    return column_width * units
