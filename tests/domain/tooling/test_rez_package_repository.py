from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from src.sotugyo.domain.tooling.models import TemplateInstallationCandidate
from src.sotugyo.domain.tooling.repositories.rez_packages import (
    ProjectRezPackageRepository,
    RezPackageRepository,
)


def test_register_candidate_writes_package(tmp_path) -> None:
    repo = RezPackageRepository(root_dir=tmp_path)
    executable = tmp_path / "maya.exe"
    executable.write_text("#!/bin/sh\n")
    candidate = TemplateInstallationCandidate(
        template_id="autodesk.maya",
        display_name="Autodesk Maya",
        executable_path=executable,
        version="2025",
    )

    package_name = repo.register_candidate(candidate)

    package_file = tmp_path / package_name / "2025" / "package.py"
    assert package_file.exists()
    content = package_file.read_text(encoding="utf-8")
    assert "name = \"autodesk_maya\"" in content
    assert str(executable) in content
    assert repo.get_package_name("autodesk.maya") == "autodesk_maya"


def test_get_package_name_returns_none_when_unknown(tmp_path) -> None:
    repo = RezPackageRepository(root_dir=tmp_path)

    assert repo.get_package_name("adobe.after_effects") is None


def test_list_packages_prefers_latest_version(tmp_path) -> None:
    repo = RezPackageRepository(root_dir=tmp_path)
    package_root = repo.root_dir
    older = package_root / "maya" / "2024"
    older.mkdir(parents=True)
    (older / "package.py").write_text("name = 'maya'\n")
    newer = package_root / "maya" / "2025"
    newer.mkdir(parents=True)
    (newer / "package.py").write_text("name = 'maya'\n")

    specs = repo.list_packages()

    assert specs[0].name == "maya"
    assert specs[0].version == "2025"
    assert specs[0].path == newer


def test_sync_packages_to_project_and_validate(tmp_path) -> None:
    source_repo = RezPackageRepository(root_dir=tmp_path / "kdmrez")
    package_root = source_repo.root_dir / "houdini" / "20.0"
    package_root.mkdir(parents=True)
    (package_root / "package.py").write_text("name = 'houdini'\n")

    project_root = tmp_path / "project"
    result = source_repo.sync_packages_to_project(
        project_root, ["houdini", "missing_pkg"]
    )

    copied_file = project_root / "config" / "rez_packages" / "houdini" / "20.0" / "package.py"
    assert copied_file.exists()
    assert result.missing == ("missing_pkg",)

    project_repo = ProjectRezPackageRepository(project_root)
    (project_repo.root_dir / "broken").mkdir(parents=True, exist_ok=True)
    validation = project_repo.validate()
    assert "broken" in validation.invalid
