"""環境定義管理サービス。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from .models import RegisteredTool, ToolEnvironmentDefinition
from .repository import ToolConfigRepository


@dataclass(slots=True)
class ToolEnvironmentRegistryService:
    """ツール環境定義の永続化と整合性維持を担当する。"""

    repository: ToolConfigRepository

    def list_environments(self) -> List[ToolEnvironmentDefinition]:
        _, environments = self.repository.load_all()
        return environments

    def save(
        self,
        *,
        name: str,
        tool_id: str,
        version_label: str,
        tools: List[RegisteredTool],
        environments: List[ToolEnvironmentDefinition],
        environment_id: Optional[str] = None,
    ) -> ToolEnvironmentDefinition:
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
                environment_id=ToolEnvironmentIdGenerator.next_id(),
                name=name.strip() or "環境",
                tool_id=tool_id,
                version_label=version_label.strip(),
                created_at=now,
                updated_at=now,
            )
            environments.append(environment)

        self.repository.save_all(tools, environments)
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


class ToolEnvironmentIdGenerator:
    """環境 ID 生成をラップしてテスト容易性を高める。"""

    @staticmethod
    def next_id() -> str:
        import uuid

        return str(uuid.uuid4())
