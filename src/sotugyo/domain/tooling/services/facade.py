"""ツール登録と環境定義を統合するファサード。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from ..models import (
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
from .rez import RezLaunchResult


@dataclass(slots=True)
class ToolEnvironmentService:
    """ツール登録と環境定義をまとめて提供する。"""

    environment_service: ToolEnvironmentRegistryService
    template_gateway: TemplateGateway
    rez_repository: RezPackageRepository

    def __init__(
        self,
        repository: ToolConfigRepository | None = None,
        *,
        environment_service: ToolEnvironmentRegistryService | None = None,
        template_gateway: TemplateGateway | None = None,
        rez_repository: RezPackageRepository | None = None,
    ) -> None:
        repo = repository or ToolConfigRepository()
        self.environment_service = (
            environment_service or ToolEnvironmentRegistryService(repo)
        )
        self.template_gateway = template_gateway or TemplateGateway()
        self.rez_repository = rez_repository or RezPackageRepository()

    # ------------------------------------------------------------------
    # ツール登録
    # ------------------------------------------------------------------
    def register_tool(
        self,
        *,
        display_name: str,
        executable_path: Path | str,
        template_id: str | None = None,
        version: str | None = None,
    ) -> ToolEnvironmentDefinition:
        normalized_path = self._normalize_executable_path(executable_path)
        if not normalized_path.exists():
            raise ValueError(f"実行ファイルが見つかりません: {normalized_path}")

        environments = self.list_environments()
        for environment in environments:
            metadata = environment.metadata
            if not isinstance(metadata, dict):
                continue
            recorded_path = metadata.get("executable_path")
            if not isinstance(recorded_path, str):
                continue
            if Path(recorded_path).resolve() == normalized_path.resolve():
                raise ValueError("同じ実行ファイルが既に登録されています。")

        candidate = TemplateInstallationCandidate(
            template_id=template_id or normalized_path.stem,
            display_name=display_name.strip() or normalized_path.stem,
            executable_path=normalized_path,
            version=version.strip() if version else None,
        )
        package_name = self.rez_repository.register_candidate(candidate)
        package_spec = package_name
        if candidate.version:
            package_spec = f"{package_name}-{candidate.version}"
        environment = self.environment_service.save(
            name=candidate.display_name,
            tool_id=package_name,
            version_label=candidate.version or "local",
            environments=environments,
            template_id=template_id,
            rez_packages=[package_spec],
            metadata={"executable_path": str(normalized_path)},
        )
        return environment

    def remove_tool(self, tool_id: str) -> bool:
        if not tool_id:
            return False
        environments = self.environment_service.list_environments()
        target = next(
            (env for env in environments if env.environment_id == tool_id), None
        )
        if target is None:
            return False
        return self.environment_service.remove(target.environment_id)

    # ------------------------------------------------------------------
    # 環境定義
    # ------------------------------------------------------------------
    def list_environments(self) -> List[ToolEnvironmentDefinition]:
        repository = self.environment_service.repository
        tools, environments = repository.load_all()
        if tools:
            updated = list(environments)
            for tool in tools:
                if any(
                    isinstance(env.metadata, dict)
                    and env.metadata.get("executable_path") == str(tool.executable_path)
                    for env in updated
                ):
                    continue
                candidate = TemplateInstallationCandidate(
                    template_id=tool.template_id or tool.executable_path.stem,
                    display_name=tool.display_name,
                    executable_path=tool.executable_path,
                    version=tool.version,
                )
                package_name = self.rez_repository.register_candidate(candidate)
                updated.append(
                    ToolEnvironmentDefinition(
                        environment_id=tool.tool_id,
                        name=tool.display_name,
                        tool_id=package_name,
                        version_label=tool.version or "local",
                        template_id=tool.template_id,
                        rez_packages=(package_name,),
                        metadata={"executable_path": str(tool.executable_path)},
                    )
                )
            repository.save_all([], updated)
            return updated
        return environments

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
        return self.environment_service.save(
            name=name,
            tool_id=tool_id,
            version_label=version_label,
            environments=self.list_environments(),
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

        environment = next(
            (env for env in self.list_environments() if env.environment_id == environment_id),
            None,
        )
        if environment is None:
            return RezLaunchResult(
                success=False,
                command=(),
                return_code=2,
                stderr="指定された環境が登録されていません。",
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

        executable_path = None
        if isinstance(environment.metadata, dict):
            executable_path = environment.metadata.get("executable_path")
        if not isinstance(executable_path, str) or not executable_path:
            return RezLaunchResult(
                success=False,
                command=(),
                return_code=2,
                stderr="起動対象の実行ファイルが設定されていません。",
            )

        return resolver.launch(
            packages=packages,
            variants=list(environment.rez_variants),
            environment=environment.rez_environment,
            command=[executable_path],
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
