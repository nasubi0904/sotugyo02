from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from packaging.version import InvalidVersion, Version

from ....infrastructure.paths.storage import get_rez_package_dir
from ..models import RezPackageSpec, TemplateInstallationCandidate

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class RezPackageRepository:
    """テンプレート検出結果から Rez パッケージを生成・管理する。"""

    root_dir: Path
    index_file: str = "packages.json"
    _index_path: Path = field(init=False)

    def __init__(self, root_dir: Path | None = None) -> None:
        base_dir = root_dir or get_rez_package_dir()
        self.root_dir = Path(base_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = "packages.json"
        self._index_path = self.root_dir / self.index_file

    def register_candidate(self, candidate: TemplateInstallationCandidate) -> str:
        """検出したインストールから Rez パッケージを生成する。"""

        package_name = self._normalize_package_name(candidate.template_id)
        version = candidate.version or "local"
        package_dir = self.root_dir / package_name / version
        package_dir.mkdir(parents=True, exist_ok=True)

        package_file = package_dir / "package.py"
        try:
            package_file.write_text(
                self._render_package(candidate, package_name, version),
                encoding="utf-8",
            )
        except OSError:
            LOGGER.warning("Rez パッケージの書き込みに失敗しました: %s", package_file, exc_info=True)

        self._update_index(
            candidate.template_id,
            package_name=package_name,
            version=version,
            executable_path=candidate.executable_path,
        )
        return package_name

    def get_package_name(self, template_id: str) -> Optional[str]:
        """テンプレート ID に紐づく Rez パッケージ名を返す。"""

        if not template_id:
            return None
        entry = self._read_index().get(template_id)
        if isinstance(entry, dict):
            package_name = entry.get("package")
            if isinstance(package_name, str) and package_name.strip():
                return package_name
        return self._normalize_package_name(template_id)

    def list_packages(self) -> List[RezPackageSpec]:
        """KDMrez 直下に存在する Rez パッケージ一覧を返す。"""

        return list(self._collect_packages(self.root_dir))

    def find_package(self, package_name: str) -> Optional[RezPackageSpec]:
        """指定パッケージの最新版と思しき定義を返す。"""

        if not package_name:
            return None
        for spec in self._collect_packages(self.root_dir, target=package_name):
            return spec
        return None

    def sync_packages_to_project(
        self, project_root: Path, packages: Iterable[str]
    ) -> "RezPackageSyncResult":
        """プロジェクト配下へ Rez パッケージをコピーする。"""

        destination = ProjectRezPackageRepository(project_root)
        missing: list[str] = []
        copied: dict[str, RezPackageSpec] = {}
        for package in dict.fromkeys(packages):
            spec = self.find_package(package)
            if spec is None:
                missing.append(package)
                continue
            copied_spec = destination.copy_from(spec)
            copied[package] = copied_spec
        if copied:
            destination.write_index(copied.values())
        return RezPackageSyncResult(copied=copied, missing=tuple(missing))

    def _read_index(self) -> Dict[str, Dict[str, str]]:
        if not self._index_path.exists():
            return {}
        try:
            with self._index_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(data, dict):
            return {}
        templates = data.get("templates")
        if isinstance(templates, dict):
            filtered: Dict[str, Dict[str, str]] = {}
            for key, value in templates.items():
                if isinstance(key, str) and isinstance(value, dict):
                    filtered[key] = value
            return filtered
        return {}

    def _update_index(
        self,
        template_id: str,
        *,
        package_name: str,
        version: str,
        executable_path: Path,
    ) -> None:
        data = {"templates": self._read_index()}
        data.setdefault("templates", {})[template_id] = {
            "package": package_name,
            "version": version,
            "executable_path": str(executable_path),
        }
        self.root_dir.mkdir(parents=True, exist_ok=True)
        with self._index_path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)

    @staticmethod
    def _normalize_package_name(template_id: str) -> str:
        return template_id.replace(".", "_").strip()

    @staticmethod
    def _render_package(
        candidate: TemplateInstallationCandidate,
        package_name: str,
        version: str,
    ) -> str:
        executable = Path(candidate.executable_path)
        bin_dir = executable.parent
        return (
            f'name = "{package_name}"\n'
            f'version = "{version}"\n\n'
            "def commands():\n"
            f"    env.PATH.prepend(r\"{bin_dir}\")\n"
            f"    env.set('{package_name.upper()}_EXE', r\"{executable}\")\n"
        )

    @staticmethod
    def _collect_packages(base_dir: Path, *, target: str | None = None):
        if not base_dir.exists():
            return []
        specs: List[RezPackageSpec] = []
        try:
            package_dirs = [entry for entry in base_dir.iterdir() if entry.is_dir()]
        except OSError:
            return []
        for package_dir in sorted(package_dirs):
            package_name = package_dir.name
            if target and package_name != target:
                continue
            best_candidate = RezPackageRepository._select_package_dir(package_dir)
            if best_candidate is None:
                continue
            version = (
                best_candidate.name if best_candidate.parent.name == package_name else None
            )
            specs.append(RezPackageSpec(package_name, version, best_candidate))
        return specs

    @staticmethod
    def _select_package_dir(package_dir: Path) -> Optional[Path]:
        """package.py を含む最適なディレクトリを選ぶ。"""

        candidates: List[Path] = []
        if (package_dir / "package.py").exists():
            candidates.append(package_dir)
        try:
            for child in package_dir.iterdir():
                if child.is_dir() and (child / "package.py").exists():
                    candidates.append(child)
        except OSError:
            LOGGER.debug("Rez パッケージ候補の走査に失敗しました: %s", package_dir, exc_info=True)
            return None
        if not candidates:
            return None
        versioned_candidates: list[tuple[Version, Path]] = []
        for candidate in candidates:
            if candidate.parent != package_dir:
                continue
            parsed = RezPackageRepository._parse_version(candidate.name)
            if parsed is not None:
                versioned_candidates.append((parsed, candidate))
        if versioned_candidates:
            versioned_candidates.sort(key=lambda entry: entry[0], reverse=True)
            return versioned_candidates[0][1]
        candidates.sort(key=lambda path: path.stat().st_mtime if path.exists() else 0, reverse=True)
        return candidates[0]

    @staticmethod
    def _parse_version(label: str | None) -> Version | None:
        if not label:
            return None
        try:
            return Version(label)
        except InvalidVersion:
            return None


@dataclass(slots=True, frozen=True)
class RezPackageSyncResult:
    """Rez パッケージ同期処理の結果。"""

    copied: Dict[str, RezPackageSpec]
    missing: tuple[str, ...]

    @property
    def has_missing(self) -> bool:
        return bool(self.missing)


@dataclass(slots=True, frozen=True)
class RezPackageValidationResult:
    """Rez パッケージ検証の結果。"""

    missing: tuple[str, ...]
    invalid: tuple[str, ...]

    @property
    def has_error(self) -> bool:
        return bool(self.missing or self.invalid)


class ProjectRezPackageRepository:
    """プロジェクト配下の Rez パッケージ管理。"""

    DIR_NAME = "rez_packages"

    def __init__(self, project_root: Path) -> None:
        self.project_root = Path(project_root)
        self.root_dir = self.project_root / "config" / self.DIR_NAME

    def list_packages(self) -> List[RezPackageSpec]:
        return list(RezPackageRepository._collect_packages(self.root_dir))

    def copy_from(self, source: RezPackageSpec) -> RezPackageSpec:
        target_dir = self.root_dir / source.name
        if source.version:
            target_dir = target_dir / source.version
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source.path, target_dir, dirs_exist_ok=True)
        return RezPackageSpec(source.name, source.version, target_dir)

    def validate(self) -> RezPackageValidationResult:
        missing: List[str] = []
        invalid: List[str] = []
        try:
            candidates = [entry for entry in self.root_dir.iterdir() if entry.is_dir()]
        except OSError:
            return RezPackageValidationResult(missing=(), invalid=())
        for entry in candidates:
            spec = RezPackageRepository._select_package_dir(entry)
            if spec is None:
                invalid.append(entry.name)
                continue
            if not (spec / "package.py").exists():
                missing.append(entry.name)
        return RezPackageValidationResult(missing=tuple(missing), invalid=tuple(invalid))

    def write_index(self, specs: Iterable[RezPackageSpec]) -> None:
        self.root_dir.mkdir(parents=True, exist_ok=True)
        index_path = self.root_dir / "packages.json"
        payload = {
            "packages": [
                {
                    "name": spec.name,
                    "version": spec.version,
                    "path": str(spec.path),
                }
                for spec in specs
            ]
        }
        with index_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)


__all__ = [
    "ProjectRezPackageRepository",
    "RezPackageRepository",
    "RezPackageSyncResult",
    "RezPackageValidationResult",
]
