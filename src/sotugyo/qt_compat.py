"""Qt.py 互換モジュールのエイリアスを提供するユーティリティ。"""
from __future__ import annotations

import sys
from types import ModuleType
from typing import Any

from qtpy import QtCore, QtGui, QtWidgets

try:
    from qtpy import QtSvg  # type: ignore
except ImportError:  # pragma: no cover - QtSvg が無効な環境向けフォールバック
    QtSvg = None  # type: ignore


class _QtCompat:
    """QtCompat 互換 API を提供するヘルパー。"""

    class QHeaderView:
        """Qt.py が提供する QHeaderView 互換ラッパー。"""

        @staticmethod
        def setSectionResizeMode(header: Any, mode: Any) -> None:
            setter = getattr(header, "setSectionResizeMode", None)
            if callable(setter):
                setter(mode)
                return
            fallback = getattr(header, "setResizeMode", None)
            if callable(fallback):
                fallback(mode)

        @staticmethod
        def setResizeMode(header: Any, mode: Any) -> None:
            setter = getattr(header, "setResizeMode", None)
            if callable(setter):
                setter(mode)
                return
            fallback = getattr(header, "setSectionResizeMode", None)
            if callable(fallback):
                fallback(mode)


def ensure_qt_module_alias() -> None:
    """NodeGraphQt が期待する ``Qt`` 名前空間を QtPy から構築する。"""

    if "Qt" in sys.modules:
        return

    qt_module = ModuleType("Qt")
    qt_module.QtCore = QtCore
    qt_module.QtGui = QtGui
    qt_module.QtWidgets = QtWidgets
    qt_module.QtCompat = _QtCompat()
    if QtSvg is not None:
        qt_module.QtSvg = QtSvg
    else:  # pragma: no cover - QtSvg 非対応環境では参照時に例外を送出する
        class _MissingQtSvg(ModuleType):
            def __getattr__(self, item: str) -> Any:  # type: ignore[override]
                raise ImportError(
                    "QtSvg is not available in the current Qt binding."
                )

        qt_module.QtSvg = _MissingQtSvg("QtSvg")
    sys.modules["Qt"] = qt_module


__all__ = ["ensure_qt_module_alias"]
