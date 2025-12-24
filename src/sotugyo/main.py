"""アプリケーションのエントリポイント。"""

from __future__ import annotations

import os
import sys
import json
from dataclasses import dataclass
from typing import Literal, Type

from qtpy import QtWidgets


# 起動時に適用するスタイルプロファイル名。
# 使用可能な候補:
#   - "dark": 既定のダークテーマ
#   - "light": 明るいライトテーマ
#   - "windows": スタイルシートを適用せず Windows 既定の外観を維持
# `ui.style.available_style_profiles()` で最新の候補一覧を確認し、好みの
# テーマに差し替えることができる。
DEFAULT_STYLE_PROFILE = "windows"


ExitReason = Literal["manual", "auto_exit", "error"]


@dataclass
class MainRunResult:
    """`main` 実行結果の概要。"""

    exit_code: int
    reason: ExitReason
    error_message: str | None = None


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


def _parse_auto_exit_delay(env_value: str | None) -> int | None:
    """環境変数から自動終了までの遅延時間をミリ秒で取得する。"""

    if not env_value:
        return None
    try:
        delay = int(env_value)
    except ValueError:
        return None
    return max(delay, 0)


def _write_exit_report(path: str, result: MainRunResult) -> None:
    """終了結果を JSON で出力する。"""

    payload = {
        "exit_code": result.exit_code,
        "reason": result.reason,
        "error_message": result.error_message,
    }
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, indent=2)


def _run_application(
    *,
    headless: bool,
    auto_exit_ms: int | None,
    show_window: bool,
    exit_report_path: str | None,
) -> MainRunResult:
    """Qt アプリケーションを起動し、終了理由を判別する。"""

    exit_reason: dict[str, ExitReason] = {"value": "manual"}

    if headless:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    try:
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    except Exception as exc:  # pragma: no cover - 環境依存エラーの保険
        result = MainRunResult(exit_code=1, reason="error", error_message=str(exc))
        if exit_report_path:
            _write_exit_report(exit_report_path, result)
        return result

    _apply_style_profile(DEFAULT_STYLE_PROFILE)

    window = None
    if show_window:
        try:
            start_window_cls = _resolve_start_window()
            window = start_window_cls()
            window.show()
        except Exception as exc:
            result = MainRunResult(exit_code=1, reason="error", error_message=str(exc))
            if exit_report_path:
                _write_exit_report(exit_report_path, result)
            return result

    if auto_exit_ms is not None:
        from qtpy import QtCore

        def _quit_application() -> None:
            exit_reason["value"] = "auto_exit"
            app.quit()

        QtCore.QTimer.singleShot(auto_exit_ms, _quit_application)

    try:
        exit_code = app.exec()
    except Exception as exc:  # pragma: no cover - イベントループ実行時の異常系
        result = MainRunResult(exit_code=1, reason="error", error_message=str(exc))
    else:
        reason = exit_reason["value"]
        if exit_code != 0 and reason == "manual":
            reason = "error"
        result = MainRunResult(exit_code=exit_code, reason=reason)

    if exit_report_path:
        _write_exit_report(exit_report_path, result)

    # Qt オブジェクトを確実に破棄する
    if window is not None:
        window.deleteLater()
    app.deleteLater()

    return result


def main() -> int:
    """スタート画面を表示してアプリケーションを起動する。"""

    headless = os.environ.get("SOTUGYO_HEADLESS_TEST", "0") == "1"
    auto_exit_ms = _parse_auto_exit_delay(os.environ.get("SOTUGYO_AUTO_EXIT_MS"))
    show_window = os.environ.get("SOTUGYO_SKIP_START_WINDOW", "0") != "1"
    exit_report_path = os.environ.get("SOTUGYO_EXIT_REPORT_PATH")

    result = _run_application(
        headless=headless,
        auto_exit_ms=auto_exit_ms,
        show_window=show_window,
        exit_report_path=exit_report_path,
    )
    return result.exit_code


if __name__ == "__main__":  # pragma: no cover - 直接実行時のみ
    sys.exit(main())
