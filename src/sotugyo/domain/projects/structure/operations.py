"""プロジェクト構造の検証・生成ロジック。"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

from .policy import DEFAULT_DIRECTORIES, DEFAULT_FILE_CONTENT, DEFAULT_FILES
from .report import ProjectStructureReport

__all__ = ["ensure_structure", "validate_structure"]


def _normalise(root: Path, entries: Iterable[str]) -> List[Path]:
    paths: List[Path] = []
    for entry in entries:
        if not entry:
            continue
        entry_path = Path(entry)
        paths.append(root.joinpath(entry_path))
    return paths


def validate_structure(root: Path) -> ProjectStructureReport:
    """既定の構成と比較して不足要素を抽出する。"""

    missing_dirs: List[str] = []
    missing_files: List[str] = []

    for directory in _normalise(root, DEFAULT_DIRECTORIES):
        if not directory.exists():
            missing_dirs.append(str(directory.relative_to(root)))

    for file_path in _normalise(root, DEFAULT_FILES):
        if not file_path.exists():
            missing_files.append(str(file_path.relative_to(root)))

    return ProjectStructureReport(missing_directories=missing_dirs, missing_files=missing_files)


def ensure_structure(root: Path) -> ProjectStructureReport:
    """不足している要素を生成しつつレポートを返す。"""

    root.mkdir(parents=True, exist_ok=True)

    missing_dirs: List[str] = []
    missing_files: List[str] = []

    for directory in _normalise(root, DEFAULT_DIRECTORIES):
        if directory.exists():
            continue
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        if not directory.exists():
            missing_dirs.append(str(directory.relative_to(root)))

    for file_path in _normalise(root, DEFAULT_FILES):
        if file_path.exists():
            continue
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            relative_key = file_path.relative_to(root).as_posix()
            content = DEFAULT_FILE_CONTENT.get(relative_key)
            if content is None:
                file_path.touch(exist_ok=True)
            else:
                file_path.write_text(content, encoding="utf-8")
        except OSError:
            pass
        if not file_path.exists():
            missing_files.append(str(file_path.relative_to(root)))

    return ProjectStructureReport(missing_directories=missing_dirs, missing_files=missing_files)
