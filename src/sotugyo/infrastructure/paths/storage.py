"""設定ファイル配置のための共通関数。"""

from __future__ import annotations

import os
from pathlib import Path

__all__ = ["get_app_config_dir"]

APP_DIR_NAME = "SotugyoTool"


def get_app_config_dir() -> Path:
    """ユーザーごとの設定ディレクトリを返す。"""

    if os.name == "nt":
        base = os.environ.get("APPDATA")
        if base:
            return Path(base) / APP_DIR_NAME
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / APP_DIR_NAME
    # POSIX 系
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        return Path(xdg_config) / APP_DIR_NAME.lower()
    return Path.home() / ".config" / APP_DIR_NAME.lower()
