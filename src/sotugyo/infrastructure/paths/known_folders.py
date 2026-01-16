"""Windows Known Folder API 由来のパスユーティリティ。"""

from __future__ import annotations

import ctypes
import functools
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ctypes import wintypes


@dataclass(frozen=True)
class KnownFolderReference:
    """Known Folder で相対化したパス情報。"""

    folder_id: str
    relative_path: str


_KNOWN_FOLDER_IDS = (
    "B4BFCC3A-DB2C-424C-B029-7FE99A87C641",  # Desktop
    "FDD39AD0-238F-46AF-ADB4-6C85480369C7",  # Documents
    "374DE290-123F-4565-9164-39C4925E467B",  # Downloads
    "3EB685DB-65F9-4CF6-A03A-E3EF65729F3D",  # AppData (Roaming)
    "F1B32785-6FBA-4FCF-9D55-7B8E7F157091",  # LocalAppData
    "905E63B6-C1BF-494E-B29C-65B732D3D21A",  # ProgramFiles
    "7C5A40EF-A0FB-4BFC-874A-C0F2E0B9FA8E",  # ProgramFilesX86
)


class _Guid(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", wintypes.BYTE * 8),
    ]


def _guid_from_str(value: str) -> _Guid:
    guid = uuid.UUID(value)
    return _Guid.from_buffer_copy(guid.bytes_le)


def _resolve_known_folder_path(folder_id: str) -> Optional[Path]:
    if os.name != "nt":
        return None

    path_ptr = ctypes.c_wchar_p()
    shell32 = ctypes.windll.shell32
    shell32.SHGetKnownFolderPath.argtypes = [
        ctypes.POINTER(_Guid),
        wintypes.DWORD,
        wintypes.HANDLE,
        ctypes.POINTER(ctypes.c_wchar_p),
    ]
    shell32.SHGetKnownFolderPath.restype = wintypes.HRESULT
    ole32 = ctypes.windll.ole32
    ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
    ole32.CoTaskMemFree.restype = None

    folder_guid = _guid_from_str(folder_id)
    result = shell32.SHGetKnownFolderPath(ctypes.byref(folder_guid), 0, None, ctypes.byref(path_ptr))
    if result != 0 or not path_ptr.value:
        return None
    try:
        return Path(path_ptr.value)
    finally:
        ole32.CoTaskMemFree(path_ptr)


@functools.lru_cache(maxsize=1)
def _known_folder_paths() -> tuple[tuple[str, Path], ...]:
    if os.name != "nt":
        return tuple()

    resolved: list[tuple[str, Path]] = []
    for folder_id in _KNOWN_FOLDER_IDS:
        folder_path = _resolve_known_folder_path(folder_id)
        if folder_path is None:
            continue
        resolved.append((folder_id, folder_path))
    return tuple(resolved)


def resolve_known_folder_reference(path: Path) -> Optional[KnownFolderReference]:
    """既知フォルダで相対化できる場合は参照情報を返す。"""

    if os.name != "nt":
        return None

    resolved_path = path.resolve(strict=False)
    for folder_id, folder_path in _known_folder_paths():
        try:
            relative = resolved_path.relative_to(folder_path)
        except ValueError:
            continue
        relative_path = relative.as_posix()
        if relative_path == ".":
            relative_path = ""
        return KnownFolderReference(folder_id=folder_id, relative_path=relative_path)
    return None
