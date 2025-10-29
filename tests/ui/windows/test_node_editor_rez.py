"""NodeEditorWindow の Rez 環境検証ロジックを検証するテスト。"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict
from unittest.mock import MagicMock

import pytest

from sotugyo.domain.tooling import RegisteredTool, ToolEnvironmentDefinition
from sotugyo.domain.tooling.services.rez import RezResolveResult
from sotugyo.ui.windows.views import node_editor


class _DummyToolEnvironmentNode:
    """テスト専用の簡易ツール環境ノード。"""

    def __init__(self, payload: Dict[str, Any]) -> None:
        self._payload = dict(payload)
        self.configured: list[Dict[str, Any]] = []

    def get_environment_payload(self) -> Dict[str, Any]:
        return dict(self._payload)

    def configure_environment(self, **kwargs: Any) -> None:
        self.configured.append(kwargs)


def _create_test_window(nodes: list[object]) -> node_editor.NodeEditorWindow:
    window = node_editor.NodeEditorWindow.__new__(node_editor.NodeEditorWindow)
    window._tool_environments = {}
    window._registered_tools = {}
    window._coordinator = SimpleNamespace(tool_service=MagicMock())
    window._collect_all_nodes = lambda: list(nodes)
    window._safe_node_name = lambda _node: "TestNode"
    window._show_warning_dialog = MagicMock()
    return window


@pytest.fixture(autouse=True)
def _patch_tool_environment_node(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(node_editor, "ToolEnvironmentNode", _DummyToolEnvironmentNode)


def test_check_rez_skips_validation_when_local_definition_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    definition = ToolEnvironmentDefinition(
        environment_id="env-1",
        name="Local Env",
        tool_id="tool-1",
        version_label="1.0",
        rez_packages=("pkgA",),
    )
    tool = RegisteredTool(
        tool_id="tool-1",
        display_name="DemoTool",
        executable_path=Path("/tmp/tool.exe"),
    )
    payload = {"environment_id": "env-1", "rez_packages": ["pkgA"]}
    node = node_editor.ToolEnvironmentNode(payload)

    window = _create_test_window([node])
    window._tool_environments = {definition.environment_id: definition}
    window._registered_tools = {tool.tool_id: tool}

    window._check_rez_environments_in_project()

    assert not window._coordinator.tool_service.validate_rez_environment.called
    assert node.configured, "ローカル定義に基づきノードが更新されていません。"
    latest_config = node.configured[-1]
    assert latest_config["tool_name"] == tool.display_name
    assert latest_config["environment_payload"]["rez_packages"] == list(
        definition.rez_packages
    )


def test_check_rez_invokes_validation_when_definition_missing() -> None:
    payload = {
        "environment_id": "unknown",
        "rez_packages": ["pkgA"],
        "rez_environment": {"VAR": "VALUE"},
    }
    node = node_editor.ToolEnvironmentNode(payload)

    window = _create_test_window([node])
    resolver_result = RezResolveResult(
        success=False,
        command=("rez",),
        return_code=127,
        stderr="rez コマンドが見つかりません。",
    )
    window._coordinator.tool_service.validate_rez_environment.return_value = (
        resolver_result
    )

    window._check_rez_environments_in_project()

    service_mock = window._coordinator.tool_service.validate_rez_environment
    service_mock.assert_called_once()
    call_kwargs = service_mock.call_args.kwargs
    assert call_kwargs["packages"] == ["pkgA"]
    assert call_kwargs["environment"] == {"VAR": "VALUE"}

    window._show_warning_dialog.assert_called_once()
    warning_message = window._show_warning_dialog.call_args.args[0]
    assert "Rez による再現が必要" in warning_message
