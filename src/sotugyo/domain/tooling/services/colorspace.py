"""DCC ツール同封の色空間候補を走査するサービス。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Iterable, Optional

from ..models import RegisteredTool, RezPackageSpec
from ..repositories.config import ToolConfigRepository
from ..repositories.rez_packages import RezPackageRepository


@dataclass(frozen=True, slots=True)
class ColorSpaceCandidate:
    """色空間の環境変数候補。"""

    env_var: str
    label: str
    config_path: Optional[Path]
    source: str


@dataclass(frozen=True, slots=True)
class ColorSpaceRule:
    """DCC ごとの色空間探索ルール。"""

    template_id: str
    label: str
    env_vars: tuple[str, ...]
    search_paths: tuple[str, ...]
    extensions: tuple[str, ...]


_RULES: tuple[ColorSpaceRule, ...] = (
    ColorSpaceRule(
        template_id="autodesk.maya",
        label="Autodesk Maya",
        env_vars=("OCIO",),
        search_paths=(
            "resources/OCIO-configs",
            "resources/ColorManagement",
            "resources/color_management",
        ),
        extensions=(".ocio",),
    ),
    ColorSpaceRule(
        template_id="dcc.houdini",
        label="SideFX Houdini",
        env_vars=("HOUDINI_OCIO", "OCIO"),
        search_paths=(
            "houdini/config/ocio",
            "houdini/ocio",
            "config/ocio",
        ),
        extensions=(".ocio",),
    ),
    ColorSpaceRule(
        template_id="dcc.nuke",
        label="Foundry Nuke",
        env_vars=("OCIO",),
        search_paths=(
            "plugins/OCIOConfigs",
            "plugins/OCIO",
            "OCIOConfigs",
        ),
        extensions=(".ocio",),
    ),
    ColorSpaceRule(
        template_id="dcc.blender",
        label="Blender",
        env_vars=("OCIO",),
        search_paths=(
            "datafiles/colormanagement",
            "datafiles/color_management",
        ),
        extensions=(".ocio",),
    ),
    ColorSpaceRule(
        template_id="adobe.substance_painter",
        label="Adobe Substance 3D Painter",
        env_vars=("OCIO",),
        search_paths=(
            "resources/color_management",
            "resources/color-management",
            "resources/ocio",
        ),
        extensions=(".ocio",),
    ),
)


@dataclass(slots=True)
class ColorSpaceScanService:
    """DCC ツールの同封色空間を走査する。"""

    repository: ToolConfigRepository
    rez_repository: RezPackageRepository = field(default_factory=RezPackageRepository)

    def __init__(
        self,
        repository: ToolConfigRepository | None = None,
        rez_repository: RezPackageRepository | None = None,
    ) -> None:
        self.repository = repository or ToolConfigRepository()
        self.rez_repository = rez_repository or RezPackageRepository()

    def scan_for_rez_package(self, spec: RezPackageSpec) -> list[ColorSpaceCandidate]:
        tool = self._find_tool_by_package(spec.name)
        executable = self._resolve_executable_path(spec, tool)
        install_root = self._resolve_install_root(executable)

        rules = self._match_rules(spec.name, tool)
        candidates: list[ColorSpaceCandidate] = []
        for rule in rules:
            candidates.extend(self._scan_with_rule(rule, install_root))

        if not candidates and install_root:
            candidates.extend(self._scan_generic(install_root))

        return self._deduplicate(candidates)

    def _find_tool_by_package(self, package_name: str) -> Optional[RegisteredTool]:
        tools, _ = self.repository.load_all()
        for tool in tools:
            if not tool.template_id:
                continue
            normalized = RezPackageRepository.normalize_template_id(tool.template_id)
            if normalized == package_name:
                return tool
        return None

    @staticmethod
    def _resolve_executable_path(
        spec: RezPackageSpec, tool: Optional[RegisteredTool]
    ) -> Optional[Path]:
        if tool and tool.executable_path:
            return tool.executable_path

        package_file = spec.path / "package.py"
        if not package_file.exists():
            return None
        try:
            content = package_file.read_text(encoding="utf-8")
        except OSError:
            return None
        pattern = re.compile(r'EXECUTE_[A-Z0-9_]+_EXE\"\\]\\s*=\\s*r?\"([^\"]+)\"')
        match = pattern.search(content)
        if not match:
            return None
        return Path(match.group(1))

    @staticmethod
    def _resolve_install_root(executable: Optional[Path]) -> Optional[Path]:
        if not executable:
            return None
        parent = executable.parent
        if parent.name.lower() in {"bin", "bin64", "bin32", "support files"}:
            return parent.parent
        return parent

    @staticmethod
    def _match_rules(
        package_name: str, tool: Optional[RegisteredTool]
    ) -> list[ColorSpaceRule]:
        template_id = tool.template_id if tool else None
        matches = []
        for rule in _RULES:
            normalized = RezPackageRepository.normalize_template_id(rule.template_id)
            if template_id == rule.template_id or normalized == package_name:
                matches.append(rule)
        return matches

    def _scan_with_rule(
        self, rule: ColorSpaceRule, install_root: Optional[Path]
    ) -> list[ColorSpaceCandidate]:
        if not install_root:
            return self._fallback_candidates(rule, None)

        found: list[ColorSpaceCandidate] = []
        config_files = self._collect_config_files(install_root, rule)
        if not config_files:
            return self._fallback_candidates(rule, install_root)

        for config in config_files:
            for env_var in rule.env_vars:
                label = self._build_label(rule.label, env_var, config, install_root)
                found.append(
                    ColorSpaceCandidate(
                        env_var=env_var,
                        label=label,
                        config_path=config,
                        source=rule.template_id,
                    )
                )
        return found

    def _collect_config_files(
        self, install_root: Path, rule: ColorSpaceRule
    ) -> list[Path]:
        configs: list[Path] = []
        for relative in rule.search_paths:
            target = install_root / relative
            if target.is_file():
                if target.suffix.lower() in rule.extensions:
                    configs.append(target)
                continue
            if not target.is_dir():
                continue
            configs.extend(self._scan_directory(target, rule.extensions))
        return configs

    @staticmethod
    def _scan_directory(directory: Path, extensions: Iterable[str]) -> list[Path]:
        try:
            entries = list(directory.iterdir())
        except OSError:
            return []
        results = []
        extension_set = {ext.lower() for ext in extensions}
        for entry in entries:
            if entry.is_file() and entry.suffix.lower() in extension_set:
                results.append(entry)
        if results:
            return results
        for entry in entries:
            if entry.is_dir() and entry.name.lower() in {"config", "configs"}:
                results.extend(
                    [child for child in entry.iterdir() if child.suffix.lower() in extension_set]
                )
        return results

    def _scan_generic(self, install_root: Path) -> list[ColorSpaceCandidate]:
        ocio_paths = [
            install_root / "config.ocio",
            install_root / "ocio" / "config.ocio",
            install_root / "color_management" / "config.ocio",
            install_root / "colormanagement" / "config.ocio",
        ]
        configs = [path for path in ocio_paths if path.exists()]
        if not configs:
            return []
        candidates = []
        for config in configs:
            label = self._build_label("汎用 OCIO", "OCIO", config, install_root)
            candidates.append(
                ColorSpaceCandidate(
                    env_var="OCIO",
                    label=label,
                    config_path=config,
                    source="generic",
                )
            )
        return candidates

    @staticmethod
    def _fallback_candidates(
        rule: ColorSpaceRule, install_root: Optional[Path]
    ) -> list[ColorSpaceCandidate]:
        candidates = []
        for env_var in rule.env_vars:
            label = (
                f"{env_var} ({rule.label}: 同梱構成が見つかりませんでした)"
                if install_root
                else f"{env_var} ({rule.label}: インストール場所を特定できませんでした)"
            )
            candidates.append(
                ColorSpaceCandidate(
                    env_var=env_var,
                    label=label,
                    config_path=None,
                    source=rule.template_id,
                )
            )
        return candidates

    @staticmethod
    def _build_label(
        label: str, env_var: str, config: Path, install_root: Path
    ) -> str:
        try:
            relative = config.relative_to(install_root)
        except ValueError:
            relative = config
        return f"{env_var} ({label}: {relative})"

    @staticmethod
    def _deduplicate(
        candidates: Iterable[ColorSpaceCandidate],
    ) -> list[ColorSpaceCandidate]:
        seen: set[tuple[str, Optional[Path]]] = set()
        unique: list[ColorSpaceCandidate] = []
        for candidate in candidates:
            key = (candidate.env_var, candidate.config_path)
            if key in seen:
                continue
            seen.add(key)
            unique.append(candidate)
        return unique
