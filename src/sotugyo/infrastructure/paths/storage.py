"""設定ファイル配置のための共通関数。"""

from __future__ import annotations

import os
from pathlib import Path

__all__ = [
    "get_app_config_dir",
    "get_machine_config_dir",
    "get_rez_package_dir",
    "get_tool_environment_dir",
]

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


def get_machine_config_dir() -> Path:
    """マシン共通の設定ディレクトリを返す。"""

    override = os.environ.get("SOTUGYO_MACHINE_CONFIG_DIR")
    if override:
        return Path(override)

    if os.name == "nt":
        for env_var in ("PROGRAMDATA", "ALLUSERSPROFILE"):
            base = os.environ.get(env_var)
            if base:
                return Path(base) / APP_DIR_NAME
        return Path("C:/ProgramData") / APP_DIR_NAME

    user_dir = get_app_config_dir()
    return user_dir.parent / f"{APP_DIR_NAME.lower()}-machine"


def get_rez_package_dir() -> Path:
    """Rez パッケージの保存先ディレクトリを返す。"""

    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / "KDMrez"
        return Path.home() / "AppData" / "Local" / "KDMrez"

    xdg_data = os.environ.get("XDG_DATA_HOME")
    if xdg_data:
        return Path(xdg_data) / "kdmrez"
    return Path.home() / ".local" / "share" / "kdmrez"


def get_tool_environment_dir() -> Path:
    """ツール環境定義の保存先ディレクトリを返す。"""

    rez_dir = get_rez_package_dir()
    env_dir_name = "KDMenvs" if rez_dir.name == "KDMrez" else "kdmenvs"
    return rez_dir.parent / env_dir_name
