"""ツール登録と環境定義を統合するファサード。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import importlib.util
import json
import logging
from pathlib import Path
import re
import tomllib
from typing import Dict, Iterable, List, Optional

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
from .environment import ToolEnvironmentRegistryService
from .registry import ToolRegistryService
from .rez import RezPackageQueryService, RezQueryResult
from ....infrastructure.paths.storage import get_tool_environment_dir

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
        file_environments = self._load_environment_definitions_from_dir()
        base_environments = [
            env for env in environments if not self._is_environment_from_file(env)
        ]
        tool_map = {tool.tool_id: tool for tool in tools}
        tool_by_package: Dict[str, RegisteredTool] = {}
        for tool in tools:
            if tool.template_id:
                tool_by_package[
                    self.rez_repository.normalize_template_id(tool.template_id)
                ] = tool
        env_map = {env.tool_id: env for env in base_environments}
        env_by_package: Dict[str, ToolEnvironmentDefinition] = {}
        for env in base_environments:
            for package in env.rez_packages:
                env_by_package[package] = env

        now = datetime.utcnow()
        synced_tools: List[RegisteredTool] = []
        synced_envs: Dict[str, ToolEnvironmentDefinition] = {
            env.environment_id: env for env in base_environments if env.environment_id
        }
        for env in file_environments:
            if env.environment_id:
                synced_envs[env.environment_id] = env

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
            if environment.environment_id:
                synced_envs[environment.environment_id] = environment

        self.registry_service.repository.save_all(synced_tools, synced_envs.values())

    def _load_environment_definitions_from_dir(self) -> List[ToolEnvironmentDefinition]:
        env_dir = get_tool_environment_dir()
        if not env_dir.exists():
            return []
        try:
            files = [entry for entry in env_dir.iterdir() if entry.is_file()]
        except OSError:
            LOGGER.warning("環境定義ディレクトリの走査に失敗しました: %s", env_dir, exc_info=True)
            return []
        candidates = [
            entry
            for entry in files
            if entry.suffix.lower() in {".json", ".yml", ".yaml", ".toml"}
        ]
        definitions: List[ToolEnvironmentDefinition] = []
        for path in sorted(candidates):
            payload = self._read_environment_payload(path)
            if not isinstance(payload, dict):
                continue
            definition = self._build_environment_definition(payload, path)
            if definition is not None:
                definitions.append(definition)
        return definitions

    def _read_environment_payload(self, path: Path) -> Optional[dict]:
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            LOGGER.warning("環境定義ファイルの読み込みに失敗しました: %s", path, exc_info=True)
            return None
        suffix = path.suffix.lower()
        if suffix == ".json":
            try:
                payload = json.loads(content)
            except json.JSONDecodeError:
                LOGGER.warning("環境定義 JSON の解析に失敗しました: %s", path, exc_info=True)
                return None
        elif suffix in {".yml", ".yaml"}:
            yaml = self._load_yaml_module()
            if yaml is None:
                LOGGER.warning("PyYAML が見つからないため YAML を読み込めません: %s", path)
                return None
            payload = yaml.safe_load(content)
        elif suffix == ".toml":
            try:
                payload = tomllib.loads(content)
            except tomllib.TOMLDecodeError:
                LOGGER.warning("環境定義 TOML の解析に失敗しました: %s", path, exc_info=True)
                return None
        else:
            return None
        if isinstance(payload, dict):
            return payload
        return None

    def _build_environment_definition(
        self,
        payload: dict,
        source_path: Path,
    ) -> Optional[ToolEnvironmentDefinition]:
        now = datetime.utcnow()
        if self._looks_like_definition_payload(payload):
            definition = ToolEnvironmentDefinition.from_dict(
                self._normalize_definition_payload(payload)
            )
        else:
            definition = self._build_definition_from_payload(payload, source_path)
        if definition is None:
            return None
        if not definition.environment_id:
            definition.environment_id = f"file:{source_path.stem}"
        if not definition.name:
            definition.name = source_path.stem
        if definition.created_at.timestamp() == 0:
            definition.created_at = now
        definition.updated_at = now
        definition.metadata = self._merge_environment_metadata(
            definition.metadata,
            payload,
            source_path,
        )
        return definition

    def _build_definition_from_payload(
        self,
        payload: dict,
        source_path: Path,
    ) -> Optional[ToolEnvironmentDefinition]:
        package_name = self._normalize_payload_package(payload)
        if not package_name:
            return None
        version_label = self._normalize_payload_version(payload) or "local"
        tool_id = f"{package_name}@{version_label}"
        rez_packages = self._normalize_payload_sequence(payload.get("rez_packages"))
        if not rez_packages:
            rez_packages = (package_name,)
        rez_variants = self._normalize_payload_sequence(payload.get("rez_variants"))
        rez_environment = self._normalize_payload_environment(
            payload.get("rez_environment")
        )
        if rez_environment is None:
            rez_environment = self._parse_environment_variables(
                payload.get("environment_variables")
            )
        now = datetime.utcnow()
        return ToolEnvironmentDefinition(
            environment_id=str(payload.get("environment_id", "")),
            name=str(payload.get("name", source_path.stem)),
            tool_id=tool_id,
            version_label=version_label,
            template_id=payload.get("template_id") or None,
            rez_packages=rez_packages,
            rez_variants=rez_variants or (),
            rez_environment=rez_environment or {},
            metadata=dict(payload.get("metadata", {}))
            if isinstance(payload.get("metadata"), dict)
            else {},
            created_at=now,
            updated_at=now,
        )

    @staticmethod
    def _looks_like_definition_payload(payload: dict) -> bool:
        return "tool_id" in payload or "environment_id" in payload

    @staticmethod
    def _normalize_definition_payload(payload: dict) -> dict:
        normalized = dict(payload)
        rez_packages = normalized.get("rez_packages")
        if isinstance(rez_packages, str):
            normalized["rez_packages"] = [rez_packages]
        rez_variants = normalized.get("rez_variants")
        if isinstance(rez_variants, str):
            normalized["rez_variants"] = [rez_variants]
        return normalized

    @staticmethod
    def _normalize_payload_package(payload: dict) -> str:
        package = payload.get("package") or payload.get("package_name")
        if isinstance(package, str) and package.strip():
            return package.strip()
        rez_packages = payload.get("rez_packages")
        if isinstance(rez_packages, str):
            return rez_packages.strip()
        if isinstance(rez_packages, list):
            for entry in rez_packages:
                if isinstance(entry, str) and entry.strip():
                    return entry.strip()
        return ""

    @staticmethod
    def _normalize_payload_version(payload: dict) -> str:
        for key in ("package_version", "version_label", "version"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    @staticmethod
    def _normalize_payload_sequence(values: object) -> Optional[tuple[str, ...]]:
        if values is None:
            return None
        if isinstance(values, str):
            values = [values]
        if not isinstance(values, list):
            return None
        normalized = tuple(
            entry.strip()
            for entry in values
            if isinstance(entry, str) and entry.strip()
        )
        return normalized or None

    @staticmethod
    def _normalize_payload_environment(values: object) -> Optional[Dict[str, str]]:
        if not isinstance(values, dict):
            return None
        normalized: Dict[str, str] = {}
        for key, value in values.items():
            if isinstance(key, str) and isinstance(value, str):
                normalized[key.strip()] = value.strip()
        return normalized

    @staticmethod
    def _parse_environment_variables(value: object) -> Dict[str, str]:
        if not isinstance(value, str) or not value.strip():
            return {}
        env_map: Dict[str, str] = {}
        for raw_line in value.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, entry_value = line.split("=", 1)
            key = key.strip()
            entry_value = entry_value.strip()
            if key:
                env_map[key] = entry_value
        return env_map

    @staticmethod
    def _merge_environment_metadata(
        base: Dict[str, object],
        payload: dict,
        source_path: Path,
    ) -> Dict[str, object]:
        metadata = dict(base)
        metadata["environment_file"] = str(source_path)
        if "environment_variables" in payload:
            metadata["environment_variables"] = payload.get("environment_variables")
        if "launch_arguments" in payload:
            metadata["launch_arguments"] = payload.get("launch_arguments")
        if "required_plugins" in payload:
            metadata["required_plugins"] = payload.get("required_plugins")
        return metadata

    @staticmethod
    def _is_environment_from_file(environment: ToolEnvironmentDefinition) -> bool:
        return bool(environment.metadata.get("environment_file"))

    @staticmethod
    def _load_yaml_module():
        if importlib.util.find_spec("yaml") is None:
            return None
        import yaml  # type: ignore

        return yaml

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
