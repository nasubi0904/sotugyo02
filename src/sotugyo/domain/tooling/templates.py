"""DCC ツールのテンプレート探索ロジック。"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Dict, List

from .models import TemplateInstallationCandidate

TEMPLATE_METADATA: Dict[str, Dict[str, str]] = {
    "autodesk.maya": {
        "label": "Autodesk Maya",
        "description": "Autodesk Maya を既定のインストール先から探索します。",
    }
}


def list_templates() -> List[Dict[str, str]]:
    """利用可能なテンプレート情報を返す。"""

    return [
        {"template_id": template_id, **metadata}
        for template_id, metadata in TEMPLATE_METADATA.items()
    ]


def discover_installations(template_id: str) -> List[TemplateInstallationCandidate]:
    """テンプレートに対応するインストール候補を探索する。"""

    if template_id == "autodesk.maya":
        return _discover_maya_installations()
    return []


def _discover_maya_installations() -> List[TemplateInstallationCandidate]:
    if sys.platform != "win32":
        return []

    candidates: List[TemplateInstallationCandidate] = []
    search_roots: List[Path] = []

    env_root = os.environ.get("AUTODESK_MAYA_DIR")
    if env_root:
        search_roots.append(Path(env_root))

    program_files = os.environ.get("PROGRAMFILES")
    if program_files:
        search_roots.append(Path(program_files) / "Autodesk")
    search_roots.append(Path("C:/Program Files/Autodesk"))

    seen_paths = set()
    for root in search_roots:
        if not root or root in seen_paths:
            continue
        seen_paths.add(root)
        if not root.exists():
            continue
        for entry in root.iterdir():
            if not entry.is_dir():
                continue
            name_lower = entry.name.lower()
            if not name_lower.startswith("maya"):
                continue
            executable = entry / "bin" / "maya.exe"
            if not executable.exists():
                continue
            version = _extract_version(entry.name)
            if version:
                display = f"Autodesk Maya {version}"
            else:
                display = "Autodesk Maya"
            candidates.append(
                TemplateInstallationCandidate(
                    template_id="autodesk.maya",
                    display_name=display,
                    executable_path=executable,
                    version=version,
                )
            )

    candidates.sort(key=lambda candidate: candidate.version or "")
    return candidates


def _extract_version(text: str) -> str:
    digits = "".join(char for char in text if char.isdigit())
    return digits or text.strip()
