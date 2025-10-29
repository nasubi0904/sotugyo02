"""ProjectRezPackageRepository の挙動を検証するテスト。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from src.sotugyo.domain.projects.envs import (
    SOFTWARE_DIRECTORY_ENV_KEY,
    ProjectRezPackage,
    ProjectRezPackageRepository,
)


def _build_entry(identifier: str, *, tool: str = "toolA") -> ProjectRezPackage:
    return ProjectRezPackage(
        environment_id=identifier,
        tool_id=tool,
        rez_packages=("maya",),
        rez_variants=("platform-windows",),
        rez_environment={"MAYA_APP_DIR": "${PROJECT_ROOT}/maya"},
    )


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    repository = ProjectRezPackageRepository(tmp_path)
    entry = _build_entry("env-001")
    entry.update_environment_variable(SOFTWARE_DIRECTORY_ENV_KEY, "C:/Tools/Maya")

    repository.save_all([entry])
    stored_path = repository.resolve_storage_path()
    assert stored_path.exists()

    loaded = repository.load_all()
    assert len(loaded) == 1
    loaded_entry = loaded[0]
    assert loaded_entry.environment_id == "env-001"
    assert loaded_entry.tool_id == "toolA"
    assert loaded_entry.rez_packages == ("maya",)
    assert loaded_entry.rez_variants == ("platform-windows",)
    assert loaded_entry.rez_environment[SOFTWARE_DIRECTORY_ENV_KEY] == "C:/Tools/Maya"


def test_repository_serializes_in_identifier_order(tmp_path: Path) -> None:
    repository = ProjectRezPackageRepository(tmp_path)
    entry_b = _build_entry("env-b")
    entry_a = _build_entry("env-a")

    repository.save_all([entry_b, entry_a])
    stored_path = repository.resolve_storage_path()
    payload = json.loads(stored_path.read_text(encoding="utf-8"))
    identifiers = [item["environment_id"] for item in payload]
    assert identifiers == ["env-a", "env-b"]


def test_update_environment_variable_updates_timestamp() -> None:
    entry = _build_entry("env-001")
    original_timestamp = entry.updated_at
    changed = entry.update_environment_variable("CUSTOM_PATH", "C:/Temp")
    assert changed is True
    assert entry.updated_at >= original_timestamp

    latest_timestamp = entry.updated_at
    changed = entry.update_environment_variable("CUSTOM_PATH", "C:/Temp")
    assert changed is False
    assert entry.updated_at == latest_timestamp


def test_update_from_node_applies_changes() -> None:
    entry = _build_entry("env-001")
    before_timestamp = entry.updated_at
    changed = entry.update_from_node(
        tool_id="toolB",
        packages=("houdini",),
        variants=(),
        environment={"HOUDINI_PATH": "C:/Houdini"},
    )
    assert changed is True
    assert entry.tool_id == "toolB"
    assert entry.rez_packages == ("houdini",)
    assert entry.rez_variants == ()
    assert entry.rez_environment == {"HOUDINI_PATH": "C:/Houdini"}
    assert entry.updated_at >= before_timestamp


def test_from_payload_accepts_non_string_environment_values() -> None:
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {
        "environment_id": "env-002",
        "tool_id": "toolC",
        "rez_packages": ["nuke"],
        "rez_variants": [],
        "rez_environment": {"BUILD": 2025},
        "updated_at": now,
    }
    entry = ProjectRezPackage.from_payload(payload)
    assert entry.rez_environment == {"BUILD": "2025"}
    assert entry.environment_id == "env-002"
    assert entry.tool_id == "toolC"
