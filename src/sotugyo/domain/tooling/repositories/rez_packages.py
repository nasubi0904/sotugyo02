from __future__ import annotations

import logging
import re
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
    _last_scan: List[RezPackageSpec] = field(init=False)
    _last_entries: List[RezPackageSpec] = field(init=False)

    def __init__(self, root_dir: Path | None = None) -> None:
        base_dir = root_dir or get_rez_package_dir()
        self.root_dir = Path(base_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self._last_scan = []
        self._last_entries = []

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
        return package_name

    def get_package_name(self, template_id: str) -> Optional[str]:
        """テンプレート ID に紐づく Rez パッケージ名を返す。"""

        if not template_id:
            return None
        normalized = self._normalize_package_name(template_id)
        self._scan_packages()
        if any(spec.name == normalized for spec in self._last_scan):
            return normalized
        return None

    def list_packages(self) -> List[RezPackageSpec]:
        """KDMrez 直下に存在する Rez パッケージ一覧を返す。"""

        self._scan_packages()
        return list(self._last_scan)

    def list_package_entries(self) -> List[RezPackageSpec]:
        """package.py ごとの Rez パッケージ一覧を返す。"""

        self._scan_package_entries()
        return list(self._last_entries)

    def find_package(self, package_name: str) -> Optional[RezPackageSpec]:
        """指定パッケージの最新版と思しき定義を返す。"""

        if not package_name:
            return None
        self._scan_packages()
        for spec in self._last_scan:
            if spec.name == package_name:
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
        return RezPackageSyncResult(copied=copied, missing=tuple(missing))

    @staticmethod
    def _normalize_package_name(template_id: str) -> str:
        return template_id.replace(".", "_").strip()

    @classmethod
    def normalize_template_id(cls, template_id: str) -> str:
        return cls._normalize_package_name(template_id)

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
            f"    env[\"{package_name.upper()}_EXE\"] = r\"{executable}\"\n"
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
        scored_candidates = []
        for path in candidates:
            try:
                version_key = Version(path.name)
                has_version = True
            except InvalidVersion:
                version_key = Version("0")
                has_version = False
            mtime = path.stat().st_mtime if path.exists() else 0.0
            scored_candidates.append((has_version, version_key, mtime, path))

        scored_candidates.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
        return scored_candidates[0][3]

    @staticmethod
    def _collect_package_entries(base_dir: Path) -> List[RezPackageSpec]:
        if not base_dir.exists():
            return []
        specs: List[RezPackageSpec] = []
        try:
            package_dirs = [entry for entry in base_dir.iterdir() if entry.is_dir()]
        except OSError:
            return []
        for package_dir in sorted(package_dirs):
            package_name = package_dir.name
            if (package_dir / "package.py").exists():
                specs.append(RezPackageSpec(package_name, None, package_dir))
            try:
                children = [entry for entry in package_dir.iterdir() if entry.is_dir()]
            except OSError:
                LOGGER.debug(
                    "Rez パッケージ候補の走査に失敗しました: %s",
                    package_dir,
                    exc_info=True,
                )
                continue
            for child in sorted(children):
                if (child / "package.py").exists():
                    specs.append(RezPackageSpec(package_name, child.name, child))
        return specs

    def _scan_packages(self) -> None:
        self._last_scan = list(self._collect_packages(self.root_dir))

    def _scan_package_entries(self) -> None:
        self._last_entries = list(self._collect_package_entries(self.root_dir))

    def remove_package(self, package_name: str) -> None:
        if not package_name:
            return
        target_dir = self.root_dir / package_name
        if not target_dir.exists():
            return
        try:
            shutil.rmtree(target_dir)
        except OSError:
            LOGGER.warning("Rez パッケージの削除に失敗しました: %s", target_dir, exc_info=True)

    def resolve_executable(self, spec: RezPackageSpec) -> Optional[Path]:
        package_file = spec.path / "package.py"
        if not package_file.exists():
            return None
        try:
            content = package_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            LOGGER.debug("package.py の読み込みに失敗しました: %s", package_file, exc_info=True)
            return None
        matches = re.findall(r"([A-Za-z]:[^\"\n]+\\.exe)", content, flags=re.IGNORECASE)
        for match in matches:
            candidate = Path(match)
            if candidate.exists():
                return candidate
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

    def write_project_package(
        self,
        project_name: str,
        requires: Iterable[str],
        *,
        version: str = "1.0",
    ) -> Path:
        normalized_dir = self._normalize_project_package_dir(project_name)
        package_dir = self.root_dir / normalized_dir / version
        package_dir.mkdir(parents=True, exist_ok=True)
        package_file = package_dir / "package.py"
        payload = self._render_project_package(project_name, version, requires)
        package_file.write_text(payload, encoding="utf-8")
        return package_file

    @staticmethod
    def _normalize_project_package_dir(project_name: str) -> str:
        normalized = project_name.strip() or "project"
        return re.sub(r"[\\\\/:*?\"<>|]", "_", normalized)

    @staticmethod
    def _render_project_package(
        project_name: str,
        version: str,
        requires: Iterable[str],
    ) -> str:
        normalized_requires = []
        for entry in requires:
            if isinstance(entry, str) and entry.strip():
                normalized_requires.append(entry.strip())
        unique_requires = list(dict.fromkeys(normalized_requires))
        requires_lines = "\n".join(f'    "{item}",' for item in unique_requires)
        if requires_lines:
            requires_block = f"requires = [\n{requires_lines}\n]\n"
        else:
            requires_block = "requires = []\n"
        return (
            f'name = "{project_name}"\n'
            f'version = "{version}"\n\n'
            f"{requires_block}"
        )

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


__all__ = [
    "ProjectRezPackageRepository",
    "RezPackageRepository",
    "RezPackageSyncResult",
    "RezPackageValidationResult",
]
