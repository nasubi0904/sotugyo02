"""ツール登録と環境定義を統合するファサード。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import importlib
import json
import logging
from pathlib import Path
import re
import tomllib
from typing import Any, Dict, Iterable, List, Optional

from ..models import (
    RegisteredTool,
    RezPackageSpec,
    TemplateInstallationCandidate,
    ToolEnvironmentDefinition,
)
from ..repositories.config import ToolConfigRepository
from ..repositories.rez_packages import (
    ProjectRezPackageRepository,
    RezPackageRepository,
    RezPackageSyncResult,
    RezPackageValidationResult,
)
from ..templates.gateway import TemplateGateway
from ....infrastructure.paths.storage import get_tool_environment_dir
from .environment import ToolEnvironmentRegistryService
from .registry import ToolRegistryService
from .rez import RezPackageQueryService, RezQueryResult


LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class ToolEnvironmentService:
    """ツール登録と環境定義をまとめて提供する。"""

    registry_service: ToolRegistryService
    environment_service: ToolEnvironmentRegistryService
    template_gateway: TemplateGateway
    rez_repository: RezPackageRepository
    rez_query_service: RezPackageQueryService

    def __init__(
        self,
        repository: ToolConfigRepository | None = None,
        *,
        registry_service: ToolRegistryService | None = None,
        environment_service: ToolEnvironmentRegistryService | None = None,
        template_gateway: TemplateGateway | None = None,
        rez_repository: RezPackageRepository | None = None,
        rez_query_service: RezPackageQueryService | None = None,
    ) -> None:
        repo = repository or ToolConfigRepository()
        self.registry_service = registry_service or ToolRegistryService(repo)
        self.environment_service = (
            environment_service or ToolEnvironmentRegistryService(repo)
        )
        self.template_gateway = template_gateway or TemplateGateway()
        self.rez_repository = rez_repository or RezPackageRepository()
        self.rez_query_service = rez_query_service or RezPackageQueryService()

    # ------------------------------------------------------------------
    # ツール登録
    # ------------------------------------------------------------------
    def list_tools(self) -> List[RegisteredTool]:
        self._sync_from_environment_dir()
        return self.registry_service.list_tools()

    def get_tool(self, tool_id: str) -> Optional[RegisteredTool]:
        return self.registry_service.get_tool(tool_id)

    def register_tool(
        self,
        *,
        display_name: str,
        executable_path: Path | str,
        template_id: str | None = None,
        version: str | None = None,
    ) -> RegisteredTool:
        normalized_path = self._normalize_executable_path(executable_path)
        if not normalized_path.exists():
            raise ValueError(f"実行ファイルが見つかりません: {normalized_path}")
        resolved_template_id = self._ensure_template_id(template_id, display_name)
        tool = self.registry_service.register(
            display_name=display_name,
            executable_path=normalized_path,
            template_id=resolved_template_id,
            version=version,
        )
        candidate = TemplateInstallationCandidate(
            template_id=resolved_template_id,
            display_name=tool.display_name,
            executable_path=tool.executable_path,
            version=tool.version,
        )
        self.rez_repository.register_candidate(candidate)
        self._sync_from_environment_dir()
        return tool

    def remove_tool(self, tool_id: str) -> bool:
        tool = self.registry_service.get_tool(tool_id)
        removed = self.registry_service.remove(tool_id)
        if removed and tool is not None:
            template_id = tool.template_id or tool.tool_id
            package_name = self.rez_repository.normalize_template_id(template_id)
            self.rez_repository.remove_package(package_name)
            self._sync_from_environment_dir()
        return removed

    # ------------------------------------------------------------------
    # 環境定義
    # ------------------------------------------------------------------
    def list_environments(self) -> List[ToolEnvironmentDefinition]:
        self._sync_from_environment_dir()
        return self.environment_service.list_environments()

    def save_environment(
        self,
        *,
        name: str,
        tool_id: str,
        version_label: str,
        environment_id: Optional[str] = None,
        template_id: Optional[str] = None,
        rez_packages: Optional[Iterable[str]] = None,
        rez_variants: Optional[Iterable[str]] = None,
        rez_environment: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, object]] = None,
    ) -> ToolEnvironmentDefinition:
        self._sync_from_environment_dir()
        tools = self.registry_service.list_tools()
        environments = self.environment_service.list_environments()
        return self.environment_service.save(
            name=name,
            tool_id=tool_id,
            version_label=version_label,
            tools=tools,
            environments=environments,
            environment_id=environment_id,
            template_id=template_id,
            rez_packages=rez_packages,
            rez_variants=rez_variants,
            rez_environment=rez_environment,
            metadata=metadata,
        )

    def remove_environment(self, environment_id: str) -> bool:
        self._sync_from_environment_dir()
        return self.environment_service.remove(environment_id)

    # ------------------------------------------------------------------
    # テンプレート連携
    # ------------------------------------------------------------------
    def list_templates(self) -> List[Dict[str, str]]:
        return self.template_gateway.list_templates()

    def discover_template_installations(
        self, template_id: str
    ) -> List[TemplateInstallationCandidate]:
        return self.template_gateway.discover_installations(template_id)

    def load_template_environment(self, template_id: str) -> Dict[str, object]:
        return self.template_gateway.load_environment_payload(template_id)

    def validate_rez_environment(
        self,
        *,
        packages: Iterable[str],
        variants: Iterable[str] | None = None,
        environment: Optional[Dict[str, str]] = None,
    ):
        return self.environment_service.validate_rez_environment(
            packages=packages,
            variants=variants,
            environment=environment,
        )

    # ------------------------------------------------------------------
    # Rez パッケージ
    # ------------------------------------------------------------------
    def list_rez_packages(self) -> List[RezPackageSpec]:
        return self.rez_repository.list_packages()

    def list_project_rez_packages(self, project_root: Path) -> List[RezPackageSpec]:
        return ProjectRezPackageRepository(project_root).list_packages()

    def sync_rez_packages_to_project(
        self, project_root: Path, packages: Iterable[str]
    ) -> RezPackageSyncResult:
        return self.rez_repository.sync_packages_to_project(project_root, packages)

    def validate_project_rez_packages(
        self, project_root: Path
    ) -> RezPackageValidationResult:
        return ProjectRezPackageRepository(project_root).validate()

    def save_project_rez_package(
        self,
        project_root: Path,
        project_name: str,
        requires: Iterable[str],
        *,
        version: str = "1.0",
    ) -> Optional[Path]:
        normalized_requires = [
            entry.strip() for entry in requires if isinstance(entry, str) and entry.strip()
        ]
        if not normalized_requires:
            return None
        repository = ProjectRezPackageRepository(project_root)
        return repository.write_project_package(
            project_name,
            normalized_requires,
            version=version,
        )

    def check_project_rez_requirements(
        self,
        project_root: Path,
        project_name: str,
        *,
        version: str = "1.0",
    ) -> RezQueryResult:
        repository = ProjectRezPackageRepository(project_root)
        requirements = repository.read_project_manifest_requirements(
            project_name,
            version=version,
        )
        return self.rez_query_service.check_requirements(requirements)

    # ------------------------------------------------------------------
    # ユーティリティ
    # ------------------------------------------------------------------
    def _normalize_executable_path(self, value: Path | str) -> Path:
        path = Path(value)
        try:
            resolved = path.expanduser()
        except RuntimeError:
            resolved = path
        if not resolved.is_absolute():
            resolved = resolved.resolve()
        return resolved

    def _sync_from_environment_dir(self) -> None:
        specs = self.rez_repository.list_package_entries()
        package_map = {self._build_rez_tool_id(spec): spec for spec in specs}

        tools, environments = self.registry_service.repository.load_all()
        environments = self._merge_environment_definitions(
            environments,
            self._load_environment_definitions_from_dir(specs),
        )
        tool_map = {tool.tool_id: tool for tool in tools}
        tool_by_package: Dict[str, RegisteredTool] = {}
        for tool in tools:
            if tool.template_id:
                tool_by_package[
                    self.rez_repository.normalize_template_id(tool.template_id)
                ] = tool
        env_map = {env.tool_id: env for env in environments}
        env_by_package: Dict[str, ToolEnvironmentDefinition] = {}
        for env in environments:
            if not env.environment_id.startswith("rez:"):
                continue
            for package in env.rez_packages:
                env_by_package[package] = env

        now = datetime.utcnow()
        synced_tools: List[RegisteredTool] = []
        synced_envs: List[ToolEnvironmentDefinition] = [
            env for env in environments if not env.environment_id.startswith("rez:")
        ]

        for tool_id, spec in sorted(package_map.items()):
            resolved_executable = self.rez_repository.resolve_executable(spec)
            tool = (
                tool_map.get(tool_id)
                or tool_map.get(spec.name)
                or tool_by_package.get(spec.name)
            )
            if tool is None:
                tool = RegisteredTool(
                    tool_id=tool_id,
                    display_name=spec.name,
                    executable_path=resolved_executable or (spec.path / "package.py"),
                    template_id=None,
                    version=spec.version,
                    created_at=now,
                    updated_at=now,
                )
            else:
                tool.tool_id = tool_id
                if not tool.display_name:
                    tool.display_name = spec.name
                if resolved_executable is not None:
                    tool.executable_path = resolved_executable
                elif not tool.executable_path.exists():
                    tool.executable_path = spec.path / "package.py"
                tool.version = spec.version
                tool.updated_at = now
            synced_tools.append(tool)

            environment = (
                env_map.get(tool_id)
                or env_map.get(spec.name)
                or env_by_package.get(spec.name)
            )
            if environment is None:
                environment = ToolEnvironmentDefinition(
                    environment_id=f"rez:{tool_id}",
                    name=self._build_rez_environment_name(spec),
                    tool_id=tool_id,
                    version_label=spec.version or "local",
                    rez_packages=(spec.name,),
                    rez_variants=(),
                    rez_environment={},
                    metadata={},
                    created_at=now,
                    updated_at=now,
                )
            else:
                environment.tool_id = tool_id
                environment.name = self._build_rez_environment_name(spec)
                environment.version_label = spec.version or environment.version_label or "local"
                environment.rez_packages = (spec.name,)
                environment.environment_id = f"rez:{tool_id}"
                environment.updated_at = now
            synced_envs.append(environment)

        self.registry_service.repository.save_all(synced_tools, synced_envs)

    @staticmethod
    def _merge_environment_definitions(
        base: List[ToolEnvironmentDefinition],
        additions: List[ToolEnvironmentDefinition],
    ) -> List[ToolEnvironmentDefinition]:
        merged = {env.environment_id: env for env in base}
        for env in additions:
            merged[env.environment_id] = env
        return list(merged.values())

    @staticmethod
    def _build_rez_tool_id(spec: RezPackageSpec) -> str:
        version_label = spec.version or "local"
        return f"{spec.name}@{version_label}"

    @staticmethod
    def _build_rez_environment_name(spec: RezPackageSpec) -> str:
        if spec.version:
            return f"Rez: {spec.name} ({spec.version})"
        return f"Rez: {spec.name}"

    def _ensure_template_id(self, template_id: str | None, display_name: str) -> str:
        if template_id:
            return template_id
        slug = self._normalize_custom_template_id(display_name)
        return f"custom.{slug}" if slug else "custom.tool"

    @staticmethod
    def _normalize_custom_template_id(display_name: str) -> str:
        cleaned = display_name.strip().lower()
        cleaned = re.sub(r"\s+", "_", cleaned)
        cleaned = re.sub(r"[^a-z0-9_]", "", cleaned)
        return cleaned

    def _load_environment_definitions_from_dir(
        self,
        specs: Iterable[RezPackageSpec],
    ) -> List[ToolEnvironmentDefinition]:
        env_dir = get_tool_environment_dir()
        env_files = self._collect_environment_files(env_dir)
        if not env_files:
            return []
        spec_lookup = self._build_spec_lookup(specs)
        environments: List[ToolEnvironmentDefinition] = []
        for env_path in env_files:
            payload = self._read_environment_payload(env_path)
            if payload is None:
                continue
            environment = self._convert_environment_payload(payload, env_path, spec_lookup)
            if environment is None:
                continue
            environments.append(environment)
        return environments

    @staticmethod
    def _collect_environment_files(root: Path) -> List[Path]:
        if not root.exists():
            return []
        try:
            entries = [entry for entry in root.iterdir() if entry.is_file()]
        except OSError:
            return []
        preferred = [
            entry
            for entry in entries
            if entry.suffix.lower() in {".json", ".yml", ".yaml", ".toml"}
        ]
        return sorted(preferred or entries)

    @staticmethod
    def _build_spec_lookup(
        specs: Iterable[RezPackageSpec],
    ) -> Dict[tuple[str, str | None], RezPackageSpec]:
        lookup: Dict[tuple[str, str | None], RezPackageSpec] = {}
        for spec in specs:
            lookup[(spec.name, spec.version)] = spec
        return lookup

    def _read_environment_payload(self, path: Path) -> Optional[Dict[str, Any]]:
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            LOGGER.warning("環境定義ファイルの読み込みに失敗しました: %s", path, exc_info=True)
            return None
        suffix = path.suffix.lower()
        try:
            if suffix == ".toml":
                payload = tomllib.loads(content)
            elif suffix in {".yml", ".yaml"}:
                payload = self._load_yaml_payload(content, path)
            else:
                payload = json.loads(content)
        except (ValueError, json.JSONDecodeError) as exc:
            LOGGER.warning(
                "環境定義ファイルの解析に失敗しました: %s (%s)",
                path,
                exc,
                exc_info=True,
            )
            return None
        if isinstance(payload, dict):
            return payload
        LOGGER.warning("環境定義ファイルが辞書形式ではありません: %s", path)
        return None

    @staticmethod
    def _load_yaml_payload(content: str, path: Path) -> Dict[str, Any]:
        if importlib.util.find_spec("yaml") is None:
            LOGGER.warning("YAML の読み込みに失敗しました: PyYAML が見つかりません (%s)", path)
            return {}
        yaml_module = importlib.import_module("yaml")
        payload = yaml_module.safe_load(content)
        if isinstance(payload, dict):
            return payload
        return {}

    def _convert_environment_payload(
        self,
        data: Dict[str, Any],
        path: Path,
        spec_lookup: Dict[tuple[str, str | None], RezPackageSpec],
    ) -> Optional[ToolEnvironmentDefinition]:
        name = str(data.get("name") or path.stem).strip() or path.stem
        raw_tool_id = data.get("tool_id")
        package_name = data.get("package") or data.get("rez_package")
        package_version = data.get("package_version")
        tool_id = str(raw_tool_id).strip() if raw_tool_id else ""
        version_label = str(data.get("version_label") or "").strip()
        spec = None
        if package_name:
            spec = self._find_spec_for_payload(spec_lookup, str(package_name), package_version)
        if not tool_id and package_name:
            resolved_version = version_label or (spec.version if spec else package_version) or "local"
            tool_id = f"{package_name}@{resolved_version}"
        if not version_label and spec is not None:
            version_label = spec.version or "local"
        if not version_label and package_version:
            version_label = str(package_version)
        if not tool_id:
            LOGGER.warning("ツール ID を解決できませんでした: %s", path)
            return None
        environment_id = str(data.get("environment_id") or f"file:{path.stem}")
        template_id = data.get("template_id")
        rez_packages = self._normalize_sequence(
            data.get("rez_packages") or ([package_name] if package_name else [])
        )
        rez_variants = self._normalize_sequence(data.get("rez_variants") or [])
        rez_environment = self._normalize_environment(
            data.get("rez_environment") or self._parse_environment_variables(data)
        ) or {}
        metadata = dict(data.get("metadata") or {})
        if "launch_arguments" in data:
            metadata["launch_arguments"] = data.get("launch_arguments")
        if "required_plugins" in data:
            metadata["required_plugins"] = data.get("required_plugins")
        if "environment_variables" in data:
            metadata["environment_variables"] = data.get("environment_variables")
        metadata["source_path"] = str(path)
        now = datetime.utcnow()
        return ToolEnvironmentDefinition(
            environment_id=environment_id,
            name=name,
            tool_id=tool_id,
            version_label=version_label or "local",
            template_id=str(template_id) if template_id else None,
            rez_packages=rez_packages or (),
            rez_variants=rez_variants or (),
            rez_environment=rez_environment,
            metadata=metadata,
            created_at=now,
            updated_at=now,
        )

    @staticmethod
    def _find_spec_for_payload(
        spec_lookup: Dict[tuple[str, str | None], RezPackageSpec],
        package_name: str,
        package_version: Any,
    ) -> Optional[RezPackageSpec]:
        version_text = str(package_version).strip() if package_version else None
        if (package_name, version_text) in spec_lookup:
            return spec_lookup[(package_name, version_text)]
        if (package_name, None) in spec_lookup:
            return spec_lookup[(package_name, None)]
        for (name, _), spec in spec_lookup.items():
            if name == package_name:
                return spec
        return None

    @staticmethod
    def _normalize_sequence(values: Iterable[Any]) -> tuple[str, ...]:
        if not values:
            return ()
        return tuple(
            str(entry).strip()
            for entry in values
            if isinstance(entry, str) and str(entry).strip()
        )

    @staticmethod
    def _normalize_environment(values: Dict[str, Any] | None) -> Dict[str, str]:
        if not values:
            return {}
        normalized: Dict[str, str] = {}
        for key, value in values.items():
            if isinstance(key, str) and isinstance(value, str):
                normalized[key.strip()] = value.strip()
        return normalized

    @classmethod
    def _parse_environment_variables(cls, data: Dict[str, Any]) -> Dict[str, str]:
        raw = data.get("environment_variables")
        if isinstance(raw, dict):
            return cls._normalize_environment(raw)
        if isinstance(raw, str):
            return cls._parse_environment_text(raw)
        return {}

    @staticmethod
    def _parse_environment_text(text: str) -> Dict[str, str]:
        env_map: Dict[str, str] = {}
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            key = key.strip()
            value = value.strip()
            if not key:
                continue
            env_map[key] = value
        return env_map
