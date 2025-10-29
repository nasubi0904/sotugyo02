"""Rez コマンドを利用した環境検証ユーティリティ。"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Dict, Iterable, Mapping, Sequence, Tuple


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


class RezEnvironmentResolver:
    """Rez CLI を呼び出してパッケージ解決を検証する。"""

    def __init__(self, executable: str = "rez") -> None:
        self._executable = executable

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

        executable = self._executable
        if shutil.which(executable) is None:
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

        env = os.environ.copy()
        if environment:
            for key, value in environment.items():
                if isinstance(key, str) and isinstance(value, str):
                    env[key] = value

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
            return RezResolveResult(
                success=False,
                command=tuple(command),
                return_code=-1,
                stderr=str(exc),
            )

        success = completed.returncode == 0
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


__all__ = ["RezEnvironmentResolver", "RezResolveResult"]
