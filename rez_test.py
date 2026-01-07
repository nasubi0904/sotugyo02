# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import datetime as _dt
import locale
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional


# =========================
# 設定（default）
# =========================
DEFAULT_PKG = "adobe_after_effects-2025"
DEFAULT_TOOL_CMD = ["AfterFX"]
DEFAULT_REZ_ENV_EXE = ""  # 空なら自動検出
DEFAULT_LOG_DIR = ""      # 空なら %TEMP% 配下に作る
DEFAULT_TAIL = True       # 親が生きている間だけログ監視する


# =========================
# encoding helpers
# =========================
def _preferred_text_encoding() -> str:
    return locale.getpreferredencoding(False) or "utf-8"


# =========================
# rez helpers
# =========================
def find_rez_env_exe(explicit: str = "") -> str:
    if explicit:
        p = Path(explicit)
        if p.exists():
            return str(p)

    w = shutil.which("rez-env")
    if w:
        return w

    py = Path(sys.executable)
    candidates = [
        py.parent / "rez-env.exe",
        py.parent / "Scripts" / "rez-env.exe",
    ]
    for c in candidates:
        if c.exists():
            return str(c)

    raise FileNotFoundError("rez-env が見つかりません（PATH または Python 環境の Scripts を確認してください）。")


def ensure_rez_packages_path_add_kdmrez() -> Path:
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    kdmrez = Path(local_appdata) / "KDMrez" if local_appdata else (Path.home() / "AppData" / "Local" / "KDMrez")

    current = os.environ.get("REZ_PACKAGES_PATH", "")
    parts = [p for p in current.split(";") if p] if current else []
    lowered = {p.lower() for p in parts}

    ks = str(kdmrez)
    if ks.lower() not in lowered:
        parts.insert(0, ks)
        os.environ["REZ_PACKAGES_PATH"] = ";".join(parts)

    return kdmrez


def build_rez_command(rez_env_exe: str, package_request: str, tool_and_args: List[str]) -> List[str]:
    if not tool_and_args:
        raise ValueError("起動したいコマンドが空です。")
    return [rez_env_exe, package_request, "--", *tool_and_args]


# =========================
# detached launch
# =========================
def launch_detached_with_log(cmd: list[str], log_file: Path) -> int:
    """
    親が落ちても子が落ちないように “独立起動” しつつ、
    空の cmd 窓が出ないようにコンソールを抑止して起動する版。

    stdout/stderr はログファイルへ出力（親が落ちても残る）。
    """
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Windows: コンソール窓を出さない/新しいプロセスグループで独立性を上げる
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    CREATE_NO_WINDOW = 0x08000000

    # 念押しでウィンドウ非表示（コンソールアプリに効く）
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0  # SW_HIDE

    with log_file.open("a", encoding="utf-8", errors="replace") as f:
        p = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=f,
            stderr=subprocess.STDOUT,
            creationflags=CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW,
            startupinfo=si,
            close_fds=True,
            env=os.environ.copy(),
        )
        return p.pid



def tail_file(path: Path, poll_sec: float = 0.2) -> None:
    """
    ログファイルを簡易 tail する（親が生きている間だけ）。
    """
    enc = "utf-8"
    # まだ作られていない可能性があるので少し待つ
    for _ in range(50):
        if path.exists():
            break
        time.sleep(poll_sec)

    if not path.exists():
        return

    with path.open("r", encoding=enc, errors="replace") as f:
        # 末尾から追いたい場合はここを調整可能（今回は先頭から）
        while True:
            line = f.readline()
            if line:
                print(line, end="")
                continue
            time.sleep(poll_sec)


# =========================
# main
# =========================
def _normalize_tool_args(tool_args: List[str]) -> List[str]:
    if tool_args and tool_args[0] == "--":
        return tool_args[1:]
    return tool_args


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rez-env", default=DEFAULT_REZ_ENV_EXE, help="rez-env 実行ファイル（空なら自動検出）")
    ap.add_argument("--pkg", default=DEFAULT_PKG, help="Rez パッケージ要求")
    ap.add_argument("--logdir", default=DEFAULT_LOG_DIR, help="ログ出力ディレクトリ（空なら %TEMP% ）")
    ap.add_argument("--tail", action="store_true", default=DEFAULT_TAIL, help="起動後にログを監視する（親が生存中のみ）")
    ap.add_argument("tool_args", nargs=argparse.REMAINDER, help="`--` の後ろに起動コマンドと引数")

    args = ap.parse_args()

    tool_args = _normalize_tool_args(args.tool_args)
    if not tool_args:
        tool_args = list(DEFAULT_TOOL_CMD)

    # Rez パス自動追加
    kdmrez = ensure_rez_packages_path_add_kdmrez()
    print(f"[launcher] REZ_PACKAGES_PATH ensured: {kdmrez}")

    rez_env_exe = find_rez_env_exe(args.rez_env)

    rez_cmd = build_rez_command(rez_env_exe, args.pkg, tool_args)

    # ログファイル決定（親が死んでも残る）
    ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    logdir = Path(args.logdir) if args.logdir else Path(os.environ.get("TEMP", ".")) / "rez_detached_logs"
    log_file = logdir / f"{args.pkg}__{'_'.join(tool_args[:1])}__{ts}.log"

    print("[launcher] rez-env resolved:", rez_env_exe)
    print("[launcher] detached launch:", " ".join(rez_cmd))
    print("[launcher] log file:", str(log_file))

    pid = launch_detached_with_log(rez_cmd, log_file)
    print(f"[launcher] started (detached) pid={pid}")

    # 親が生きている間だけログ監視（親が落ちた後は当然止まるが、ログは残る）
    if args.tail:
        tail_file(log_file)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
