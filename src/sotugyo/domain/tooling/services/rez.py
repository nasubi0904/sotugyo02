"""Rez コマンドを利用した環境検証ユーティリティ。"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
import importlib.util
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
class RezQueryResult:
    """Rez パッケージ照会の結果。"""

    success: bool
    checked: Tuple[str, ...]
    missing: Tuple[str, ...]
    message: str = ""

    def to_dict(self) -> Dict[str, object]:
        return {
            "success": self.success,
            "checked": list(self.checked),
            "missing": list(self.missing),
            "message": self.message,
        }


class RezPackageQueryService:
    """Rez Python API を使ってパッケージの存在を検証する。"""

    def check_requirements(self, requirements: Iterable[str]) -> RezQueryResult:
        normalized = tuple(
            entry.strip() for entry in requirements if isinstance(entry, str) and entry.strip()
        )
        if not normalized:
            return RezQueryResult(
                success=True,
                checked=(),
                missing=(),
                message="Rez パッケージの要求がありません。",
            )
        if importlib.util.find_spec("rez") is None:
            return RezQueryResult(
                success=False,
                checked=normalized,
                missing=normalized,
                message="rez Python モジュールが見つかりません。",
            )
        try:
            import rez  # noqa: F401
            from rez import packages as rez_packages  # type: ignore
        except ImportError as exc:
            return RezQueryResult(
                success=False,
                checked=normalized,
                missing=normalized,
                message=f"rez Python モジュールの読み込みに失敗しました: {exc}",
            )

        getter = getattr(rez_packages, "get_package_from_string", None)
        if getter is None:
            return RezQueryResult(
                success=False,
                checked=normalized,
                missing=normalized,
                message="rez.packages の照会 API が見つかりません。",
            )

        missing = []
        for requirement in normalized:
            try:
                package = getter(requirement)
            except Exception as exc:
                LOGGER.error("rez.query の呼び出しに失敗しました: %s", exc, exc_info=True)
                return RezQueryResult(
                    success=False,
                    checked=normalized,
                    missing=tuple(normalized),
                    message=f"rez.query の呼び出しに失敗しました: {exc}",
                )
            if package is None:
                missing.append(requirement)
        return RezQueryResult(
            success=not missing,
            checked=normalized,
            missing=tuple(missing),
            message="Rez パッケージの照会が完了しました。",
        )


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
        normalized = self._normalize_packages(packages)
        if not normalized:
            return RezResolveResult(
                success=True,
                command=(),
                stdout="Rez パッケージが指定されていないため検証を省略しました。",
            )

        env = self._build_environment(environment)

        if not self._is_executable_available(env):
            return RezResolveResult(
                success=False,
                command=(self._executable,),
                return_code=127,
                stderr="rez コマンドが見つかりません。パス設定を確認してください。",
            )

        command = self._build_command(normalized, variants or ())

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

    @staticmethod
    def _build_variant_arguments(variants: Iterable[str]) -> Tuple[str, ...]:
        normalized = [variant.strip() for variant in variants if variant and variant.strip()]
        if not normalized:
            return ()
        joined = ",".join(normalized)
        return ("--variants", joined)

    def _build_command(self, packages: Sequence[str], variants: Iterable[str]) -> list[str]:
        command: list[str] = [self._executable, "env", *packages]
        command.extend(self._build_variant_arguments(variants))
        command.extend(["--", "python", "-c", "pass"])
        return command

    def _build_environment(
        self, user_environment: Mapping[str, str] | None = None
    ) -> dict[str, str]:
        """Rez 実行用の環境変数セットを構築する。"""

        base_env = os.environ.copy()
        base_env.update(self._normalize_environment(user_environment))

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
    def _normalize_packages(packages: Sequence[str]) -> Tuple[str, ...]:
        return tuple(
            entry.strip() for entry in packages if isinstance(entry, str) and entry.strip()
        )

    @staticmethod
    def _normalize_environment(
        user_environment: Mapping[str, str] | None,
    ) -> dict[str, str]:
        if not user_environment:
            return {}
        normalized: dict[str, str] = {}
        for key, value in user_environment.items():
            if isinstance(key, str) and isinstance(value, str):
                normalized[key] = value
        return normalized

    def _is_executable_available(self, env: Mapping[str, str]) -> bool:
        path_env = env.get("PATH") or env.get("Path") or ""
        return shutil.which(self._executable, path=path_env) is not None


__all__ = [
    "RezEnvironmentResolver",
    "RezPackageQueryService",
    "RezQueryResult",
    "RezResolveResult",
]
