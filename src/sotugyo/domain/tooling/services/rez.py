"""Rez コマンドを利用した環境検証ユーティリティ。"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
import traceback
from typing import Dict, Iterable, Mapping, Sequence, Tuple


LOGGER = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class RezResolveResult:
    """Rez 環境解決の結果。"""

    success: bool
    command: Tuple[str, ...]
    return_code: int = 0
    stdout: str = ""
    stderr: str = ""

    def message(self) -> str:
        if self.success:
            return "Rez 環境の解決に成功しました。"
        if self.stderr.strip():
            return self.stderr.strip()
        if self.stdout.strip():
            return self.stdout.strip()
        return "Rez 環境の解決に失敗しました。"

    def to_dict(self) -> Dict[str, object]:
        return {
            "success": self.success,
            "command": list(self.command),
            "return_code": self.return_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }


@dataclass(slots=True, frozen=True)
class RezLaunchResult:
    """Rez 環境でツールを起動した結果。"""

    success: bool
    command: Tuple[str, ...]
    pid: int | None = None
    stdout: str = ""
    stderr: str = ""
    traceback_text: str = ""

    def message(self) -> str:
        if self.success:
            return "Rez 環境でのツール起動に成功しました。"
        if self.stderr.strip():
            return self.stderr.strip()
        if self.stdout.strip():
            return self.stdout.strip()
        if self.traceback_text.strip():
            return self.traceback_text.strip()
        return "Rez 環境でのツール起動に失敗しました。"

    def to_dict(self) -> Dict[str, object]:
        return {
            "success": self.success,
            "command": list(self.command),
            "pid": self.pid,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "traceback": self.traceback_text,
        }


class RezEnvironmentResolver:
    """Rez CLI を呼び出してパッケージ解決を検証する。"""

    def __init__(
        self,
        executable: str = "rez",
        *,
        path_env_var: str = "SOTUGYO_REZ_PATH",
    ) -> None:
        self._executable = executable
        self._path_env_var = path_env_var
        self._apply_rez_path_hint()

    def resolve(
        self,
        packages: Sequence[str],
        *,
        variants: Sequence[str] | None = None,
        environment: Mapping[str, str] | None = None,
        timeout: int | None = 60,
    ) -> RezResolveResult:
        normalized = tuple(
            entry.strip() for entry in packages if isinstance(entry, str) and entry.strip()
        )
        if not normalized:
            return RezResolveResult(
                success=True,
                command=(),
                stdout="Rez パッケージが指定されていないため検証を省略しました。",
            )

        env = self._build_environment(environment)
        path_env = env.get("PATH") or env.get("Path") or ""

        executable = self._executable
        if shutil.which(executable, path=path_env) is None:
            return RezResolveResult(
                success=False,
                command=(executable,),
                return_code=127,
                stderr="rez コマンドが見つかりません。パス設定を確認してください。",
            )

        command: list[str] = [executable, "env", *normalized]
        variant_args = self._build_variant_arguments(variants or ())
        command.extend(variant_args)
        command.extend(["--", "python", "-c", "pass"])

        try:
            completed = subprocess.run(  # noqa: S603,S607 - 実行コマンドを明示
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                env=env,
            )
        except (OSError, subprocess.SubprocessError) as exc:  # pragma: no cover - 実行環境依存
            LOGGER.error("Rez コマンドの実行に失敗しました: %s", exc)
            return RezResolveResult(
                success=False,
                command=tuple(command),
                return_code=-1,
                stderr=str(exc),
            )

        success = completed.returncode == 0
        if not success:
            if completed.stdout:
                LOGGER.error("Rez コマンド標準出力:\n%s", completed.stdout)
            if completed.stderr:
                LOGGER.error("Rez コマンド標準エラー:\n%s", completed.stderr)
        return RezResolveResult(
            success=success,
            command=tuple(command),
            return_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    def launch_tool(
        self,
        executable_path: str,
        *,
        packages: Sequence[str] | None = None,
        variants: Sequence[str] | None = None,
        environment: Mapping[str, str] | None = None,
        args: Sequence[str] | None = None,
    ) -> RezLaunchResult:
        normalized_packages = tuple(
            entry.strip() for entry in (packages or ()) if isinstance(entry, str) and entry.strip()
        )
        executable = executable_path.strip()
        if not executable:
            return RezLaunchResult(
                success=False,
                command=(),
                stderr="起動する実行ファイルが指定されていません。",
            )
        executable_path_obj = Path(executable)
        try:
            executable_exists = executable_path_obj.exists()
        except OSError:
            executable_exists = False
        if not executable_exists:
            return RezLaunchResult(
                success=False,
                command=(executable,),
                stderr=f"実行ファイルが見つかりません: {executable}",
            )
        executable = str(executable_path_obj)
        env_vars = self._build_environment(environment)
        path_env = env_vars.get("PATH") or env_vars.get("Path") or ""

        if normalized_packages:
            if shutil.which(self._executable, path=path_env) is None:
                return RezLaunchResult(
                    success=False,
                    command=(self._executable,),
                    stderr="rez コマンドが見つかりません。パス設定を確認してください。",
                )
            command: list[str] = [self._executable, "env", *normalized_packages]
            variant_args = self._build_variant_arguments(variants or ())
            command.extend(variant_args)
            command.extend(["--", executable])
        else:
            command = [executable]

        if args:
            command.extend(str(arg) for arg in args if str(arg).strip())

        try:
            process = subprocess.Popen(  # noqa: S603,S607 - 実行コマンドを明示
                command,
                env=env_vars,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except (OSError, subprocess.SubprocessError) as exc:  # pragma: no cover - 実行環境依存
            return RezLaunchResult(
                success=False,
                command=tuple(command),
                stderr=str(exc),
                traceback_text=traceback.format_exc(),
            )

        self._stream_output(process, stream_name="stdout", level=logging.INFO)
        self._stream_output(process, stream_name="stderr", level=logging.ERROR)

        return RezLaunchResult(
            success=True,
            command=tuple(command),
            pid=process.pid,
        )

    @staticmethod
    def _stream_output(process: subprocess.Popen, *, stream_name: str, level: int) -> None:
        stream = getattr(process, stream_name, None)
        if stream is None:
            return

        def _run() -> None:
            try:
                for line in stream:
                    if not line:
                        continue
                    LOGGER.log(level, "[rez %s] %s", stream_name, line.rstrip())
            except Exception:  # pragma: no cover - ストリーム読み取りエラーはログのみ
                LOGGER.debug("Rez 出力の読み取り中に例外が発生しました", exc_info=True)

        threading.Thread(target=_run, name=f"RezStream-{stream_name}", daemon=True).start()

    @staticmethod
    def _build_variant_arguments(variants: Iterable[str]) -> Tuple[str, ...]:
        normalized = [variant.strip() for variant in variants if variant and variant.strip()]
        if not normalized:
            return ()
        joined = ",".join(normalized)
        return ("--variants", joined)

    def _build_environment(
        self, user_environment: Mapping[str, str] | None = None
    ) -> dict[str, str]:
        """Rez 実行用の環境変数セットを構築する。"""

        base_env = os.environ.copy()
        if user_environment:
            for key, value in user_environment.items():
                if isinstance(key, str) and isinstance(value, str):
                    base_env[key] = value

        path_value = self._build_path_value(base_env)
        base_env["PATH"] = path_value
        base_env["Path"] = path_value
        return base_env

    def _build_path_value(self, env: Mapping[str, str]) -> str:
        rez_path_raw = env.get(self._path_env_var, "")
        hint_paths = [entry.strip() for entry in rez_path_raw.split(os.pathsep) if entry.strip()]

        current_path = env.get("PATH") or env.get("Path") or ""
        existing_entries = [entry for entry in current_path.split(os.pathsep) if entry]
        merged_entries = list(dict.fromkeys([*hint_paths, *existing_entries]))
        return os.pathsep.join(merged_entries)

    def _apply_rez_path_hint(self) -> None:
        """PATH を上書きして後続のプロセスに Rez パスを伝搬させる。"""

        updated_env = self._build_environment({})
        os.environ.update(
            {
                "PATH": updated_env["PATH"],
                "Path": updated_env["Path"],
            }
        )


__all__ = ["RezEnvironmentResolver", "RezLaunchResult", "RezResolveResult"]
