# -*- coding: utf-8 -*-
"""
rez_detached_launcher.py

コンセプト
----------
- Rez パッケージ環境を介して DCC/ツールを起動する。
- 親プロセスが落ちても、起動したツールが落ちないよう「独立起動(detached)」する。
- 標準出力/標準エラーは、親プロセスのパイプ監視ではなく「ログファイルへリダイレクト」する。
  （親が死んだ後でもログが残るため）
- Rez パッケージ探索パスに %LOCALAPPDATA%\\KDMrez を「実行時に」安全に追加する（永続変更しない）。

追加仕様（今回の改造）
----------------------
- `--` 以降の tool_args が省略された場合、
  Rez 環境内の環境変数から `EXECUTE_` で始まる変数を探索し、
  その値（exe パス）を起動コマンドとして採用する。
- `EXECUTE_` 変数が複数ある場合は曖昧なのでエラーとし、
  `--exec-var` により使用する変数名を明示できる。

提供する主な API
----------------
- ensure_kdmrez_in_rez_packages_path()
- resolve_rez_env_exe()
- build_rez_env_command()
- launch_detached_with_log()
- launch_rez_detached()  ← 外部からはこれを呼ぶのが基本
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence, Tuple, Dict, List


# =========================
# 例外（呼び出し側が握れるように明確化）
# =========================
class RezLauncherError(RuntimeError):
    """本モジュールの基底例外。"""


class RezEnvNotFoundError(RezLauncherError):
    """rez-env 実行ファイルが見つからない。"""


class InvalidArgumentsError(RezLauncherError):
    """引数が不正（空、型不一致、存在しないディレクトリ等）。"""


class LaunchError(RezLauncherError):
    """プロセス起動に失敗。"""


class ExecuteVarNotFoundError(RezLauncherError):
    """EXECUTE_ 変数が見つからない / 指定された EXECUTE_ 変数が存在しない。"""


class ExecuteVarAmbiguousError(RezLauncherError):
    """EXECUTE_ 変数が複数あり、どれを使うべきか曖昧。"""


# =========================
# 設定データ（呼び出し側で組み立てやすい）
# =========================
@dataclass(frozen=True)
class LaunchResult:
    pid: int
    log_path: Path
    command: Tuple[str, ...]  # 実行したコマンド（確認用）


# =========================
# 関数ごとの説明（簡潔・確実）
# =========================
def ensure_kdmrez_in_rez_packages_path(prepend_path: Optional[Path] = None) -> Path:
    """
    REZ_PACKAGES_PATH に %LOCALAPPDATA%\\KDMrez を「このプロセス内だけ」安全に追加する。

    - 永続設定（レジストリ/ユーザー環境変数）を変更しない。
    - 既に含まれていれば何もしない。
    - 追加は先頭(prepend)とし、KDMrez を優先探索させる。

    引数:
        prepend_path: 追加したいパスを明示する場合に指定（通常は None）

    戻り値:
        実際に追加を試みたパス（存在チェックはここでは強制しない）
    """
    if prepend_path is None:
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        if local_appdata:
            prepend_path = Path(local_appdata) / "KDMrez"
        else:
            prepend_path = Path.home() / "AppData" / "Local" / "KDMrez"

    target = str(prepend_path)

    current = os.environ.get("REZ_PACKAGES_PATH", "")
    parts = [p for p in current.split(";") if p] if current else []
    lowered = {p.lower() for p in parts}

    if target.lower() not in lowered:
        parts.insert(0, target)
        os.environ["REZ_PACKAGES_PATH"] = ";".join(parts)

    return prepend_path


def resolve_rez_env_exe(hint: Optional[str] = None) -> str:
    """
    rez-env 実行ファイルを確実に見つける。

    探索順:
      1) hint（フルパスなど）を指定した場合はそれ
      2) PATH 上の rez-env(.exe)
      3) 現在の Python 実行ファイル近傍（venv/埋め込み環境の Scripts）にある rez-env.exe

    失敗時:
      RezEnvNotFoundError を送出
    """
    if hint:
        p = Path(hint)
        if p.exists():
            return str(p)
        # hint が無効でも次の探索へ進む（呼び出し側が柔軟に運用できるように）

    w = shutil.which("rez-env")
    if w:
        return w

    py = Path(sys.executable)

    candidates = (
        py.parent / "rez-env.exe",
        py.parent / "rez-env",
        py.parent / "Scripts" / "rez-env.exe",
        py.parent / "Scripts" / "rez-env",
    )
    for c in candidates:
        if c.exists():
            return str(c)

    raise RezEnvNotFoundError(
        "rez-env が見つかりません。PATH または現在の Python 環境の Scripts に rez-env.exe が必要です。"
    )


def build_rez_env_command(
    rez_env_exe: str,
    package_request: str,
    tool_args: Sequence[str],
) -> Tuple[str, ...]:
    """
    rez-env の実行コマンドを生成する。

    形式:
      rez-env <package_request> -- <tool> <args...>

    注意:
      tool_args は ['AfterFX'] のように「コマンド単位」で渡す。
      文字列 1 つを文字分解して渡すような処理はここでは一切しない。

    失敗時:
      InvalidArgumentsError を送出
    """
    if not rez_env_exe:
        raise InvalidArgumentsError("rez_env_exe が空です。")
    if not package_request or not isinstance(package_request, str):
        raise InvalidArgumentsError("package_request が不正です（空または非文字列）。")
    if not tool_args:
        raise InvalidArgumentsError("tool_args が空です（起動コマンドが必要です）。")

    # tool_args 内に空文字が混じるのは事故率が高いので弾く
    if any((not isinstance(a, str)) or (a.strip() == "") for a in tool_args):
        raise InvalidArgumentsError("tool_args に空要素または非文字列が含まれています。")

    return tuple([rez_env_exe, package_request, "--", *tool_args])


def _sanitize_log_token(value: str) -> str:
    """ログファイル名に使えるよう簡易サニタイズする。"""
    cleaned = value.strip().replace(" ", "_")
    for ch in ("/", "\\", ":", "*", "?", "\"", "<", ">", "|"):
        cleaned = cleaned.replace(ch, "_")
    return cleaned or "tool"


def _make_log_path(
    log_dir: Optional[str],
    package_request: str,
    tool_args: Sequence[str],
) -> Path:
    """
    ログファイルの保存先を決める（安全に一意化）。
    """
    ts = time.strftime("%Y%m%d_%H%M%S")
    base_dir = Path(log_dir) if log_dir else Path(os.environ.get("TEMP", ".")) / "rez_detached_logs"
    tool = _sanitize_log_token(Path(tool_args[0]).name)
    package_label = _sanitize_log_token(package_request)
    name = f"{package_label}__{tool}__{ts}.log"
    return base_dir / name


def launch_detached_with_log(
    command: Sequence[str],
    log_path: Path,
    env: Optional[dict] = None,
) -> int:
    """
    コマンドを「独立起動(detached)」し、stdout/stderr を log_path に書き込む。

    目的:
      - 親プロセスがクラッシュしても子が落ちないようにする
      - コンソール窓（空の cmd）が出ないようにする

    戻り値:
      起動したプロセスの PID

    失敗時:
      LaunchError を送出
    """
    if not command:
        raise InvalidArgumentsError("command が空です。")
    if not isinstance(log_path, Path):
        raise InvalidArgumentsError("log_path は Path である必要があります。")

    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Windows creation flags
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    CREATE_NO_WINDOW = 0x08000000

    # 念押しの非表示（コンソールアプリに効く）
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0  # SW_HIDE

    try:
        with log_path.open("a", encoding="utf-8", errors="replace") as f:
            p = subprocess.Popen(
                list(command),
                stdin=subprocess.DEVNULL,
                stdout=f,
                stderr=subprocess.STDOUT,
                env=(env if env is not None else os.environ.copy()),
                creationflags=CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW,
                startupinfo=si,
                close_fds=True,
            )
            return int(p.pid)
    except OSError as e:
        raise LaunchError(f"プロセス起動に失敗しました: {e}") from e


def tail_log_file(log_path: Path, poll_sec: float = 0.2) -> None:
    """
    ログファイルを簡易的に tail する（親が生存中だけ使用する想定）。

    注意:
      親が落ちた後は当然 tail できないため、
      「親が落ちてもログは残る」目的に対して補助的な機能です。
    """
    if poll_sec <= 0:
        raise InvalidArgumentsError("poll_sec は正の値が必要です。")

    # ファイル生成待ち（起動直後対策）
    for _ in range(50):
        if log_path.exists():
            break
        time.sleep(poll_sec)

    if not log_path.exists():
        return

    with log_path.open("r", encoding="utf-8", errors="replace") as f:
        while True:
            line = f.readline()
            if line:
                print(line, end="")
            else:
                time.sleep(poll_sec)


# =========================
# 追加: Rez 環境内の EXECUTE_ 変数を取得して起動コマンドを決める
# =========================
def _collect_execute_vars_via_rez_env(
    rez_env_exe: str,
    package_request: str,
    rez_env_hint: Optional[str] = None,
    extra_env: Optional[dict] = None,
) -> Dict[str, str]:
    """
    rez-env <pkg> -- python -c ... を実行し、Rez 環境内で定義された EXECUTE_ 変数を収集する。

    返り値:
      {"EXECUTE_...": "C:\\path\\to\\exe", ...}

    失敗時:
      RezLauncherError 派生例外を送出
    """
    # Windows でも確実に動くよう python 実行を優先
    # （rez-env は指定した Python を解決する可能性があるため）
    probe = (
        "import os, json; "
        "d={k:v for k,v in os.environ.items() if k.startswith('EXECUTE_') and v}; "
        "print(json.dumps(d, ensure_ascii=False))"
    )

    cmd = [rez_env_exe, package_request, "--", sys.executable, "-c", probe]

    try:
        cp = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=(extra_env if extra_env is not None else os.environ.copy()),
            check=False,
        )
    except OSError as e:
        raise LaunchError(f"EXECUTE_ 変数取得用の rez-env 実行に失敗しました: {e}") from e

    if cp.returncode != 0:
        # stderr も stdout に含めて最低限のトラブルシュート情報を残す
        msg = (cp.stderr or "").strip()
        out = (cp.stdout or "").strip()
        detail = msg if msg else out
        raise LaunchError(f"EXECUTE_ 変数の取得に失敗しました（rez-env returncode={cp.returncode}）。{detail}")

    raw = (cp.stdout or "").strip()
    if not raw:
        return {}

    try:
        import json as _json
        data = _json.loads(raw)
        if isinstance(data, dict):
            # 値が文字列であることだけ保証
            return {str(k): str(v) for k, v in data.items() if str(v).strip()}
        return {}
    except Exception as e:
        raise LaunchError(f"EXECUTE_ 変数の解析に失敗しました（JSON として解釈不可）。stdout={raw}") from e


def _resolve_tool_args_from_execute_vars(
    execute_vars: Dict[str, str],
    exec_var: Optional[str] = None,
) -> List[str]:
    """
    収集した EXECUTE_ 変数群から、起動に使う tool_args（先頭は exe）を決定する。

    ルール:
      - exec_var が指定されていればそれを優先（存在しない場合はエラー）
      - 未指定なら EXECUTE_ 変数が 1個のときのみ採用
      - 0個ならエラー、複数なら曖昧エラー
    """
    if exec_var:
        if exec_var not in execute_vars:
            raise ExecuteVarNotFoundError(
                f"--exec-var で指定された '{exec_var}' が見つかりません。"
                f" 利用可能: {sorted(execute_vars.keys())}"
            )
        exe = execute_vars[exec_var].strip()
        if not exe:
            raise ExecuteVarNotFoundError(f"'{exec_var}' の値が空です。")
        return [exe]

    keys = sorted(execute_vars.keys())
    if not keys:
        raise ExecuteVarNotFoundError(
            "EXECUTE_ で始まる環境変数が Rez 環境内に見つかりません。"
            " package.py 側で EXECUTE_... を定義してください。"
        )

    if len(keys) > 1:
        raise ExecuteVarAmbiguousError(
            "EXECUTE_ 変数が複数見つかりました。どれを起動すべきか曖昧です。"
            f" 見つかった候補: {keys}  /  --exec-var で使用する変数名を指定してください。"
        )

    exe = execute_vars[keys[0]].strip()
    if not exe:
        raise ExecuteVarNotFoundError(f"'{keys[0]}' の値が空です。")
    return [exe]


def launch_rez_detached(
    package_request: str,
    tool_args: Optional[Sequence[str]] = None,
    rez_env_hint: Optional[str] = None,
    log_dir: Optional[str] = None,
    add_kdmrez: bool = True,
    exec_var: Optional[str] = None,
) -> LaunchResult:
    """
    外部から呼ぶ「高レベル API」。
    Rez パッケージからツールを独立起動し、ログファイルへ出力する。

    引数:
      package_request:
        例) "adobe_after_effects-2025", "dcc_houdini-21.0.440"
      tool_args:
        例) ["AfterFX"] / ["houdinifx"] / ["houdinifx", "-foreground"] 等
        None または空の場合は、Rez 環境内の EXECUTE_... 変数から起動コマンドを自動解決する。
      rez_env_hint:
        rez-env.exe のパスを明示したい場合に指定（None なら自動探索）
      log_dir:
        ログ保存ディレクトリ（None/空なら %TEMP%\\rez_detached_logs）
      add_kdmrez:
        True の場合、REZ_PACKAGES_PATH に %LOCALAPPDATA%\\KDMrez を実行時に追加する
      exec_var:
        EXECUTE_ 変数が複数ある場合などに、使う変数名を明示する（例: "EXECUTE_ADOBE_AFTER_EFFECTS_EXE"）

    戻り値:
      LaunchResult(pid, log_path, command)

    例外:
      RezEnvNotFoundError / InvalidArgumentsError / LaunchError / ExecuteVarNotFoundError / ExecuteVarAmbiguousError
    """
    if add_kdmrez:
        ensure_kdmrez_in_rez_packages_path()

    rez_env = resolve_rez_env_exe(rez_env_hint)

    # tool_args が無い場合は EXECUTE_... から自動解決
    resolved_tool_args: List[str]
    if tool_args:
        resolved_tool_args = list(tool_args)
    else:
        execute_vars = _collect_execute_vars_via_rez_env(
            rez_env_exe=rez_env,
            package_request=package_request,
            rez_env_hint=rez_env_hint,
            extra_env=os.environ.copy(),
        )
        resolved_tool_args = _resolve_tool_args_from_execute_vars(execute_vars, exec_var=exec_var)

    cmd = build_rez_env_command(rez_env, package_request, resolved_tool_args)
    log_path = _make_log_path(log_dir, package_request, resolved_tool_args)

    pid = launch_detached_with_log(cmd, log_path, env=os.environ.copy())
    return LaunchResult(pid=pid, log_path=log_path, command=cmd)


# =========================
# 任意: CLI（モジュール利用が主目的なので最小限）
# =========================
def _parse_cli(
    argv: Optional[Sequence[str]] = None
) -> Tuple[str, Sequence[str], Optional[str], Optional[str], bool, bool, Optional[str]]:
    """
    CLI 用引数解析（必要最小限）。

    - `--` 以降が空の場合でもエラーにせず、
      EXECUTE_... による自動解決で起動できるようにする。
    """
    import argparse as _argparse

    ap = _argparse.ArgumentParser()
    ap.add_argument("--pkg", required=True, help="Rez パッケージ要求（例: adobe_after_effects-2025）")
    ap.add_argument("--rez-env", default=None, help="rez-env.exe のパス（省略可）")
    ap.add_argument("--logdir", default=None, help="ログ保存先ディレクトリ（省略可）")
    ap.add_argument("--no-kdmrez", action="store_true", help="KDMrez を REZ_PACKAGES_PATH に追加しない")
    ap.add_argument("--tail", action="store_true", help="起動後にログを tail する（親が生存中のみ）")
    ap.add_argument(
        "--exec-var",
        default=None,
        help="EXECUTE_ 変数が複数ある場合に使用する変数名を指定（例: EXECUTE_ADOBE_AFTER_EFFECTS_EXE）",
    )

    # `--` 以降をそのまま tool_args に
    ap.add_argument("tool_args", nargs=_argparse.REMAINDER, help="`--` の後に起動コマンドと引数（省略可）")

    ns = ap.parse_args(argv)

    tool_args = list(ns.tool_args)
    if tool_args and tool_args[0] == "--":
        tool_args = tool_args[1:]

    # ここでは「空でもOK」にする（自動解決に回すため）
    return ns.pkg, tool_args, ns.rez_env, ns.logdir, (not ns.no_kdmrez), ns.tail, ns.exec_var


def main(argv: Optional[Sequence[str]] = None) -> int:
    """
    CLI エントリ。
    モジュールとして import 利用する場合は、この main を使う必要はありません。
    """
    try:
        pkg, tool_args, rez_env, logdir, add_kdmrez, do_tail, exec_var = _parse_cli(argv)

        # tool_args が空なら自動解決に回すため、None を渡す
        tool_args_opt = tool_args if tool_args else None

        result = launch_rez_detached(
            package_request=pkg,
            tool_args=tool_args_opt,
            rez_env_hint=rez_env,
            log_dir=logdir,
            add_kdmrez=add_kdmrez,
            exec_var=exec_var,
        )
        print(f"[launcher] started pid={result.pid}")
        print(f"[launcher] log={result.log_path}")
        print(f"[launcher] cmd={' '.join(result.command)}")
        if do_tail:
            tail_log_file(result.log_path)
        return 0
    except RezLauncherError as e:
        print(f"[launcher][error] {e}", file=sys.stderr)
        return 2
    except Exception as e:
        # 想定外も握り潰さず、最低限の情報を出して異常終了
        print(f"[launcher][fatal] {type(e).__name__}: {e}", file=sys.stderr)
        return 99


if __name__ == "__main__":
    raise SystemExit(main())
