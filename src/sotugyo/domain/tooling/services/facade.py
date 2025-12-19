"""ツール登録と環境定義を統合するファサード。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
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
from .rez import RezLaunchResult


@dataclass(slots=True)
class ToolEnvironmentService:
    """ツール登録と環境定義をまとめて提供する。"""

    registry_service: ToolRegistryService
    environment_service: ToolEnvironmentRegistryService
    template_gateway: TemplateGateway
    rez_repository: RezPackageRepository

    def __init__(
        self,
        repository: ToolConfigRepository | None = None,
        *,
        registry_service: ToolRegistryService | None = None,
        environment_service: ToolEnvironmentRegistryService | None = None,
        template_gateway: TemplateGateway | None = None,
        rez_repository: RezPackageRepository | None = None,
    ) -> None:
        repo = repository or ToolConfigRepository()
        self.registry_service = registry_service or ToolRegistryService(repo)
        self.environment_service = (
            environment_service or ToolEnvironmentRegistryService(repo)
        )
        self.template_gateway = template_gateway or TemplateGateway()
        self.rez_repository = rez_repository or RezPackageRepository()

    # ------------------------------------------------------------------
    # ツール登録
    # ------------------------------------------------------------------
    def list_tools(self) -> List[RegisteredTool]:
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
        return self.registry_service.register(
            display_name=display_name,
            executable_path=normalized_path,
            template_id=template_id,
            version=version,
        )

    def remove_tool(self, tool_id: str) -> bool:
        return self.registry_service.remove(tool_id)

    # ------------------------------------------------------------------
    # 環境定義
    # ------------------------------------------------------------------
    def list_environments(self) -> List[ToolEnvironmentDefinition]:
        return self.environment_service.list_environments()

    def get_environment(self, environment_id: str) -> Optional[ToolEnvironmentDefinition]:
        return self.environment_service.get_environment(environment_id)

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

    # ------------------------------------------------------------------
    # Rez 起動
    # ------------------------------------------------------------------
    def launch_environment(self, environment_id: str) -> RezLaunchResult:
        if not environment_id:
            return RezLaunchResult(
                success=False,
                command=(),
                return_code=2,
                stderr="environment_id が指定されていません。",
            )

        environment = self.environment_service.get_environment(environment_id)
        if environment is None:
            return RezLaunchResult(
                success=False,
                command=(),
                return_code=2,
                stderr="指定された環境が登録されていません。",
            )

        tool = self.registry_service.get_tool(environment.tool_id)
        if tool is None:
            return RezLaunchResult(
                success=False,
                command=(),
                return_code=2,
                stderr="環境が参照するツールが登録されていません。",
            )

        packages = list(environment.rez_packages)
        if not packages and environment.template_id:
            package_name = self.rez_repository.get_package_name(environment.template_id)
            if package_name:
                packages = [package_name]

        if not packages:
            return RezLaunchResult(
                success=False,
                command=(),
                return_code=2,
                stderr="起動に必要な Rez パッケージが設定されていません。",
            )

        missing = [
            package for package in packages if self.rez_repository.find_package(package) is None
        ]
        if missing:
            missing_list = ", ".join(missing)
            return RezLaunchResult(
                success=False,
                command=(),
                return_code=2,
                stderr=f"Rez パッケージが見つかりません: {missing_list}",
            )

        resolver = self.environment_service.rez_resolver
        if resolver is None:  # pragma: no cover - 予防的措置
            return RezLaunchResult(
                success=False,
                command=(),
                return_code=2,
                stderr="Rez 実行環境が初期化されていません。",
            )

        return resolver.launch(
            packages=packages,
            variants=list(environment.rez_variants),
            environment=environment.rez_environment,
            command=[str(tool.executable_path)],
            packages_path=[str(self.rez_repository.root_dir)],
        )

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
