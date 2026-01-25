"""ツール登録と環境定義を統合するファサード。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re
from typing import Dict, Iterable, List, Optional

from ..models import (
    TOOL_ENVIRONMENT_METADATA_KEY,
    RegisteredTool,
    RezPackageSpec,
    TemplateInstallationCandidate,
    ToolEnvironmentDefinition,
    collect_node_input_names,
    merge_node_inputs,
    normalize_node_input_name,
    normalize_node_inputs,
    normalize_required_plugins,
    normalize_text_payload,
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
            for package in env.rez_packages:
                env_by_package[package] = env

        now = datetime.utcnow()
        synced_tools: List[RegisteredTool] = []
        synced_envs: List[ToolEnvironmentDefinition] = []

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

        custom_envs = self._load_custom_environments(synced_tools)
        merged_envs = self._merge_environment_definitions(synced_envs, custom_envs)
        self.registry_service.repository.save_all(synced_tools, merged_envs)

    @staticmethod
    def _build_rez_tool_id(spec: RezPackageSpec) -> str:
        version_label = spec.version or "local"
        return f"{spec.name}@{version_label}"

    @staticmethod
    def _build_rez_tool_id_from_payload(package: str, version_label: str) -> str:
        return f"{package}@{version_label or 'local'}"

    @staticmethod
    def _build_rez_environment_name(spec: RezPackageSpec) -> str:
        if spec.version:
            return f"Rez: {spec.name} ({spec.version})"
        return f"Rez: {spec.name}"

    def _load_custom_environments(
        self, tools: Iterable[RegisteredTool]
    ) -> List[ToolEnvironmentDefinition]:
        tool_map = {tool.tool_id: tool for tool in tools}
        env_dir = get_tool_environment_dir()
        if not env_dir.exists():
            return []
        envs: List[ToolEnvironmentDefinition] = []
        try:
            entries = [entry for entry in env_dir.iterdir() if entry.is_file()]
        except OSError:
            LOGGER.warning("環境定義ディレクトリの走査に失敗しました: %s", env_dir)
            return []
        for entry in sorted(entries):
            if entry.suffix.lower() != ".json":
                continue
            payload = self._read_environment_payload(entry)
            if payload is None:
                continue
            definition = self._build_environment_definition_from_payload(
                payload, entry, tool_map
            )
            if definition is None:
                continue
            envs.append(definition)
        return envs

    def _read_environment_payload(self, path: Path) -> Optional[Dict[str, object]]:
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            LOGGER.warning("環境定義ファイルの読み込みに失敗しました: %s", path)
            return None
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            LOGGER.warning("環境定義ファイルの解析に失敗しました: %s", path)
            return None
        if not isinstance(payload, dict):
            return None
        return payload

    def _build_environment_definition_from_payload(
        self,
        payload: Dict[str, object],
        source_path: Path,
        tool_map: Dict[str, RegisteredTool],
    ) -> Optional[ToolEnvironmentDefinition]:
        package = payload.get("package")
        if not isinstance(package, str) or not package.strip():
            LOGGER.warning("環境定義に package が不足しています: %s", source_path)
            return None
        package_version = payload.get("package_version")
        version_label = (
            str(package_version).strip()
            if isinstance(package_version, str) and package_version.strip()
            else "local"
        )
        tool_id = self._build_rez_tool_id_from_payload(package, version_label)
        if tool_id not in tool_map:
            LOGGER.warning(
                "環境定義が参照するツールが見つかりませんでした: %s (%s)",
                package,
                source_path,
            )
            return None
        env_id = payload.get("environment_id")
        if isinstance(env_id, str) and env_id.strip():
            environment_id = env_id.strip()
        else:
            environment_id = f"env:{tool_id}:{source_path.stem}"
        name = payload.get("name")
        display_name = (
            name.strip()
            if isinstance(name, str) and name.strip()
            else source_path.stem
        )

        env_vars_payload = normalize_text_payload(payload.get("environment_variables"))
        launch_payload = normalize_text_payload(payload.get("launch_arguments"))
        required_plugins = normalize_required_plugins(payload.get("required_plugins"))
        node_inputs = normalize_node_inputs(payload.get("node_inputs"))
        extra_inputs: List[str] = []
        extra_inputs.extend(collect_node_input_names(env_vars_payload["tokens"]))
        extra_inputs.extend(collect_node_input_names(launch_payload["tokens"]))
        for entry in required_plugins:
            if entry.get("path_type") == "node":
                input_name = entry.get("input_name")
                if isinstance(input_name, str):
                    normalized = normalize_node_input_name(input_name)
                    if normalized:
                        extra_inputs.append(normalized)
        merged_inputs = merge_node_inputs(node_inputs, extra_inputs)
        tool_payload = {
            "environment_id": environment_id,
            "name": display_name,
            "package": package,
            "package_version": version_label,
            "environment_variables": env_vars_payload,
            "launch_arguments": launch_payload,
            "required_plugins": required_plugins,
            "node_inputs": merged_inputs,
            "schema_version": payload.get("schema_version", 1),
        }
        metadata = {TOOL_ENVIRONMENT_METADATA_KEY: tool_payload}
        return ToolEnvironmentDefinition(
            environment_id=environment_id,
            name=display_name,
            tool_id=tool_id,
            version_label=version_label,
            template_id=None,
            rez_packages=(package,),
            rez_variants=(),
            rez_environment={},
            metadata=metadata,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

    @staticmethod
    def _merge_environment_definitions(
        base_envs: Iterable[ToolEnvironmentDefinition],
        custom_envs: Iterable[ToolEnvironmentDefinition],
    ) -> List[ToolEnvironmentDefinition]:
        env_map = {env.environment_id: env for env in base_envs}
        for env in custom_envs:
            env_map[env.environment_id] = env
        return list(env_map.values())

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
