"""プロジェクトルートの既定構成と検証機能。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

__all__ = [
    "DEFAULT_DIRECTORIES",
    "DEFAULT_FILES",
    "ProjectStructureReport",
    "validate_project_structure",
    "ensure_project_structure",
]

# プロジェクトルート配下に必須となるディレクトリとファイル
DEFAULT_DIRECTORIES: List[str] = [
    "assets",
    "assets/source",
    "assets/published",
    "renders",
    "reviews",
    "config",
]
DEFAULT_FILES: List[str] = [
    "config/project_settings.json",
    "config/node_graph.json",
]
DEFAULT_FILE_CONTENT = {
    "config/project_settings.json": "{}\n",
    "config/node_graph.json": "{\n  \"nodes\": [],\n  \"connections\": []\n}\n",
}


@dataclass
class ProjectStructureReport:
    """構成チェックの結果。"""

    missing_directories: List[str]
    missing_files: List[str]

    @property
    def is_valid(self) -> bool:
        return not self.missing_directories and not self.missing_files

    def summary(self) -> str:
        messages: List[str] = []
        if self.missing_directories:
            messages.append(
                "未作成のディレクトリ: " + ", ".join(sorted(self.missing_directories))
            )
        if self.missing_files:
            messages.append("未作成のファイル: " + ", ".join(sorted(self.missing_files)))
        return "\n".join(messages) if messages else "既定構成を満たしています。"


def _normalise(root: Path, entries: Iterable[str]) -> List[Path]:
    paths: List[Path] = []
    for entry in entries:
        if not entry:
            continue
        entry_path = Path(entry)
        full_path = root.joinpath(entry_path)
        paths.append(full_path)
    return paths


def validate_project_structure(root: Path) -> ProjectStructureReport:
    """既定の構成と比較して不足している要素を報告する。"""

    missing_dirs: List[str] = []
    missing_files: List[str] = []

    for directory in _normalise(root, DEFAULT_DIRECTORIES):
        if not directory.exists():
            missing_dirs.append(str(directory.relative_to(root)))

    for file_path in _normalise(root, DEFAULT_FILES):
        if not file_path.exists():
            missing_files.append(str(file_path.relative_to(root)))

    return ProjectStructureReport(missing_directories=missing_dirs, missing_files=missing_files)


def ensure_project_structure(root: Path) -> ProjectStructureReport:
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
