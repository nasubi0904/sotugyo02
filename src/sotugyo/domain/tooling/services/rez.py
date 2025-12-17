"""Rez コマンドを利用した環境検証ユーティリティ。"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Dict, Iterable, Mapping, Optional, Sequence, Tuple

from ..models import RegisteredTool


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
class ToolRegistrationResolution:
    """登録済みツールの突き合わせ結果。"""

    tool: Optional[RegisteredTool]
    payload: Dict[str, object]
    updated: bool = False


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

    @property
    def executable(self) -> str:
        """Rez CLI 実行に使用するコマンド名を返す。"""

        return self._executable

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

    def build_environment(
        self, user_environment: Mapping[str, str] | None = None
    ) -> dict[str, str]:
        """Rez 実行用に PATH をマージした環境変数セットを生成する。"""

        return self._build_environment(user_environment)

    @staticmethod
    def build_variant_arguments(variants: Iterable[str]) -> Tuple[str, ...]:
        """`rez env` へ渡すバリアント引数を組み立てる。"""

        return RezEnvironmentResolver._build_variant_arguments(variants)

    def reconcile_registered_tool(
        self,
        *,
        payload: Mapping[str, object],
        registered_tools: Mapping[str, RegisteredTool],
        package_registry: Mapping[str, str] | None = None,
        package_candidates: Iterable[str] | None = None,
    ) -> ToolRegistrationResolution:
        """ノードに保存されたツール情報を登録済みツールと突き合わせる。"""

        normalized_payload = dict(payload)
        tool_id = self._normalize_identifier(normalized_payload.get("tool_id"))
        template_id = self._normalize_identifier(normalized_payload.get("template_id"))
        tool_name = self._normalize_identifier(normalized_payload.get("tool_name"))
        registry_packages: dict[str, str] = {}
        for reg_tool_id, package_name in (package_registry or {}).items():
            if not isinstance(package_name, str) or not package_name.strip():
                continue
            tool_obj = registered_tools.get(reg_tool_id)
            if tool_obj is None:
                continue
            registry_packages[tool_obj.tool_id] = package_name.strip()
        package_candidates = self._normalize_package_candidates(
            package_candidates, normalized_payload
        )

        tool = registered_tools.get(tool_id) if tool_id else None
        if tool is None and template_id:
            tool = next(
                (
                    candidate
                    for candidate in registered_tools.values()
                    if candidate.template_id == template_id
                ),
                None,
            )

        if tool is None and tool_name:
            tool = next(
                (
                    candidate
                    for candidate in registered_tools.values()
                    if candidate.display_name == tool_name
                ),
                None,
            )

        if tool is None and registry_packages and package_candidates:
            for candidate in package_candidates:
                matched = next(
                    (
                        registered_tools.get(tool_id)
                        for tool_id, package_name in registry_packages.items()
                        if package_name == candidate
                    ),
                    None,
                )
                if matched is not None:
                    tool = matched
                    break

        if tool is None:
            return ToolRegistrationResolution(tool=None, payload=normalized_payload)

        updated = False
        if tool.tool_id != tool_id:
            normalized_payload["tool_id"] = tool.tool_id
            updated = True
        if tool.display_name and normalized_payload.get("tool_name") != tool.display_name:
            normalized_payload["tool_name"] = tool.display_name
            updated = True

        return ToolRegistrationResolution(
            tool=tool,
            payload=normalized_payload,
            updated=updated,
        )

    @staticmethod
    def _normalize_package_candidates(
        candidates: Iterable[str] | None, payload: Mapping[str, object]
    ) -> tuple[str, ...]:
        normalized: list[str] = []
        if candidates is not None:
            for entry in candidates:
                if isinstance(entry, str) and entry.strip():
                    normalized.append(entry.strip())
        direct = payload.get("rez_package_name")
        if isinstance(direct, str) and direct.strip():
            normalized.append(direct.strip())
        packages = payload.get("rez_packages")
        if isinstance(packages, (list, tuple)):
            normalized.extend(
                entry.strip()
                for entry in packages
                if isinstance(entry, str) and entry.strip()
            )
        return tuple(dict.fromkeys(normalized))

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

    @staticmethod
    def _normalize_identifier(value: object) -> str:
        if isinstance(value, str):
            return value.strip()
        return ""


__all__ = [
    "RezEnvironmentResolver",
    "RezResolveResult",
    "ToolRegistrationResolution",
]
