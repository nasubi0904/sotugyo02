"""アプリケーションのエントリポイント。"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

# --- import guard for direct script run ---
import os
import sys

if __package__:
    # パッケージとして実行された場合（python -m sotugyo.main など）
    from .gui.start_window import StartWindow
else:
    # 直接実行された場合（python main.py）
    # main.py の親（= src）を sys.path に追加し、絶対インポートに切り替える
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from sotugyo.gui.start_window import StartWindow
# --- end guard ---

def main() -> int:
    """スタート画面を表示してアプリケーションを起動する。"""

    app = QApplication.instance() or QApplication(sys.argv)
    window = StartWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":  # pragma: no cover - 直接実行時のみ
    sys.exit(main())
