"""環境定義管理サービス。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Optional

from ..models import RegisteredTool, ToolEnvironmentDefinition
from ..repositories.config import ToolConfigRepository
from .rez import RezEnvironmentResolver, RezResolveResult


@dataclass(slots=True)
class ToolEnvironmentRegistryService:
    """ツール環境定義の永続化と整合性維持を担当する。"""

    repository: ToolConfigRepository
    rez_resolver: RezEnvironmentResolver = field(default_factory=RezEnvironmentResolver)

    def list_environments(self) -> List[ToolEnvironmentDefinition]:
        _, environments = self.repository.load_all()
        return environments

    def save(
        self,
        *,
        tools: List[RegisteredTool],
        environments: List[ToolEnvironmentDefinition],
        rez_packages: Optional[Iterable[str]] = None,
        rez_variants: Optional[Iterable[str]] = None,
    ) -> ToolEnvironmentDefinition:
        normalized_packages = self._normalize_sequence(rez_packages) or ()
        normalized_variants = self._normalize_sequence(rez_variants) or ()

        target = self._find_matching_environment(
            environments, normalized_packages, normalized_variants
        )
        if target is None:
            environment = ToolEnvironmentDefinition(
                rez_packages=normalized_packages,
                rez_variants=normalized_variants,
            )
            environments.append(environment)
        else:
            target.rez_packages = normalized_packages
            target.rez_variants = normalized_variants
            environment = target
        self.repository.save_all(tools, environments)
        return environment

    def remove(self, package_key_label: str) -> bool:
        tools_list, environments = self.repository.load_all()
        new_environments = [
            env
            for env in environments
            if env.package_key_label() != package_key_label
        ]
        if len(new_environments) == len(environments):
            return False
        self.repository.save_all(tools_list, new_environments)
        return True

    def validate_rez_environment(
        self,
        *,
        packages: Iterable[str],
        variants: Iterable[str] | None = None,
        environment: Optional[Dict[str, str]] = None,
    ) -> RezResolveResult:
        resolver = self.rez_resolver
        if resolver is None:  # pragma: no cover - 予防的措置
            return RezResolveResult(True, command=(), stdout="Rez 検証を実施しませんでした。")
        return resolver.resolve(
            packages=list(packages),
            variants=list(variants or ()),
            environment=environment or {},
        )

    @staticmethod
    def _normalize_sequence(values: Optional[Iterable[str]]) -> Optional[tuple[str, ...]]:
        if values is None:
            return None
        normalized = tuple(
            entry.strip()
            for entry in values
            if isinstance(entry, str) and entry.strip()
        )
        return normalized

    @staticmethod
    def _find_matching_environment(
        environments: Iterable[ToolEnvironmentDefinition],
        rez_packages: Iterable[str],
        rez_variants: Iterable[str],
    ) -> ToolEnvironmentDefinition | None:
        normalized_key = set(rez_packages)
        normalized_variants = set(rez_variants)
        for environment in environments:
            if (
                set(environment.rez_packages) == normalized_key
                and set(environment.rez_variants) == normalized_variants
            ):
                return environment
        return None
