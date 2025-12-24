"""環境定義管理サービス。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

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
        name: str,
        tools: List[RegisteredTool],
        environments: List[ToolEnvironmentDefinition],
        rez_packages: Optional[Iterable[str]] = None,
        rez_variants: Optional[Iterable[str]] = None,
        rez_environment: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, object]] = None,
    ) -> ToolEnvironmentDefinition:
        normalized_packages = self._normalize_sequence(rez_packages) or ()
        normalized_variants = self._normalize_sequence(rez_variants)
        normalized_env = self._normalize_environment(rez_environment)

        target = self._find_matching_environment(
            environments, normalized_packages
        )
        if target is None:
            environment = ToolEnvironmentDefinition(
                name=name.strip() or "環境",
                rez_packages=normalized_packages,
                rez_variants=normalized_variants or (),
                rez_environment=normalized_env or {},
                metadata=dict(metadata) if metadata else {},
            )
            environments.append(environment)
        else:
            target.name = name.strip() or target.name
            target.rez_packages = normalized_packages
            if normalized_variants is not None:
                target.rez_variants = normalized_variants
            if normalized_env is not None:
                target.rez_environment = normalized_env
            if metadata is not None:
                target.metadata = dict(metadata)
            environment = target

        validation_result = self.validate_rez_environment(
            packages=environment.rez_packages,
            variants=environment.rez_variants,
            environment=environment.rez_environment,
        )
        environment.metadata["rez_validation"] = validation_result.to_dict()
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
    ) -> ToolEnvironmentDefinition | None:
        if rez_packages is None:
            return None
        normalized_key = set(rez_packages)
        for environment in environments:
            if set(environment.rez_packages) == normalized_key:
                return environment
        return None

    @staticmethod
    def _normalize_environment(values: Optional[Dict[str, str]]) -> Optional[Dict[str, str]]:
        if values is None:
            return None
        normalized: Dict[str, str] = {}
        for key, value in values.items():
            if isinstance(key, str) and isinstance(value, str):
                normalized[key.strip()] = value.strip()
        return normalized
