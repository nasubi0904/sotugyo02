"""アプリケーションのエントリポイント。"""

from __future__ import annotations

import os
import sys
from typing import Type

from qtpy import QtWidgets


# 起動時に適用するスタイルプロファイル名。
# 使用可能な候補:
#   - "dark": 既定のダークテーマ
#   - "light": 明るいライトテーマ
#   - "windows": スタイルシートを適用せず Windows 既定の外観を維持
# `ui.style.available_style_profiles()` で最新の候補一覧を確認し、好みの
# テーマに差し替えることができる。
DEFAULT_STYLE_PROFILE = "windows"


def _ensure_package_root() -> str:
    """スクリプト実行時にパッケージルートを ``sys.path`` に追加する。"""

    package_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if package_root not in sys.path:
        sys.path.insert(0, package_root)
    return package_root


def _resolve_start_window() -> Type["StartWindow"]:
    """実行形態に応じて `StartWindow` クラスを遅延インポートする。"""

    if __package__:
        from .ui.windows.views.start import StartWindow
    else:
        _ensure_package_root()
        from sotugyo.ui.windows.views.start import StartWindow
    return StartWindow


def _apply_style_profile(profile_name: str) -> None:
    """メインループ開始前にスタイルプロファイルを適用する。"""

    if __package__:
        from .ui.style import set_style_profile
    else:
        _ensure_package_root()
        from sotugyo.ui.style import set_style_profile

    set_style_profile(profile_name)


def main() -> int:
    """スタート画面を表示してアプリケーションを起動する。"""

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    _apply_style_profile(DEFAULT_STYLE_PROFILE)
    start_window_cls = _resolve_start_window()
    window = start_window_cls()
    window.show()
    return app.exec()


if __name__ == "__main__":  # pragma: no cover - 直接実行時のみ
    sys.exit(main())
