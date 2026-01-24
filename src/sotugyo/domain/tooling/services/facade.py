"""ツール登録と環境定義を統合するファサード。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re
from typing import Dict, Iterable, List, Optional

from ..models import (
    RegisteredTool,
    RezPackageSpec,
    TemplateInstallationCandidate,
    ToolEnvironmentDefinition,
)
from ..repositories.config import ToolConfigRepository
from ..repositories.environment_files import ToolEnvironmentFileRepository
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


@dataclass(slots=True)
class ToolEnvironmentService:
    """ツール登録と環境定義をまとめて提供する。"""

    registry_service: ToolRegistryService
    environment_service: ToolEnvironmentRegistryService
    template_gateway: TemplateGateway
    rez_repository: RezPackageRepository
    rez_query_service: RezPackageQueryService
    environment_file_repository: ToolEnvironmentFileRepository

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
        self.environment_file_repository = ToolEnvironmentFileRepository()

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
        existing_envs = {env.environment_id: env for env in environments}
        tool_by_package: Dict[str, RegisteredTool] = {}
        for tool in tools:
            if tool.template_id:
                tool_by_package[
                    self.rez_repository.normalize_template_id(tool.template_id)
                ] = tool

        now = datetime.utcnow()
        synced_tools: List[RegisteredTool] = []
        synced_envs: Dict[str, ToolEnvironmentDefinition] = {}

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
            env_id = f"rez:{tool_id}"
            existing_env = existing_envs.get(env_id)
            default_env = ToolEnvironmentDefinition(
                environment_id=env_id,
                name=self._build_rez_environment_name(spec),
                tool_id=tool_id,
                version_label=spec.version or "local",
                rez_packages=(spec.name,),
                rez_variants=(),
                rez_environment={},
                metadata=dict(existing_env.metadata) if existing_env else {},
                created_at=existing_env.created_at if existing_env else now,
                updated_at=now,
            )
            synced_envs[default_env.environment_id] = default_env

        synced_tool_ids = {tool.tool_id for tool in synced_tools}
        file_payloads = self.environment_file_repository.load_all()
        for path, payload in file_payloads:
            tool_payload = payload.get("tool", {}) if isinstance(payload, dict) else {}
            tool_id = tool_payload.get("tool_id") if isinstance(tool_payload, dict) else None
            package_name = tool_payload.get("package") if isinstance(tool_payload, dict) else None
            version_label = tool_payload.get("version") if isinstance(tool_payload, dict) else None
            if not isinstance(tool_id, str) or not tool_id:
                if isinstance(package_name, str) and package_name:
                    tool_id = self.build_rez_tool_id(package_name, version_label)
            if not tool_id or tool_id not in synced_tool_ids:
                continue
            env_id = payload.get("environment_id")
            if not isinstance(env_id, str) or not env_id:
                continue
            name = payload.get("name") if isinstance(payload.get("name"), str) else path.stem
            rez_packages = (package_name,) if isinstance(package_name, str) and package_name else ()
            existing_env = existing_envs.get(env_id)
            metadata = dict(existing_env.metadata) if existing_env else {}
            raw_payload = payload.get("payload")
            if isinstance(raw_payload, dict):
                metadata["tool_environment_payload"] = dict(raw_payload)
            metadata["environment_file"] = path.name
            custom_env = ToolEnvironmentDefinition(
                environment_id=env_id,
                name=name or path.stem,
                tool_id=tool_id,
                version_label=version_label or "local",
                rez_packages=rez_packages,
                rez_variants=(),
                rez_environment={},
                metadata=metadata,
                created_at=existing_env.created_at if existing_env else now,
                updated_at=now,
            )
            synced_envs[custom_env.environment_id] = custom_env

        self.registry_service.repository.save_all(synced_tools, synced_envs.values())

    @staticmethod
    def _build_rez_tool_id(spec: RezPackageSpec) -> str:
        version_label = spec.version or "local"
        return f"{spec.name}@{version_label}"

    @staticmethod
    def build_rez_tool_id(package_name: str, version_label: str | None) -> str:
        """パッケージ名とバージョンからツール ID を構成する。"""

        version = version_label or "local"
        return f"{package_name}@{version}"

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
