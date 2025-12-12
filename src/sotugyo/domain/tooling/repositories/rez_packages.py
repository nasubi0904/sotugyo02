from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

from ....infrastructure.paths.storage import get_rez_package_dir
from ..models import TemplateInstallationCandidate

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


__all__ = ["RezPackageRepository"]
