from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from src.sotugyo.domain.tooling.repositories.config import ToolConfigRepository
from src.sotugyo.domain.tooling.repositories.rez_packages import RezPackageRepository
from src.sotugyo.domain.tooling.services.facade import ToolEnvironmentService


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def test_launch_environment_runs_dummy_tool(monkeypatch) -> None:
    with TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        rez_dir = root / "rez_bin"
        rez_dir.mkdir(parents=True, exist_ok=True)
        package_root = root / "packages"
        package_root.mkdir(parents=True, exist_ok=True)
        output_file = root / "launch.txt"

        dummy_tool = root / "dummyTool.exe.test"
        _write_executable(
            dummy_tool,
            "\n".join(
                [
                    f"#!{sys.executable}",
                    "from pathlib import Path",
                    f"Path(r\"{output_file}\").write_text(\"ok\", encoding=\"utf-8\")",
                ]
            ),
        )

        rez_command = rez_dir / "rez"
        _write_executable(
            rez_command,
            "\n".join(
                [
                    f"#!{sys.executable}",
                    "import subprocess",
                    "import sys",
                    "args = sys.argv[1:]",
                    "if '--' in args:",
                    "    idx = args.index('--')",
                    "    command = args[idx + 1:]",
                    "else:",
                    "    command = []",
                    "if not command:",
                    "    sys.exit(2)",
                    "completed = subprocess.run(command, check=False)",
                    "sys.exit(completed.returncode)",
                ]
            ),
        )

        monkeypatch.setenv("SOTUGYO_REZ_PATH", str(rez_dir))
        monkeypatch.setenv("PATH", "")

        repository = ToolConfigRepository(storage_dir=package_root)
        rez_repository = RezPackageRepository(root_dir=package_root)
        service = ToolEnvironmentService(
            repository=repository,
            rez_repository=rez_repository,
        )

        environment = service.register_tool(
            display_name="DummyTool",
            executable_path=dummy_tool,
            template_id="autodesk.maya",
            version="2025",
        )

        package_name = environment.rez_packages[0] if environment.rez_packages else ""
        result = service.launch_environment(package_name)
        assert result.success is True

        timeout = time.time() + 5.0
        while time.time() < timeout and not output_file.exists():
            time.sleep(0.1)

        assert output_file.exists()
