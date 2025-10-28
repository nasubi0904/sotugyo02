"""ツール登録管理サービス。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List

from .models import RegisteredTool
from .repository import ToolConfigRepository


@dataclass(slots=True)
class ToolRegistryService:
    """ツール登録の永続化と検証を担当する。"""

    repository: ToolConfigRepository

    def list_tools(self) -> List[RegisteredTool]:
        tools, _ = self.repository.load_all()
        return tools

    def get_tool(self, tool_id: str) -> RegisteredTool | None:
        for tool in self.list_tools():
            if tool.tool_id == tool_id:
                return tool
        return None

    def register(
        self,
        *,
        display_name: str,
        executable_path: Path,
        template_id: str | None = None,
        version: str | None = None,
    ) -> RegisteredTool:
        tools, environments = self.repository.load_all()
        for tool in tools:
            if tool.executable_path.resolve() == executable_path.resolve():
                raise ValueError("同じ実行ファイルが既に登録されています。")

        now = datetime.utcnow()
        tool = RegisteredTool(
            tool_id=RegisteredToolIdGenerator.next_id(),
            display_name=display_name.strip() or executable_path.stem,
            executable_path=executable_path,
            template_id=template_id,
            version=version.strip() if version else None,
            created_at=now,
            updated_at=now,
        )
        tools.append(tool)
        self.repository.save_all(tools, environments)
        return tool

    def remove(self, tool_id: str) -> bool:
        tools, environments = self.repository.load_all()
        new_tools = [tool for tool in tools if tool.tool_id != tool_id]
        if len(new_tools) == len(tools):
            return False
        new_environments = [env for env in environments if env.tool_id != tool_id]
        self.repository.save_all(new_tools, new_environments)
        return True

    def save_snapshot(
        self,
        tools: Iterable[RegisteredTool],
        environments: Iterable,
    ) -> None:
        self.repository.save_all(tools, environments)


class RegisteredToolIdGenerator:
    """UUID 生成をラップしてテスト容易性を高める。"""

    @staticmethod
    def next_id() -> str:
        import uuid

        return str(uuid.uuid4())
