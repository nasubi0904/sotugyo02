from __future__ import annotations

import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from src.sotugyo.domain.tooling.models import RegisteredTool, ToolEnvironmentDefinition
from src.sotugyo.domain.tooling.repositories.config import ToolConfigRepository
from src.sotugyo.domain.tooling.services.environment import ToolEnvironmentRegistryService
from src.sotugyo.domain.tooling.services.rez import RezResolveResult


class DummyResolver:
    def __init__(self, *, success: bool, message: str = "") -> None:
        self._result = RezResolveResult(
            success=success,
            command=("rez", "env"),
            stdout=message if success else "",
            stderr="" if success else message or "resolve failed",
        )
        self.calls: list[tuple[tuple[str, ...], tuple[str, ...], dict[str, str]]] = []

    def resolve(
        self,
        packages,
        *,
        variants=None,
        environment=None,
        timeout=None,
    ) -> RezResolveResult:
        normalized_packages = tuple(packages)
        normalized_variants = tuple(variants or ())
        normalized_env = dict(environment or {})
        self.calls.append((normalized_packages, normalized_variants, normalized_env))
        return self._result


def make_tool(tool_id: str) -> RegisteredTool:
    return RegisteredTool(
        tool_id=tool_id,
        display_name="TestTool",
        executable_path=Path("C:/Tools/test.exe"),
        template_id="autodesk.maya",
        version="2024",
    )


def test_tool_environment_definition_serialization_roundtrip() -> None:
    definition = ToolEnvironmentDefinition(
        environment_id="env-1",
        name="レンダー環境",
        tool_id="tool-1",
        version_label="2024.1",
        template_id="autodesk.maya",
        rez_packages=("maya", "arnold"),
        rez_variants=("platform-windows",),
        rez_environment={"MAYA_APP_DIR": "C:/Project/maya"},
        metadata={"rez_validation": {"success": True}},
    )

    restored = ToolEnvironmentDefinition.from_dict(definition.to_dict())

    assert restored.environment_id == definition.environment_id
    assert restored.template_id == "autodesk.maya"
    assert restored.rez_packages == ("maya", "arnold")
    assert restored.rez_variants == ("platform-windows",)
    assert restored.rez_environment == {"MAYA_APP_DIR": "C:/Project/maya"}
    assert restored.metadata.get("rez_validation", {}).get("success") is True


def test_environment_registry_saves_rez_metadata() -> None:
    with TemporaryDirectory() as tmp_dir:
        repository = ToolConfigRepository(storage_dir=Path(tmp_dir))
        resolver = DummyResolver(success=False, message="package missing")
        service = ToolEnvironmentRegistryService(repository=repository, rez_resolver=resolver)

        tool = make_tool("tool-1")
        tools = [tool]
        environments: list[ToolEnvironmentDefinition] = []

        environment = service.save(
            name="テスト環境",
            tool_id=tool.tool_id,
            version_label="v1",
            tools=tools,
            environments=environments,
            template_id="autodesk.maya",
            rez_packages=["maya"],
            rez_variants=["platform-windows"],
            rez_environment={"MAYA_APP_DIR": "C:/maya"},
        )

        assert resolver.calls
        packages, variants, env_map = resolver.calls[0]
        assert packages == ("maya",)
        assert variants == ("platform-windows",)
        assert env_map == {"MAYA_APP_DIR": "C:/maya"}

        assert environment.rez_packages == ("maya",)
        assert environment.template_id == "autodesk.maya"
        assert environment.metadata["rez_validation"]["success"] is False

        stored_tools, stored_envs = repository.load_all()
        assert stored_tools[0].tool_id == tool.tool_id
        assert stored_envs[0].rez_packages == ("maya",)


def test_environment_registry_can_clear_template_and_packages() -> None:
    with TemporaryDirectory() as tmp_dir:
        repository = ToolConfigRepository(storage_dir=Path(tmp_dir))
        resolver = DummyResolver(success=True, message="ok")
        service = ToolEnvironmentRegistryService(repository=repository, rez_resolver=resolver)

        tool = make_tool("tool-1")
        initial = service.save(
            name="環境A",
            tool_id=tool.tool_id,
            version_label="v1",
            tools=[tool],
            environments=[],
            template_id="autodesk.maya",
            rez_packages=["maya"],
        )

        tools, environments = repository.load_all()
        updated = service.save(
            name="環境A",
            tool_id=tool.tool_id,
            version_label="v2",
            tools=tools,
            environments=environments,
            environment_id=initial.environment_id,
            template_id=None,
            rez_packages=[],
            rez_variants=[],
            rez_environment={},
        )

        assert updated.template_id is None
        assert updated.rez_packages == ()
        assert updated.rez_variants == ()
        assert updated.rez_environment == {}

