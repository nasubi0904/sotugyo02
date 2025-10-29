#!/usr/bin/env python3
"""プロジェクト依存関係のセットアップ用ユーティリティ。"""
from __future__ import annotations

import subprocess
import sys
from typing import List, Sequence, Tuple

Dependency = Tuple[str, str]

# pip list で確認済みの必須依存関係とバージョン固定
DEPENDENCIES: Sequence[Dependency] = (
    ("PySide6", "6.10.0"),
    ("PySide6-Addons", "6.10.0"),
    ("PySide6-Essentials", "6.10.0"),
    ("shiboken6", "6.10.0"),
    ("NodeGraphQt", "0.6.43"),
    ("OdenGraphQt", "0.7.4"),
    ("Qt.py", "1.4.8"),
    ("QtPy", "2.4.3"),
    ("types-pyside2", "5.15.2.1.7"),
    ("typing_extensions", "4.15.0"),
)


def build_install_arguments(dependencies: Sequence[Dependency]) -> List[str]:
    """pip に渡すインストール引数リストを生成する。"""
    return [f"{name}=={version}" for name, version in dependencies]


def install_dependencies() -> None:
    """定義済み依存関係を pip でインストールする。"""
    args = [sys.executable, "-m", "pip", "install", "--upgrade"]
    args.extend(build_install_arguments(DEPENDENCIES))
    subprocess.check_call(args)


if __name__ == "__main__":
    install_dependencies()
