#!/usr/bin/env python3
"""Rez パッケージ経由でツールを起動する。"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sotugyo.domain.tooling.repositories.rez_packages import (
    ProjectRezPackageRepository,
    RezPackageRepository,
)
from sotugyo.infrastructure.paths.storage import get_rez_package_dir


def _normalize_version(version: Optional[str]) -> Optional[str]:
    if not version:
        return None
    normalized = version.strip()
    return normalized or None


def _build_requirement(name: str, version: Optional[str]) -> str:
    if version:
        return f"{name}-{version}"
    return name


def _ensure_packages_path(paths: Iterable[Path]) -> dict[str, str]:
    env = os.environ.copy()
    existing = env.get("REZ_PACKAGES_PATH")
    ordered = [str(path) for path in paths if path and path.exists()]
    if existing:
        ordered.extend([entry for entry in existing.split(os.pathsep) if entry])
    if ordered:
        env["REZ_PACKAGES_PATH"] = os.pathsep.join(dict.fromkeys(ordered))
    return env


def _find_package_spec(
    name: str,
    version: Optional[str],
    *,
    project_root: Optional[Path],
) -> Optional[object]:
    version_label = _normalize_version(version)
    repo = RezPackageRepository()
    candidates = repo.list_package_entries()
    if project_root:
        project_repo = ProjectRezPackageRepository(project_root)
        candidates.extend(
            RezPackageRepository._collect_package_entries(project_repo.root_dir)
        )
    if version_label:
        for spec in candidates:
            if spec.name == name and spec.version == version_label:
                return spec
    for spec in candidates:
        if spec.name == name:
            return spec
    return repo.find_package(name)


def _resolve_executable(spec) -> Optional[Path]:
    repo = RezPackageRepository(root_dir=spec.path.parents[1])
    return repo.resolve_executable(spec)


def _launch_package(
    name: str,
    version: Optional[str],
    *,
    project_root: Optional[Path],
) -> int:
    spec = _find_package_spec(name, version, project_root=project_root)
    if spec is None:
        print("Rez パッケージが見つかりませんでした。")
        return 1
    executable = _resolve_executable(spec)
    if executable is None:
        print("起動対象の実行ファイルが特定できませんでした。")
        return 1

    requirement = _build_requirement(name, _normalize_version(version))
    env = _ensure_packages_path(
        [
            project_root / "config" / "rez_packages" if project_root else None,
            get_rez_package_dir(),
        ]
    )
    args = ["rez-env", requirement, "--", str(executable)]
    try:
        completed = subprocess.run(args, env=env, check=False)
    except OSError as exc:
        print(f"Rez の起動に失敗しました: {exc}")
        return 1
    return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Rez パッケージからツールを起動します。")
    parser.add_argument("--package", required=True, help="Rez パッケージ名")
    parser.add_argument("--version", help="Rez パッケージのバージョン")
    parser.add_argument("--project-root", help="プロジェクトルートのパス")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else None
    if project_root and not project_root.exists():
        print("指定されたプロジェクトルートが見つかりませんでした。")
        return 1

    return _launch_package(args.package, args.version, project_root=project_root)


if __name__ == "__main__":
    raise SystemExit(main())
