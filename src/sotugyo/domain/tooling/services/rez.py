"""Rez Python API を利用した環境検証ユーティリティ。"""

from __future__ import annotations

import logging
import os
import sys
import threading
from dataclasses import dataclass
from io import StringIO
from subprocess import PIPE
from typing import Dict, Iterable, Mapping, Sequence, Tuple

from rez.resolved_context import ResolvedContext
from rez.resolver import ResolverStatus


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
    """Rez Python API でパッケージ解決を検証する。"""

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
        package_paths = self._extract_package_paths(env)
        command_preview = self._build_command_preview(
            normalized,
            variants or (),
            ("python", "-c", "pass"),
        )

        try:
            context = self._create_context(
                normalized,
                package_paths=package_paths,
                time_limit=timeout,
            )
        except Exception as exc:  # pragma: no cover - 実行環境依存
            LOGGER.error("Rez 環境の解決に失敗しました: %s", exc)
            return RezResolveResult(
                success=False,
                command=command_preview,
                return_code=-1,
                stderr=str(exc),
            )

        success = self._is_context_solved(context)
        stdout = ""
        stderr = ""
        if not success:
            stderr = self._format_context_info(context)
            if stderr:
                LOGGER.error("Rez 解決失敗:\n%s", stderr)
                print(stderr, end="", file=sys.stderr)
        return RezResolveResult(
            success=success,
            command=command_preview,
            return_code=0 if success else 1,
            stdout=stdout,
            stderr=stderr,
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
        package_paths = self._extract_package_paths(env)
        rez_command = list(
            self._build_command_preview(
                normalized,
                variants or (),
                tuple(str(entry) for entry in command),
            )
        )

        try:
            context = self._create_context(
                normalized,
                package_paths=package_paths,
            )
        except Exception as exc:  # pragma: no cover - 実行環境依存
            LOGGER.error("Rez 環境の構築に失敗しました: %s", exc)
            return RezLaunchResult(
                success=False,
                command=tuple(rez_command),
                return_code=-1,
                stderr=str(exc),
            )

        if not self._is_context_solved(context):
            stderr = self._format_context_info(context)
            if stderr:
                print(stderr, end="", file=sys.stderr)
            return RezLaunchResult(
                success=False,
                command=tuple(rez_command),
                return_code=1,
                stderr=stderr or "Rez 環境の解決に失敗しました。",
            )

        try:
            process = context.execute_shell(
                command=[str(entry) for entry in command],
                parent_environ=env,
                block=False,
                stdout=PIPE,
                stderr=PIPE,
                text=True,
            )
        except OSError as exc:  # pragma: no cover - 実行環境依存
            LOGGER.error("Rez 起動処理に失敗しました: %s", exc)
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

    def _create_context(
        self,
        packages: Sequence[str],
        *,
        package_paths: Sequence[str] | None = None,
        time_limit: int | None = None,
    ) -> ResolvedContext:
        return ResolvedContext(
            package_requests=list(packages),
            package_paths=list(package_paths) if package_paths else None,
            time_limit=time_limit if time_limit is not None else -1,
        )

    @staticmethod
    def _build_variant_arguments(variants: Iterable[str]) -> Tuple[str, ...]:
        normalized = [variant.strip() for variant in variants if variant and variant.strip()]
        if not normalized:
            return ()
        joined = ",".join(normalized)
        return ("--variants", joined)

    def _build_command_preview(
        self,
        packages: Sequence[str],
        variants: Iterable[str],
        command: Sequence[str],
    ) -> Tuple[str, ...]:
        base = [self._executable, "env", *packages]
        base.extend(self._build_variant_arguments(variants))
        base.append("--")
        base.extend(command)
        return tuple(base)

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
    def _is_context_solved(context: ResolvedContext) -> bool:
        return context.status == ResolverStatus.solved

    @staticmethod
    def _format_context_info(context: ResolvedContext) -> str:
        buffer = StringIO()
        context.print_info(buf=buffer)
        return buffer.getvalue()

    def _extract_package_paths(self, env: Mapping[str, str]) -> list[str] | None:
        raw_paths = env.get("REZ_PACKAGES_PATH", "")
        entries = [entry.strip() for entry in raw_paths.split(os.pathsep) if entry.strip()]
        return entries or None

    @staticmethod
    def _stream_output(stream, is_error: bool) -> None:
        for line in stream:
            if is_error:
                print(line, end="", file=sys.stderr)
            else:
                print(line, end="")


__all__ = ["RezEnvironmentResolver", "RezLaunchResult", "RezResolveResult"]
