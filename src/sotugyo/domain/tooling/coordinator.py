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
    tool_name: str | None = None
    version_label: str | None = None


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
        filtered_envs: Dict[str, ToolEnvironmentDefinition] = {}
        for environment in environments:
            if environment.tool_id in tool_map:
                filtered_envs[environment.environment_id] = environment
            else:
                LOGGER.warning(
                    "ツール %s が存在しないため環境 %s を読み込みから除外しました。",
                    environment.tool_id,
                    environment.environment_id,
                )
        return ToolEnvironmentSnapshot(tool_map, filtered_envs)

    def build_tool_catalog(self, snapshot: ToolEnvironmentSnapshot) -> List[NodeCatalogRecord]:
        records: List[NodeCatalogRecord] = []
        environments = sorted(
            snapshot.environments.values(),
            key=lambda item: (
                snapshot.tools.get(item.tool_id).display_name
                if item.tool_id in snapshot.tools
                else item.name,
                item.version_label,
                item.environment_id,
            ),
        )
        for environment in environments:
            tool = snapshot.tools.get(environment.tool_id)
            tool_name = tool.display_name if tool is not None else environment.name
            version_label = environment.version_label or "未指定"
            subtitle = environment.name if environment.name != version_label else ""
            node_type = f"tool-environment:{environment.environment_id}"
            keywords: Tuple[str, ...] = (
                environment.environment_id,
                tool_name,
                version_label,
            )
            icon_path = None
            if tool is not None and tool.executable_path.suffix.lower() == ".exe":
                if tool.executable_path.exists():
                    icon_path = str(tool.executable_path)
            records.append(
                NodeCatalogRecord(
                    node_type=node_type,
                    title=version_label,
                    subtitle=subtitle,
                    genre="ツール環境",
                    keywords=keywords,
                    icon_path=icon_path,
                    tool_name=tool_name,
                    version_label=version_label,
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
