"""ツール登録と環境定義を管理するサービス。"""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from . import templates
from .models import (
    RegisteredTool,
    TemplateInstallationCandidate,
    ToolEnvironmentDefinition,
)
from .repository import ToolConfigRepository


class ToolEnvironmentService:
    """マシン上のツール登録と環境ノード定義を扱う。"""

    def __init__(self, repository: ToolConfigRepository | None = None) -> None:
        self._repository = repository or ToolConfigRepository()

    # ------------------------------------------------------------------
    # ツール登録
    # ------------------------------------------------------------------
    def list_tools(self) -> List[RegisteredTool]:
        tools, _ = self._repository.load_all()
        return tools

    def get_tool(self, tool_id: str) -> Optional[RegisteredTool]:
        tools = self.list_tools()
        for tool in tools:
            if tool.tool_id == tool_id:
                return tool
        return None

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

        tools, environments = self._repository.load_all()
        for tool in tools:
            if tool.executable_path.resolve() == normalized_path.resolve():
                raise ValueError("同じ実行ファイルが既に登録されています。")

        now = datetime.utcnow()
        tool = RegisteredTool(
            tool_id=str(uuid.uuid4()),
            display_name=display_name.strip() or normalized_path.stem,
            executable_path=normalized_path,
            template_id=template_id,
            version=version.strip() if version else None,
            created_at=now,
            updated_at=now,
        )
        tools.append(tool)
        self._repository.save_all(tools, environments)
        return tool

    def remove_tool(self, tool_id: str) -> bool:
        tools, environments = self._repository.load_all()
        new_tools = [tool for tool in tools if tool.tool_id != tool_id]
        if len(new_tools) == len(tools):
            return False
        new_environments = [env for env in environments if env.tool_id != tool_id]
        self._repository.save_all(new_tools, new_environments)
        return True

    # ------------------------------------------------------------------
    # 環境定義
    # ------------------------------------------------------------------
    def list_environments(self) -> List[ToolEnvironmentDefinition]:
        _, environments = self._repository.load_all()
        return environments

    def save_environment(
        self,
        *,
        name: str,
        tool_id: str,
        version_label: str,
        environment_id: Optional[str] = None,
    ) -> ToolEnvironmentDefinition:
        tools, environments = self._repository.load_all()
        tool_map: Dict[str, RegisteredTool] = {tool.tool_id: tool for tool in tools}
        if tool_id not in tool_map:
            raise ValueError("選択されたツールが登録されていません。")

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
            target.tool_id = tool_id
            target.version_label = version_label.strip()
            target.updated_at = now
            environment = target
        else:
            environment = ToolEnvironmentDefinition(
                environment_id=str(uuid.uuid4()),
                name=name.strip() or "環境",
                tool_id=tool_id,
                version_label=version_label.strip(),
                created_at=now,
                updated_at=now,
            )
            environments.append(environment)

        self._repository.save_all(tools, environments)
        return environment

    def remove_environment(self, environment_id: str) -> bool:
        tools, environments = self._repository.load_all()
        new_environments = [
            env for env in environments if env.environment_id != environment_id
        ]
        if len(new_environments) == len(environments):
            return False
        self._repository.save_all(tools, new_environments)
        return True

    # ------------------------------------------------------------------
    # テンプレート連携
    # ------------------------------------------------------------------
    def list_templates(self) -> List[Dict[str, str]]:
        return templates.list_templates()

    def discover_template_installations(
        self, template_id: str
    ) -> List[TemplateInstallationCandidate]:
        return templates.discover_installations(template_id)

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
