from __future__ import annotations

import os
import shutil
import subprocess
import sys
import types
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from src.sotugyo.domain.tooling.models import RegisteredTool, ToolEnvironmentDefinition
from src.sotugyo.domain.tooling.repositories.config import ToolConfigRepository
from src.sotugyo.domain.tooling.services.environment import ToolEnvironmentRegistryService
from src.sotugyo.domain.tooling.services.rez import RezEnvironmentResolver, RezResolveResult


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


def test_tool_config_repository_uses_rez_package_dir(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", "")
    monkeypatch.setenv("APPDATA", "")
    from src.sotugyo.domain.tooling.repositories import config as config_module

    monkeypatch.setattr(config_module, "get_rez_package_dir", lambda: tmp_path)

    repository = config_module.ToolConfigRepository()

    assert repository._storage_dir == tmp_path
    assert repository._storage_path.parent == tmp_path
    assert repository._storage_path.name == config_module.ToolConfigRepository.FILE_NAME


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


def test_rez_resolver_adds_path_from_environment(tmp_path, monkeypatch) -> None:
    bin_dir = tmp_path / "rez_bin"
    bin_dir.mkdir()
    rez_executable = bin_dir / "rez"
    rez_executable.write_text("#!/bin/sh\nexit 0\n")
    rez_executable.chmod(0o755)

    monkeypatch.setenv("PATH", "")
    monkeypatch.setenv("SOTUGYO_REZ_PATH", str(bin_dir))

    called_env: dict | None = None

    def _fake_run(*_, **kwargs):
        nonlocal called_env
        called_env = kwargs.get("env")
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    resolver = RezEnvironmentResolver()

    monkeypatch.setattr(subprocess, "run", _fake_run)

    result = resolver.resolve(["maya"], environment={})

    assert result.success is True
    assert called_env is not None
    path_entries = called_env["PATH"].split(os.pathsep)
    assert path_entries[0] == str(bin_dir)
    assert shutil.which("rez") is not None


def test_rez_resolver_uses_updated_hint_on_resolve(tmp_path, monkeypatch) -> None:
    bin_dir = tmp_path / "rez_bin"
    bin_dir.mkdir()
    rez_executable = bin_dir / "rez"
    rez_executable.write_text("#!/bin/sh\nexit 0\n")
    rez_executable.chmod(0o755)

    monkeypatch.setenv("PATH", "")
    monkeypatch.delenv("SOTUGYO_REZ_PATH", raising=False)

    resolver = RezEnvironmentResolver()

    monkeypatch.setenv("SOTUGYO_REZ_PATH", str(bin_dir))

    called_env: dict | None = None

    def _fake_run(*_, **kwargs):
        nonlocal called_env
        called_env = kwargs.get("env")
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)

    result = resolver.resolve(["maya"], environment={})

    assert result.success is True
    assert called_env is not None
    path_entries = called_env["PATH"].split(os.pathsep)
    assert path_entries[0] == str(bin_dir)


def test_reconcile_registered_tool_matches_by_package_name() -> None:
    resolver = RezEnvironmentResolver()
    tool = make_tool("tool-registered")
    payload = {
        "tool_id": "maya",  # 古いプロジェクトでパッケージ名を tool_id に保存していたケース
        "rez_packages": ["maya"],
        "rez_package_name": "maya",
    }

    result = resolver.reconcile_registered_tool(
        payload=payload,
        registered_tools={tool.tool_id: tool},
        package_registry={tool.tool_id: "maya"},
    )

    assert result.tool == tool
    assert result.updated is True
    assert result.payload["tool_id"] == tool.tool_id
    assert result.payload["tool_name"] == tool.display_name
