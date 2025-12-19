"""環境定義管理サービス。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Iterable, List, Optional

from ..models import ToolEnvironmentDefinition
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

    def get_environment(self, environment_id: str) -> Optional[ToolEnvironmentDefinition]:
        if not environment_id:
            return None
        _, environments = self.repository.load_all()
        for environment in environments:
            if environment.environment_id == environment_id:
                return environment
        return None

    def save(
        self,
        *,
        name: str,
        tool_id: str,
        version_label: str,
        environments: List[ToolEnvironmentDefinition],
        environment_id: Optional[str] = None,
        template_id: Optional[str] = None,
        rez_packages: Optional[Iterable[str]] = None,
        rez_variants: Optional[Iterable[str]] = None,
        rez_environment: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, object]] = None,
    ) -> ToolEnvironmentDefinition:
        normalized_packages = self._normalize_sequence(rez_packages)
        normalized_variants = self._normalize_sequence(rez_variants)
        normalized_env = self._normalize_environment(rez_environment)
        resolved_tool_id = tool_id.strip()
        if not resolved_tool_id and normalized_packages:
            resolved_tool_id = normalized_packages[0]
        if not resolved_tool_id:
            resolved_tool_id = "rez-tool"
        normalized_packages = self._apply_versioned_packages(
            normalized_packages,
            resolved_tool_id,
            version_label,
        )

        now = datetime.utcnow()
        if environment_id:
            target = None
            for env in environments:
                if env.environment_id == environment_id:
                    target = env
                    break
            if target is None:
                raise ValueError("指定された環境が存在しません。")
            target.name = name.strip() or target.name
            target.tool_id = resolved_tool_id
            target.version_label = version_label.strip()
            target.template_id = template_id or None
            if normalized_packages is not None:
                target.rez_packages = normalized_packages
            if normalized_variants is not None:
                target.rez_variants = normalized_variants
            if normalized_env is not None:
                target.rez_environment = normalized_env
            if metadata is not None:
                target.metadata = dict(metadata)
            target.updated_at = now
            environment = target
        else:
            environment = ToolEnvironmentDefinition(
                environment_id=ToolEnvironmentIdGenerator.next_id(),
                name=name.strip() or "環境",
                tool_id=resolved_tool_id,
                version_label=version_label.strip(),
                template_id=template_id or None,
                rez_packages=normalized_packages or (),
                rez_variants=normalized_variants or (),
                rez_environment=normalized_env or {},
                metadata=dict(metadata) if metadata else {},
                created_at=now,
                updated_at=now,
            )
            environments.append(environment)

        validation_result = self.validate_rez_environment(
            packages=environment.rez_packages,
            variants=environment.rez_variants,
            environment=environment.rez_environment,
        )
        environment.metadata["rez_validation"] = validation_result.to_dict()
        environment.updated_at = now
        self.repository.save_all([], environments)
        return environment

    def remove(self, environment_id: str) -> bool:
        tools_list, environments = self.repository.load_all()
        new_environments = [
            env for env in environments if env.environment_id != environment_id
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
    def _normalize_environment(values: Optional[Dict[str, str]]) -> Optional[Dict[str, str]]:
        if values is None:
            return None
        normalized: Dict[str, str] = {}
        for key, value in values.items():
            if isinstance(key, str) and isinstance(value, str):
                normalized[key.strip()] = value.strip()
        return normalized

    @staticmethod
    def _apply_versioned_packages(
        packages: Optional[tuple[str, ...]],
        tool_id: str,
        version_label: str,
    ) -> Optional[tuple[str, ...]]:
        if not packages:
            return packages
        base = tool_id.strip()
        version = version_label.strip()
        if not base or not version:
            return packages
        updated: list[str] = []
        for entry in packages:
            normalized = entry.strip()
            if normalized == base:
                updated.append(f"{base}-{version}")
            else:
                updated.append(normalized)
        return tuple(updated)


class ToolEnvironmentIdGenerator:
    """環境 ID 生成をラップしてテスト容易性を高める。"""

    @staticmethod
    def next_id() -> str:
        import uuid

        return str(uuid.uuid4())
