"""設定ファイル配置のための共通関数。"""

from __future__ import annotations

import ctypes
import os
import uuid
from pathlib import Path
from ctypes import wintypes

__all__ = [
    "get_app_config_dir",
    "get_machine_config_dir",
    "get_rez_package_dir",
    "get_tool_environment_dir",
]

APP_DIR_NAME = "SotugyoTool"
_FOLDERID_LOCAL_APPDATA = "F1B32785-6FBA-4FCF-9D55-7B8E7F157091"


class _Guid(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", wintypes.BYTE * 8),
    ]


def _guid_from_string(value: str) -> _Guid:
    parsed = uuid.UUID(value)
    data4 = (wintypes.BYTE * 8)()
    data4[0] = parsed.clock_seq_hi_variant
    data4[1] = parsed.clock_seq_low
    node_bytes = parsed.node.to_bytes(6, "big")
    for index, byte in enumerate(node_bytes, start=2):
        data4[index] = byte
    return _Guid(
        parsed.time_low,
        parsed.time_mid,
        parsed.time_hi_version,
        data4,
    )


def _get_windows_known_folder_path(folder_id: str) -> Path | None:
    if os.name != "nt":
        return None

    path_ptr = wintypes.LPWSTR()
    try:
        folder_guid = _guid_from_string(folder_id)
        shell32 = ctypes.windll.shell32
        shell32.SHGetKnownFolderPath.argtypes = [
            ctypes.POINTER(_Guid),
            wintypes.DWORD,
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.LPWSTR),
        ]
        shell32.SHGetKnownFolderPath.restype = wintypes.HRESULT
        result = shell32.SHGetKnownFolderPath(
            ctypes.byref(folder_guid),
            0,
            None,
            ctypes.byref(path_ptr),
        )
        if result != 0:
            return None
        return Path(path_ptr)
    except Exception:
        return None
    finally:
        try:
            if path_ptr:
                ctypes.windll.ole32.CoTaskMemFree(path_ptr)
        except Exception:
            pass


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
        known_base = _get_windows_known_folder_path(_FOLDERID_LOCAL_APPDATA)
        if known_base:
            return known_base / "KDMrez"
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / "KDMrez"
        base = os.environ.get("APPDATA")
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
