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
    },
    "adobe.after_effects": {
        "label": "Adobe After Effects",
        "description": "Adobe After Effects を既定のインストール先から探索します。",
    },
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
    if template_id == "adobe.after_effects":
        return _discover_after_effects_installations()
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


def _discover_after_effects_installations() -> List[TemplateInstallationCandidate]:
    if sys.platform != "win32":
        return []

    candidates: List[TemplateInstallationCandidate] = []
    search_roots: List[Path] = []

    env_root = os.environ.get("ADOBE_AFTEREFFECTS_DIR")
    if env_root:
        search_roots.append(Path(env_root))

    program_files = os.environ.get("PROGRAMFILES")
    if program_files:
        search_roots.append(Path(program_files) / "Adobe")
    search_roots.append(Path("C:/Program Files/Adobe"))

    seen_paths = set()

    def version_hint(directory: Path) -> str:
        parent = directory.parent
        if directory.name.lower() == "support files" and parent is not None:
            return parent.name
        return directory.name

    def add_candidate(executable: Path, hint_source: Path) -> None:
        try:
            resolved = executable.resolve()
        except OSError:
            resolved = executable
        if not executable.exists() or resolved in seen_paths:
            return
        seen_paths.add(resolved)
        hint = version_hint(hint_source)
        version = _extract_version(hint)
        display = "Adobe After Effects"
        if version:
            display = f"{display} {version}"
        candidates.append(
            TemplateInstallationCandidate(
                template_id="adobe.after_effects",
                display_name=display,
                executable_path=executable,
                version=version or None,
            )
        )

    def inspect_directory(target: Path) -> None:
        if not target.exists():
            return
        if target.is_file():
            if target.name.lower() == "afterfx.exe":
                add_candidate(target, target.parent)
            return

        direct_exec = target / "AfterFX.exe"
        if direct_exec.exists():
            add_candidate(direct_exec, target)

        support_exec = target / "Support Files" / "AfterFX.exe"
        if support_exec.exists():
            add_candidate(support_exec, target / "Support Files")

        try:
            entries = list(target.iterdir())
        except PermissionError:
            return
        for entry in entries:
            if entry.is_dir() and "after effects" in entry.name.lower():
                inspect_directory(entry)

    processed_roots = set()
    for root in search_roots:
        if not root or root in processed_roots:
            continue
        processed_roots.add(root)
        inspect_directory(root)

    candidates.sort(key=lambda candidate: candidate.version or "")
    return candidates


def _extract_version(text: str) -> str:
    digits = "".join(char for char in text if char.isdigit())
    return digits or text.strip()
