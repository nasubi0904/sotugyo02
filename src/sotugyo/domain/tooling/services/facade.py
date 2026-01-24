"""ツール登録と環境定義を統合するファサード。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import importlib
import importlib.util
import json
import logging
from pathlib import Path
import re
from typing import Dict, Iterable, List, Optional

import tomllib

from ....infrastructure.paths.storage import get_tool_environment_dir
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
        environments = self._merge_environment_definitions(environments)
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

        self.registry_service.repository.save_all(synced_tools, synced_envs)

    def _merge_environment_definitions(
        self,
        environments: List[ToolEnvironmentDefinition],
    ) -> List[ToolEnvironmentDefinition]:
        file_environments = self._load_environment_definitions_from_dir()
        if not file_environments:
            return environments
        env_map = {env.environment_id: env for env in environments}
        for env in file_environments:
            env_map[env.environment_id] = env
        return list(env_map.values())

    def _load_environment_definitions_from_dir(self) -> List[ToolEnvironmentDefinition]:
        env_dir = get_tool_environment_dir()
        if not env_dir.exists():
            return []
        files = self._collect_environment_files(env_dir)
        definitions: List[ToolEnvironmentDefinition] = []
        for path in files:
            payload = self._read_environment_payload(path)
            if payload is None:
                continue
            definitions.extend(self._convert_payload_to_definitions(path, payload))
        return definitions

    @staticmethod
    def _collect_environment_files(root: Path) -> List[Path]:
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

    def _read_environment_payload(self, path: Path) -> object | None:
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            LOGGER.warning(
                "環境定義ファイルの読み込みに失敗しました: %s",
                path,
                exc_info=True,
            )
            return None
        suffix = path.suffix.lower()
        if suffix == ".json":
            return self._parse_json_payload(path, content)
        if suffix in {".yml", ".yaml"}:
            return self._parse_yaml_payload(path, content)
        if suffix == ".toml":
            return self._parse_toml_payload(path, content)
        return self._parse_json_payload(path, content)

    def _parse_json_payload(self, path: Path, content: str) -> object | None:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            LOGGER.warning(
                "環境定義 JSON の解析に失敗しました: %s",
                path,
                exc_info=True,
            )
            return None

    def _parse_yaml_payload(self, path: Path, content: str) -> object | None:
        if importlib.util.find_spec("yaml") is None:
            LOGGER.warning(
                "PyYAML が未導入のため環境定義 YAML を読み込めません: %s",
                path,
            )
            return None
        yaml_module = importlib.import_module("yaml")
        return yaml_module.safe_load(content)

    def _parse_toml_payload(self, path: Path, content: str) -> object | None:
        try:
            return tomllib.loads(content)
        except tomllib.TOMLDecodeError:
            LOGGER.warning(
                "環境定義 TOML の解析に失敗しました: %s",
                path,
                exc_info=True,
            )
            return None

    def _convert_payload_to_definitions(
        self,
        path: Path,
        payload: object,
    ) -> List[ToolEnvironmentDefinition]:
        entries: List[dict] = []
        if isinstance(payload, dict):
            raw_entries = payload.get("environments")
            if isinstance(raw_entries, list):
                entries = [entry for entry in raw_entries if isinstance(entry, dict)]
            else:
                entries = [payload]
        elif isinstance(payload, list):
            entries = [entry for entry in payload if isinstance(entry, dict)]
        definitions: List[ToolEnvironmentDefinition] = []
        for entry in entries:
            definition = self._build_environment_definition(path, entry)
            if definition is not None:
                definitions.append(definition)
        return definitions

    def _build_environment_definition(
        self,
        path: Path,
        payload: dict,
    ) -> ToolEnvironmentDefinition | None:
        name = str(payload.get("name") or path.stem)
        package_name = payload.get("package") or payload.get("rez_package")
        version_label = (
            str(payload.get("version_label") or "")
            or str(payload.get("package_version") or "")
            or str(payload.get("version") or "")
            or "local"
        )
        tool_id = str(payload.get("tool_id") or "")
        if not tool_id and package_name:
            tool_id = f"{package_name}@{version_label}"
        if not tool_id:
            LOGGER.warning("環境定義に tool_id が無いため読み込みをスキップしました: %s", path)
            return None
        environment_id = str(payload.get("environment_id") or f"file:{path.stem}")
        rez_packages = self._normalize_sequence(
            payload.get("rez_packages")
            or ([str(package_name)] if package_name else [])
        )
        rez_variants = self._normalize_sequence(payload.get("rez_variants") or [])
        rez_environment = self._normalize_environment(
            payload.get("rez_environment") or self._parse_environment_variables(
                payload.get("environment_variables")
            )
        )
        metadata = self._extract_metadata(payload)
        timestamp = datetime.utcnow()
        try:
            stat = path.stat()
            timestamp = datetime.utcfromtimestamp(stat.st_mtime)
        except OSError:
            LOGGER.debug("環境定義の更新日時取得に失敗しました: %s", path, exc_info=True)
        return ToolEnvironmentDefinition(
            environment_id=environment_id,
            name=name,
            tool_id=tool_id,
            version_label=version_label,
            template_id=payload.get("template_id") or None,
            rez_packages=rez_packages,
            rez_variants=rez_variants,
            rez_environment=rez_environment,
            metadata=metadata,
            created_at=timestamp,
            updated_at=timestamp,
        )

    @staticmethod
    def _normalize_sequence(values: object) -> tuple[str, ...]:
        if not values:
            return ()
        if isinstance(values, (list, tuple, set)):
            items = values
        else:
            items = [values]
        normalized = tuple(
            str(entry).strip()
            for entry in items
            if isinstance(entry, str) and str(entry).strip()
        )
        return normalized

    @staticmethod
    def _normalize_environment(values: object) -> Dict[str, str]:
        if not isinstance(values, dict):
            return {}
        return {
            str(key).strip(): str(value).strip()
            for key, value in values.items()
            if isinstance(key, str) and isinstance(value, str)
        }

    @staticmethod
    def _parse_environment_variables(raw: object) -> Dict[str, str]:
        if isinstance(raw, dict):
            return {
                str(key).strip(): str(value).strip()
                for key, value in raw.items()
                if isinstance(key, str) and isinstance(value, str)
            }
        if not isinstance(raw, str):
            return {}
        env_map: Dict[str, str] = {}
        for line in raw.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            env_map[key.strip()] = value.strip()
        return env_map

    @staticmethod
    def _extract_metadata(payload: dict) -> Dict[str, object]:
        metadata = {}
        raw_metadata = payload.get("metadata")
        if isinstance(raw_metadata, dict):
            metadata.update(raw_metadata)
        if "environment_variables" in payload:
            metadata["environment_variables"] = payload.get("environment_variables")
        if "launch_arguments" in payload:
            metadata["launch_arguments"] = payload.get("launch_arguments")
        if "required_plugins" in payload:
            metadata["required_plugins"] = payload.get("required_plugins")
        if "package" in payload:
            metadata["package"] = payload.get("package")
        if "package_version" in payload:
            metadata["package_version"] = payload.get("package_version")
        return metadata

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
