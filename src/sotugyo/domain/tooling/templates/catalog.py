"""DCC ツールのテンプレート探索ロジック。"""

from __future__ import annotations

import os
import re
import logging
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

from ..models import TemplateInstallationCandidate
from ..repositories.rez_packages import RezPackageRepository

LOGGER = logging.getLogger(__name__)

TEMPLATE_METADATA: Dict[str, Dict[str, str]] = {
    "autodesk.maya": {
        "label": "Autodesk Maya",
        "description": "Autodesk Maya を既定のインストール先から探索します。",
    },
    "autodesk.3ds_max": {
        "label": "Autodesk 3ds Max",
        "description": "Autodesk 3ds Max を既定のインストール先から探索します。",
    },
    "autodesk.motionbuilder": {
        "label": "Autodesk MotionBuilder",
        "description": "Autodesk MotionBuilder を既定のインストール先から探索します。",
    },
    "adobe.after_effects": {
        "label": "Adobe After Effects",
        "description": "Adobe After Effects を既定のインストール先から探索します。",
    },
    "adobe.premiere_pro": {
        "label": "Adobe Premiere Pro",
        "description": "Adobe Premiere Pro を既定のインストール先から探索します。",
    },
    "adobe.photoshop": {
        "label": "Adobe Photoshop",
        "description": "Adobe Photoshop を既定のインストール先から探索します。",
    },
    "adobe.substance_painter": {
        "label": "Adobe Substance 3D Painter",
        "description": "Adobe Substance 3D Painter を既定のインストール先から探索します。",
    },
    "dcc.blender": {
        "label": "Blender",
        "description": "Blender を既定のインストール先から探索します。",
    },
    "dcc.houdini": {
        "label": "SideFX Houdini",
        "description": "SideFX Houdini を既定のインストール先から探索します。",
    },
    "dcc.nuke": {
        "label": "Foundry Nuke",
        "description": "Foundry Nuke を既定のインストール先から探索します。",
    },
}

_REZ_REPOSITORY = RezPackageRepository()


def list_templates() -> List[Dict[str, str]]:
    """利用可能なテンプレート情報を返す。"""

    return [
        {"template_id": template_id, **metadata}
        for template_id, metadata in TEMPLATE_METADATA.items()
    ]


def discover_installations(template_id: str) -> List[TemplateInstallationCandidate]:
    """テンプレートに対応するインストール候補を探索する。"""

    candidates: List[TemplateInstallationCandidate] = []
    if template_id == "autodesk.maya":
        candidates = _discover_maya_installations()
    elif template_id == "autodesk.3ds_max":
        candidates = _discover_3ds_max_installations()
    elif template_id == "autodesk.motionbuilder":
        candidates = _discover_motionbuilder_installations()
    elif template_id == "adobe.after_effects":
        candidates = _discover_after_effects_installations()
    elif template_id == "adobe.premiere_pro":
        candidates = _discover_premiere_pro_installations()
    elif template_id == "adobe.photoshop":
        candidates = _discover_photoshop_installations()
    elif template_id == "adobe.substance_painter":
        candidates = _discover_substance_painter_installations()
    elif template_id == "dcc.blender":
        candidates = _discover_blender_installations()
    elif template_id == "dcc.houdini":
        candidates = _discover_houdini_installations()
    elif template_id == "dcc.nuke":
        candidates = _discover_nuke_installations()

    _register_rez_packages(candidates)
    return candidates


def load_environment_payload(template_id: str) -> Dict[str, object]:
    """テンプレートに紐づく Rez 環境設定を返す。"""

    package_name = _REZ_REPOSITORY.get_package_name(template_id)
    if not package_name:
        return {}
    payload: Dict[str, object] = {"rez_packages": [package_name]}
    if sys.platform == "win32":
        payload["rez_variants"] = ["platform-windows"]
    return payload


def _register_rez_packages(candidates: Iterable[TemplateInstallationCandidate]) -> None:
    for candidate in candidates:
        try:
            _REZ_REPOSITORY.register_candidate(candidate)
        except OSError:
            LOGGER.warning(
                "Rez パッケージ登録に失敗しました: %s", candidate.executable_path, exc_info=True
            )


def _collect_search_roots(
    env_vars: Sequence[str],
    program_files_subdirs: Sequence[str],
    fallback_paths: Sequence[str],
) -> List[Path]:
    roots: List[Path] = []
    for env_name in env_vars:
        env_value = os.environ.get(env_name)
        if env_value:
            roots.append(Path(env_value))

    program_files = os.environ.get("PROGRAMFILES")
    if program_files:
        base = Path(program_files)
        for subdir in program_files_subdirs:
            roots.append(base / subdir)

    for fallback in fallback_paths:
        roots.append(Path(fallback))
    return roots


def _iter_unique_existing(paths: Iterable[Path]) -> Iterable[Path]:
    seen: set[Path] = set()
    for path in paths:
        if not path:
            continue
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        if resolved in seen:
            continue
        seen.add(resolved)
        if resolved.exists():
            yield resolved


def _discover_maya_installations() -> List[TemplateInstallationCandidate]:
    if sys.platform != "win32":
        return []

    candidates: List[TemplateInstallationCandidate] = []
    search_roots = _collect_search_roots(
        ["AUTODESK_MAYA_DIR"],
        ["Autodesk"],
        ["C:/Program Files/Autodesk"],
    )

    seen_paths: set[Path] = set()
    for root in _iter_unique_existing(search_roots):
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
    search_roots = _collect_search_roots(
        ["ADOBE_AFTEREFFECTS_DIR"],
        ["Adobe"],
        ["C:/Program Files/Adobe"],
    )

    seen_paths: set[Path] = set()

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

    processed_roots: set[Path] = set()
    for root in _iter_unique_existing(search_roots):
        if root in processed_roots:
            continue
        processed_roots.add(root)
        inspect_directory(root)

    candidates.sort(key=lambda candidate: candidate.version or "")
    return candidates


def _discover_3ds_max_installations() -> List[TemplateInstallationCandidate]:
    if sys.platform != "win32":
        return []

    candidates: List[TemplateInstallationCandidate] = []
    search_roots = _collect_search_roots(
        ["AUTODESK_3DSMAX_DIR"],
        ["Autodesk"],
        ["C:/Program Files/Autodesk"],
    )

    for root in _iter_unique_existing(search_roots):
        for entry in root.iterdir():
            if not entry.is_dir():
                continue
            if "3ds" not in entry.name.lower():
                continue
            executable = entry / "3dsmax.exe"
            if not executable.exists():
                continue
            version = _extract_version(entry.name)
            display = "Autodesk 3ds Max"
            if version:
                display = f"{display} {version}"
            candidates.append(
                TemplateInstallationCandidate(
                    template_id="autodesk.3ds_max",
                    display_name=display,
                    executable_path=executable,
                    version=version or None,
                )
            )

    candidates.sort(key=lambda candidate: candidate.version or "")
    return candidates


def _discover_motionbuilder_installations() -> List[TemplateInstallationCandidate]:
    if sys.platform != "win32":
        return []

    candidates: List[TemplateInstallationCandidate] = []
    search_roots = _collect_search_roots(
        ["AUTODESK_MOTIONBUILDER_DIR"],
        ["Autodesk"],
        ["C:/Program Files/Autodesk"],
    )

    for root in _iter_unique_existing(search_roots):
        for entry in root.iterdir():
            if not entry.is_dir():
                continue
            if "motionbuilder" not in entry.name.lower():
                continue
            executable = entry / "bin" / "x64" / "motionbuilder.exe"
            if not executable.exists():
                executable = entry / "motionbuilder.exe"
            if not executable.exists():
                continue
            version = _extract_version(entry.name)
            display = "Autodesk MotionBuilder"
            if version:
                display = f"{display} {version}"
            candidates.append(
                TemplateInstallationCandidate(
                    template_id="autodesk.motionbuilder",
                    display_name=display,
                    executable_path=executable,
                    version=version or None,
                )
            )

    candidates.sort(key=lambda candidate: candidate.version or "")
    return candidates


def _discover_premiere_pro_installations() -> List[TemplateInstallationCandidate]:
    if sys.platform != "win32":
        return []

    candidates: List[TemplateInstallationCandidate] = []
    search_roots = _collect_search_roots(
        ["ADOBE_PREMIERE_PRO_DIR"],
        ["Adobe"],
        ["C:/Program Files/Adobe"],
    )

    def locate_executable(target: Path) -> Path | None:
        candidates = [
            target / "Adobe Premiere Pro.exe",
            target / "PremierePro.exe",
            target / "Adobe Premiere Pro" / "Adobe Premiere Pro.exe",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    for root in _iter_unique_existing(search_roots):
        if root.is_file():
            if root.name.lower() in {"adobe premiere pro.exe", "premierepro.exe"}:
                parent = root.parent
                version = _extract_version(parent.name) if parent else ""
                display = "Adobe Premiere Pro"
                if version:
                    display = f"{display} {version}"
                candidates.append(
                    TemplateInstallationCandidate(
                        template_id="adobe.premiere_pro",
                        display_name=display,
                        executable_path=root,
                        version=version or None,
                    )
                )
            continue
        for entry in root.iterdir():
            if not entry.is_dir():
                continue
            if "premiere" not in entry.name.lower():
                continue
            executable = locate_executable(entry)
            if not executable:
                continue
            version = _extract_version(entry.name)
            display = "Adobe Premiere Pro"
            if version:
                display = f"{display} {version}"
            candidates.append(
                TemplateInstallationCandidate(
                    template_id="adobe.premiere_pro",
                    display_name=display,
                    executable_path=executable,
                    version=version or None,
                )
            )

    candidates.sort(key=lambda candidate: candidate.version or "")
    return candidates


def _discover_photoshop_installations() -> List[TemplateInstallationCandidate]:
    if sys.platform != "win32":
        return []

    candidates: List[TemplateInstallationCandidate] = []
    search_roots = _collect_search_roots(
        ["ADOBE_PHOTOSHOP_DIR"],
        ["Adobe"],
        ["C:/Program Files/Adobe"],
    )

    def locate_executable(target: Path) -> Path | None:
        options = [
            target / "Photoshop.exe",
            target / "Adobe Photoshop.exe",
        ]
        for option in options:
            if option.exists():
                return option
        return None

    for root in _iter_unique_existing(search_roots):
        if root.is_file():
            if root.name.lower() in {"photoshop.exe", "adobe photoshop.exe"}:
                parent = root.parent
                version = _extract_version(parent.name) if parent else ""
                display = "Adobe Photoshop"
                if version:
                    display = f"{display} {version}"
                candidates.append(
                    TemplateInstallationCandidate(
                        template_id="adobe.photoshop",
                        display_name=display,
                        executable_path=root,
                        version=version or None,
                    )
                )
            continue
        for entry in root.iterdir():
            if not entry.is_dir():
                continue
            if "photoshop" not in entry.name.lower():
                continue
            executable = locate_executable(entry)
            if not executable:
                continue
            version = _extract_version(entry.name)
            display = "Adobe Photoshop"
            if version:
                display = f"{display} {version}"
            candidates.append(
                TemplateInstallationCandidate(
                    template_id="adobe.photoshop",
                    display_name=display,
                    executable_path=executable,
                    version=version or None,
                )
            )

    candidates.sort(key=lambda candidate: candidate.version or "")
    return candidates


def _discover_substance_painter_installations() -> List[TemplateInstallationCandidate]:
    if sys.platform != "win32":
        return []

    candidates: List[TemplateInstallationCandidate] = []
    search_roots = _collect_search_roots(
        ["ADOBE_SUBSTANCE_PAINTER_DIR"],
        ["Adobe", "Adobe Substance 3D"],
        ["C:/Program Files/Adobe", "C:/Program Files/Adobe Substance 3D"],
    )

    def locate_executable(target: Path) -> Path | None:
        options = [
            target / "Adobe Substance 3D Painter.exe",
            target / "Substance Painter.exe",
        ]
        for option in options:
            if option.exists():
                return option
        return None

    for root in _iter_unique_existing(search_roots):
        if root.is_file():
            if root.name.lower() in {
                "adobe substance 3d painter.exe",
                "substance painter.exe",
            }:
                parent = root.parent
                version = _extract_version(parent.name) if parent else ""
                display = "Adobe Substance 3D Painter"
                if version:
                    display = f"{display} {version}"
                candidates.append(
                    TemplateInstallationCandidate(
                        template_id="adobe.substance_painter",
                        display_name=display,
                        executable_path=root,
                        version=version or None,
                    )
                )
            continue
        for entry in root.iterdir():
            if not entry.is_dir():
                continue
            if "painter" not in entry.name.lower():
                continue
            executable = locate_executable(entry)
            if not executable:
                continue
            version = _extract_version(entry.name)
            display = "Adobe Substance 3D Painter"
            if version:
                display = f"{display} {version}"
            candidates.append(
                TemplateInstallationCandidate(
                    template_id="adobe.substance_painter",
                    display_name=display,
                    executable_path=executable,
                    version=version or None,
                )
            )

    candidates.sort(key=lambda candidate: candidate.version or "")
    return candidates


def _discover_blender_installations() -> List[TemplateInstallationCandidate]:
    if sys.platform != "win32":
        return []

    candidates: List[TemplateInstallationCandidate] = []
    search_roots = _collect_search_roots(
        ["BLENDER_DIR"],
        ["Blender Foundation"],
        ["C:/Program Files/Blender Foundation"],
    )

    def add_candidate(executable: Path) -> None:
        version = _extract_version(executable.parent.name)
        display = "Blender"
        if version:
            display = f"{display} {version}"
        candidates.append(
            TemplateInstallationCandidate(
                template_id="dcc.blender",
                display_name=display,
                executable_path=executable,
                version=version or None,
            )
        )

    for root in _iter_unique_existing(search_roots):
        if root.is_file() and root.name.lower() == "blender.exe":
            add_candidate(root)
            continue
        for entry in root.iterdir():
            if entry.is_file() and entry.name.lower() == "blender.exe":
                add_candidate(entry)
                continue
            if not entry.is_dir():
                continue
            executable = entry / "blender.exe"
            if executable.exists():
                add_candidate(executable)

    candidates.sort(key=lambda candidate: candidate.version or "")
    return candidates


def _discover_houdini_installations() -> List[TemplateInstallationCandidate]:
    if sys.platform != "win32":
        return []

    candidates: List[TemplateInstallationCandidate] = []
    search_roots = _collect_search_roots(
        ["HOUDINI_DIR"],
        ["Side Effects Software"],
        ["C:/Program Files/Side Effects Software"],
    )

    def locate_executable(directory: Path) -> Path | None:
        options = [
            directory / "bin" / "houdinifx.exe",
            directory / "bin" / "houdini.exe",
            directory / "houdini.exe",
        ]
        for option in options:
            if option.exists():
                return option
        return None

    for root in _iter_unique_existing(search_roots):
        if root.is_file() and root.name.lower() in {"houdini.exe", "houdinifx.exe"}:
            parent = root.parent
            version = _extract_version(parent.name) if parent else ""
            display = "SideFX Houdini"
            if version:
                display = f"{display} {version}"
            candidates.append(
                TemplateInstallationCandidate(
                    template_id="dcc.houdini",
                    display_name=display,
                    executable_path=root,
                    version=version or None,
                )
            )
            continue
        for entry in root.iterdir():
            if not entry.is_dir():
                continue
            if "houdini" not in entry.name.lower():
                continue
            executable = locate_executable(entry)
            if not executable:
                continue
            version = _extract_version(entry.name)
            display = "SideFX Houdini"
            if version:
                display = f"{display} {version}"
            candidates.append(
                TemplateInstallationCandidate(
                    template_id="dcc.houdini",
                    display_name=display,
                    executable_path=executable,
                    version=version or None,
                )
            )

    candidates.sort(key=lambda candidate: candidate.version or "")
    return candidates


def _discover_nuke_installations() -> List[TemplateInstallationCandidate]:
    if sys.platform != "win32":
        return []

    candidates: List[TemplateInstallationCandidate] = []
    search_roots = _collect_search_roots(
        ["NUKE_DIR"],
        ["Nuke", "Foundry"],
        ["C:/Program Files/Nuke", "C:/Program Files/Foundry"],
    )

    for root in _iter_unique_existing(search_roots):
        if root.is_file() and root.suffix.lower() == ".exe" and "nuke" in root.name.lower():
            parent = root.parent
            version = _extract_version(parent.name) if parent else ""
            display = "Foundry Nuke"
            if version:
                display = f"{display} {version}"
            candidates.append(
                TemplateInstallationCandidate(
                    template_id="dcc.nuke",
                    display_name=display,
                    executable_path=root,
                    version=version or None,
                )
            )
            continue
        for entry in root.iterdir():
            if not entry.is_dir():
                continue
            if "nuke" not in entry.name.lower():
                continue

            executable_candidates = list(entry.glob("Nuke*.exe"))
            executable = None
            if executable_candidates:
                executable_candidates.sort(
                    key=lambda path: (_extract_version(path.stem) or "", path.name),
                    reverse=True,
                )
                executable = executable_candidates[0]
            if not executable:
                fallback = entry / f"{entry.name}.exe"
                if fallback.exists():
                    executable = fallback
            if not executable:
                fallback = entry / "Nuke.exe"
                if fallback.exists():
                    executable = fallback
            if not executable:
                continue
            version = _extract_version(entry.name)
            display = "Foundry Nuke"
            if version:
                display = f"{display} {version}"
            candidates.append(
                TemplateInstallationCandidate(
                    template_id="dcc.nuke",
                    display_name=display,
                    executable_path=executable,
                    version=version or None,
                )
            )

    candidates.sort(key=lambda candidate: candidate.version or "")
    return candidates


def _extract_version(text: str) -> str:
    pattern = re.compile(r"(\d+(?:[._]\d+)*(?:v\d+)?)")
    matches = pattern.findall(text)
    if matches:
        return matches[-1]
    digits = "".join(char for char in text if char.isdigit())
    return digits or text.strip()
