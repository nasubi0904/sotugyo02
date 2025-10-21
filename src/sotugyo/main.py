"""アプリケーションのエントリポイント。"""

from __future__ import annotations

import os
import sys
from typing import Type

from PySide6.QtWidgets import QApplication


def _resolve_start_window() -> Type["StartWindow"]:
    """実行形態に応じて `StartWindow` クラスを遅延インポートする。"""

    if __package__:
        from .gui.start_window import StartWindow
    else:
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
        from sotugyo.gui.start_window import StartWindow
    return StartWindow


def main() -> int:
    """スタート画面を表示してアプリケーションを起動する。"""

    app = QApplication.instance() or QApplication(sys.argv)
    start_window_cls = _resolve_start_window()
    window = start_window_cls()
    window.show()
    return app.exec()


if __name__ == "__main__":  # pragma: no cover - 直接実行時のみ
    sys.exit(main())
