"""Rez コマンドを利用した環境検証ユーティリティ。"""

from __future__ import annotations

import logging
import importlib.util
import os
import subprocess
import sys
import threading
from dataclasses import dataclass
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
    """Rez 実行の結果。"""

    success: bool
    command: Tuple[str, ...]
    return_code: int = 0
    stdout: str = ""
    stderr: str = ""
    process_id: int | None = None

    def message(self) -> str:
        if self.success:
            return "Rez でツールを起動しました。"
        if self.stderr.strip():
            return self.stderr.strip()
        if self.stdout.strip():
            return self.stdout.strip()
        return "Rez による起動に失敗しました。"


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
        if not self._rez_available():
            return RezResolveResult(
                success=False,
                command=self._build_rez_command_prefix(),
                return_code=127,
                stderr="rez モジュールが見つかりません。パス設定を確認してください。",
            )

        command: list[str] = [*self._build_rez_command_prefix(), "env", *normalized]
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
        if completed.stdout:
            print(completed.stdout, end="")
        if completed.stderr:
            print(completed.stderr, end="", file=sys.stderr)
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

    def launch(
        self,
        packages: Sequence[str],
        *,
        variants: Sequence[str] | None = None,
        environment: Mapping[str, str] | None = None,
        command: Sequence[str],
        packages_path: Sequence[str] | None = None,
    ) -> RezLaunchResult:
        normalized = tuple(
            entry.strip() for entry in packages if isinstance(entry, str) and entry.strip()
        )
        if not normalized:
            return RezLaunchResult(
                success=False,
                command=(),
                return_code=2,
                stderr="Rez パッケージが指定されていません。",
            )
        if not command:
            return RezLaunchResult(
                success=False,
                command=(),
                return_code=2,
                stderr="起動コマンドが指定されていません。",
            )

        env = self._build_environment(environment, packages_path=packages_path)
        if not self._rez_available():
            return RezLaunchResult(
                success=False,
                command=self._build_rez_command_prefix(),
                return_code=127,
                stderr="rez モジュールが見つかりません。パス設定を確認してください。",
            )

        rez_command: list[str] = [*self._build_rez_command_prefix(), "env", *normalized]
        rez_command.extend(self._build_variant_arguments(variants or ()))
        rez_command.append("--")
        rez_command.extend(str(entry) for entry in command)

        try:
            process = subprocess.Popen(  # noqa: S603,S607 - ツール実行を許可
                rez_command,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except OSError as exc:  # pragma: no cover - 実行環境依存
            LOGGER.error("Rez 起動コマンドの実行に失敗しました: %s", exc)
            return RezLaunchResult(
                success=False,
                command=tuple(rez_command),
                return_code=-1,
                stderr=str(exc),
            )

        if process.stdout:
            threading.Thread(
                target=self._stream_output,
                args=(process.stdout, False),
                daemon=True,
            ).start()
        if process.stderr:
            threading.Thread(
                target=self._stream_output,
                args=(process.stderr, True),
                daemon=True,
            ).start()

        return RezLaunchResult(
            success=True,
            command=tuple(rez_command),
            process_id=process.pid,
        )

    @staticmethod
    def _build_variant_arguments(variants: Iterable[str]) -> Tuple[str, ...]:
        normalized = [variant.strip() for variant in variants if variant and variant.strip()]
        if not normalized:
            return ()
        joined = ",".join(normalized)
        return ("--variants", joined)

    def _build_environment(
        self,
        user_environment: Mapping[str, str] | None = None,
        *,
        packages_path: Sequence[str] | None = None,
    ) -> dict[str, str]:
        """Rez 実行用の環境変数セットを構築する。"""

        base_env = os.environ.copy()
        if user_environment:
            for key, value in user_environment.items():
                if isinstance(key, str) and isinstance(value, str):
                    base_env[key] = value

        if packages_path:
            resolved_paths = [
                entry.strip()
                for entry in packages_path
                if isinstance(entry, str) and entry.strip()
            ]
            if resolved_paths:
                existing = base_env.get("REZ_PACKAGES_PATH", "")
                existing_entries = [
                    entry for entry in existing.split(os.pathsep) if entry.strip()
                ]
                merged = list(dict.fromkeys([*resolved_paths, *existing_entries]))
                base_env["REZ_PACKAGES_PATH"] = os.pathsep.join(merged)

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

    @staticmethod
    def _rez_available() -> bool:
        return importlib.util.find_spec("rez") is not None

    @staticmethod
    def _build_rez_command_prefix() -> Tuple[str, ...]:
        return (sys.executable, "-m", "rez")

    @staticmethod
    def _stream_output(stream, is_error: bool) -> None:
        for line in stream:
            if is_error:
                print(line, end="", file=sys.stderr)
            else:
                print(line, end="")


__all__ = ["RezEnvironmentResolver", "RezLaunchResult", "RezResolveResult"]
