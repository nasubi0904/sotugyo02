from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from src.sotugyo.domain.tooling.models import TemplateInstallationCandidate
from src.sotugyo.domain.tooling.repositories.rez_packages import RezPackageRepository


def test_register_candidate_writes_package_and_index(tmp_path) -> None:
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

    index_path = tmp_path / "packages.json"
    assert index_path.exists()
    data = json.loads(index_path.read_text(encoding="utf-8"))
    assert data["templates"]["autodesk.maya"]["package"] == "autodesk_maya"
    assert data["templates"]["autodesk.maya"]["version"] == "2025"


def test_get_package_name_returns_normalized_when_unknown(tmp_path) -> None:
    repo = RezPackageRepository(root_dir=tmp_path)

    assert repo.get_package_name("adobe.after_effects") == "adobe_after_effects"
