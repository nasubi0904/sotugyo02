from __future__ import annotations

import json

from qtpy import QtWidgets

from sotugyo import main as main_module


def test_run_application_writes_headless_exit_report(tmp_path):
    report_path = tmp_path / "exit_report.json"

    result = main_module._run_application(
        headless=True,
        auto_exit_ms=10,
        show_window=False,
        exit_report_path=str(report_path),
    )

    assert result.reason == "manual"
    assert result.exit_code == 0

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["reason"] == "manual"
    assert report["exit_code"] == 0


def test_run_application_reports_startup_error(tmp_path, monkeypatch):
    report_path = tmp_path / "error_report.json"

    class FaultyWindow(QtWidgets.QWidget):
        def __init__(self) -> None:
            super().__init__()
            raise RuntimeError("boom")

    monkeypatch.setattr(main_module, "_resolve_start_window", lambda: FaultyWindow)

    result = main_module._run_application(
        headless=True,
        auto_exit_ms=None,
        show_window=True,
        exit_report_path=str(report_path),
    )

    assert result.reason == "error"
    assert result.exit_code == 1

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["reason"] == "error"
    assert "boom" in (report.get("error_message") or "")


def test_run_application_marks_nonzero_exit_as_error(monkeypatch):
    class DummyApplication:
        _instance: "DummyApplication | None" = None

        def __init__(self, argv: list[str]):  # noqa: ARG002 - テスト用スタブ
            DummyApplication._instance = self

        @classmethod
        def instance(cls) -> "DummyApplication | None":
            return cls._instance

        def exec(self) -> int:
            return 5

        def deleteLater(self) -> None:  # pragma: no cover - Qt 互換のダミー
            pass

    monkeypatch.setattr(main_module.QtWidgets, "QApplication", DummyApplication)

    result = main_module._run_application(
        headless=False,
        auto_exit_ms=None,
        show_window=False,
        exit_report_path=None,
    )

    assert result.reason == "error"
    assert result.exit_code == 5
