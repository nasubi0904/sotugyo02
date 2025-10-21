"""アプリケーションのエントリポイント。"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .gui.start_window import StartWindow


def main() -> int:
    """スタート画面を表示してアプリケーションを起動する。"""

    app = QApplication.instance() or QApplication(sys.argv)
    window = StartWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":  # pragma: no cover - 直接実行時のみ
    sys.exit(main())
