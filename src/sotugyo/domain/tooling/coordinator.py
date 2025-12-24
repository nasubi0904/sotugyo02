"""ノードエディタ用の調整ロジック。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from ..projects.service import ProjectService
from ..users.settings import UserSettingsManager
from .models import RegisteredTool, RezPackageSpec, ToolEnvironmentDefinition
from .services import ToolEnvironmentService

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ToolEnvironmentSnapshot:
    """ツール登録と環境定義のスナップショット。"""

    tools: Dict[str, RegisteredTool]
    environments: Dict[str, ToolEnvironmentDefinition]


@dataclass(frozen=True)
class NodeCatalogRecord:
    """コンテンツブラウザ向けノードカタログ要素。"""

    node_type: str
    title: str
    subtitle: str
    genre: str
    keywords: Tuple[str, ...] = ()
    icon_path: str | None = None


class NodeEditorCoordinator:
    """ノードエディタ画面とドメイン層の橋渡しを行う。"""

    def __init__(
        self,
        *,
        project_service: ProjectService | None = None,
        user_manager: UserSettingsManager | None = None,
        tool_service: ToolEnvironmentService | None = None,
    ) -> None:
        self.project_service = project_service or ProjectService()
        self.user_manager = user_manager or UserSettingsManager()
        self.tool_service = tool_service or ToolEnvironmentService()

    def load_tool_snapshot(self) -> ToolEnvironmentSnapshot:
        try:
            tools = self.tool_service.list_tools()
        except OSError as exc:
            LOGGER.error("ツール情報の取得に失敗しました: %s", exc, exc_info=True)
            tools = []
        try:
            environments = self.tool_service.list_environments()
        except OSError as exc:
            LOGGER.error("環境情報の取得に失敗しました: %s", exc, exc_info=True)
            environments = []

        tool_map = {tool.tool_id: tool for tool in tools}
        env_map: Dict[str, ToolEnvironmentDefinition] = {
            environment.package_key_label(): environment
            for environment in environments
        }
        return ToolEnvironmentSnapshot(tool_map, env_map)

    def build_tool_catalog(self, snapshot: ToolEnvironmentSnapshot) -> List[NodeCatalogRecord]:
        records: List[NodeCatalogRecord] = []
        for environment in sorted(
            snapshot.environments.values(), key=lambda item: item.display_label()
        ):
            packages_text = " ".join(environment.rez_packages)
            variants_text = ", ".join(environment.rez_variants)
            subtitle = packages_text or "Rez パッケージ未指定"
            if variants_text:
                subtitle = f"{subtitle} / {variants_text}"
            node_type = f"tool-environment:{environment.package_key_label()}"
            keywords: Tuple[str, ...] = (packages_text, variants_text)
            icon_path = None
            records.append(
                NodeCatalogRecord(
                    node_type=node_type,
                    title=environment.display_label(),
                    subtitle=subtitle,
                    genre="ツール環境",
                    keywords=keywords,
                    icon_path=icon_path,
                )
            )
        return records

    def extend_catalog(
        self,
        base_entries: Iterable[NodeCatalogRecord],
        snapshot: ToolEnvironmentSnapshot,
    ) -> List[NodeCatalogRecord]:
        entries = list(base_entries)
        entries.extend(self.build_tool_catalog(snapshot))
        return entries

    def list_rez_packages(self) -> List[RezPackageSpec]:
        return self.tool_service.list_rez_packages()

    def list_project_rez_packages(self, project_root: Path) -> List[RezPackageSpec]:
        return self.tool_service.list_project_rez_packages(project_root)

    def sync_rez_packages_to_project(
        self, project_root: Path, packages: Iterable[str]
    ):
        return self.tool_service.sync_rez_packages_to_project(project_root, packages)

    def validate_project_rez_packages(self, project_root: Path):
        return self.tool_service.validate_project_rez_packages(project_root)
