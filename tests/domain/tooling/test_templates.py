"""テンプレート探索ロジックのテスト。"""

from __future__ import annotations

import os
from pathlib import Path
import sys
import types

import pytest

SRC_ROOT = Path(__file__).resolve().parents[3] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

original_pyside6 = sys.modules.get("PySide6")
original_pyside6_qtcore = sys.modules.get("PySide6.QtCore")

if "PySide6" not in sys.modules:
    stub_module = types.ModuleType("PySide6")
    qtcore_module = types.ModuleType("PySide6.QtCore")

    class _DummyQSettings:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def beginGroup(self, *args, **kwargs) -> None:
            return None

        def childGroups(self) -> list[str]:
            return []

        def value(self, *args, **kwargs):
            return None

        def endGroup(self) -> None:
            return None

        def setValue(self, *args, **kwargs) -> None:
            return None

        def sync(self) -> None:
            return None

        def contains(self, *args, **kwargs) -> bool:
            return False

        def remove(self, *args, **kwargs) -> None:
            return None

    qtcore_module.QSettings = _DummyQSettings  # type: ignore[attr-defined]
    stub_module.QtCore = qtcore_module  # type: ignore[attr-defined]
    sys.modules["PySide6"] = stub_module
    sys.modules["PySide6.QtCore"] = qtcore_module

from sotugyo.domain.tooling.templates import catalog

if original_pyside6 is None:
    sys.modules.pop("PySide6", None)
else:
    sys.modules["PySide6"] = original_pyside6

if original_pyside6_qtcore is None:
    sys.modules.pop("PySide6.QtCore", None)
else:
    sys.modules["PySide6.QtCore"] = original_pyside6_qtcore


def _force_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(catalog.sys, "platform", "win32", raising=False)


def test_discover_3ds_max_from_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _force_windows(monkeypatch)
    install_root = tmp_path / "Autodesk"
    install_dir = install_root / "Autodesk 3ds Max 2024"
    install_dir.mkdir(parents=True)
    executable = install_dir / "3dsmax.exe"
    executable.write_text("", encoding="utf-8")

    monkeypatch.setitem(os.environ, "AUTODESK_3DSMAX_DIR", str(install_root))
    monkeypatch.delenv("PROGRAMFILES", raising=False)

    candidates = catalog.discover_installations("autodesk.3ds_max")

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.executable_path == executable
    assert candidate.version == "2024"
    assert "3ds Max" in candidate.display_name


def test_discover_photoshop_from_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _force_windows(monkeypatch)
    install_root = tmp_path / "Adobe"
    install_dir = install_root / "Adobe Photoshop 2025"
    install_dir.mkdir(parents=True)
    executable = install_dir / "Photoshop.exe"
    executable.write_text("", encoding="utf-8")

    monkeypatch.setitem(os.environ, "ADOBE_PHOTOSHOP_DIR", str(install_root))
    monkeypatch.delenv("PROGRAMFILES", raising=False)

    candidates = catalog.discover_installations("adobe.photoshop")

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.executable_path == executable
    assert candidate.version == "2025"
    assert "Photoshop" in candidate.display_name


def test_discover_blender_returns_empty_when_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _force_windows(monkeypatch)
    monkeypatch.delenv("BLENDER_DIR", raising=False)
    monkeypatch.setitem(os.environ, "PROGRAMFILES", str(tmp_path / "ProgramFiles"))

    candidates = catalog.discover_installations("dcc.blender")

    assert candidates == []
