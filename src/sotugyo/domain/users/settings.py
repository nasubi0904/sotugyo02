"""ユーザーアカウントを管理するためのユーティリティ。"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import List, Optional, TYPE_CHECKING

try:
    from qtpy import QtCore
except Exception:  # pragma: no cover - Qt バインディングが無い環境向けフォールバック
    QtCore = None  # type: ignore[assignment]
    if TYPE_CHECKING:  # pragma: no cover - 型チェック専用
        from qtpy import QtCore as _QtCore  # noqa: F401
else:
    QSettings = QtCore.QSettings


if QtCore is None:
    class QSettings:  # type: ignore[override]
        """QtPy が利用できない環境向けの簡易 QSettings 代替。"""

        def __init__(self, *args, **kwargs) -> None:
            self._store: dict[str, object] = {}
            self._group_stack: list[str] = []

        # グループ操作 --------------------------------------------------
        def beginGroup(self, prefix: str) -> None:
            self._ensure_group(prefix)
            self._group_stack.append(prefix)

        def endGroup(self) -> None:
            if self._group_stack:
                self._group_stack.pop()

        def childGroups(self) -> list[str]:
            current = self._resolve_group(create=False)
            return [
                key
                for key, value in current.items()
                if isinstance(value, dict)
            ]

        # 値アクセス ----------------------------------------------------
        def value(self, key: str, default: object | None = None) -> object | None:
            current = self._resolve_group(create=False)
            return current.get(key, default)

        def setValue(self, key: str, value: object) -> None:
            current = self._resolve_group(create=True)
            current[key] = value

        def contains(self, key: str) -> bool:
            current = self._resolve_group(create=False)
            return key in current

        def remove(self, key: str) -> None:
            current = self._resolve_group(create=False)
            current.pop(key, None)

        def sync(self) -> None:
            return

        # 内部ユーティリティ ------------------------------------------
        def _resolve_group(self, *, create: bool) -> dict[str, object]:
            group = self._store
            for name in self._group_stack:
                next_group = group.get(name)
                if not isinstance(next_group, dict):
                    if not create:
                        next_group = {}
                    else:
                        next_group = {}
                        group[name] = next_group
                group = next_group
            return group

        def _ensure_group(self, name: str) -> None:
            group = self._resolve_group(create=True)
            if name not in group or not isinstance(group[name], dict):
                group[name] = {}

__all__ = ["UserAccount", "UserSettingsManager", "hash_password"]


@dataclass
class UserAccount:
    user_id: str
    display_name: str
    password_hash: str

    def verify_password(self, password: str) -> bool:
        return self.password_hash == hash_password(password)


def hash_password(password: str) -> str:
    digest = hashlib.sha256()
    digest.update(password.encode("utf-8"))
    return digest.hexdigest()


class UserSettingsManager:
    """QSettings を用いてユーザー情報を永続化する。"""

    def __init__(self) -> None:
        self._settings = QSettings("Sotugyo", "UserSettings")

    # 読み込み ----------------------------------------------------------
    def list_accounts(self) -> List[UserAccount]:
        accounts: List[UserAccount] = []
        self._settings.beginGroup("users")
        for user_id in self._settings.childGroups():
            self._settings.beginGroup(user_id)
            display_name = self._settings.value("display_name", user_id)
            password_hash = self._settings.value("password_hash", "")
            self._settings.endGroup()
            if not isinstance(display_name, str) or not isinstance(password_hash, str):
                continue
            accounts.append(
                UserAccount(user_id=user_id, display_name=display_name, password_hash=password_hash)
            )
        self._settings.endGroup()
        return accounts

    def get_account(self, user_id: str) -> Optional[UserAccount]:
        self._settings.beginGroup("users")
        self._settings.beginGroup(user_id)
        display_name = self._settings.value("display_name")
        password_hash = self._settings.value("password_hash")
        self._settings.endGroup()
        self._settings.endGroup()
        if isinstance(display_name, str) and isinstance(password_hash, str):
            return UserAccount(user_id=user_id, display_name=display_name, password_hash=password_hash)
        return None

    def last_user_id(self) -> Optional[str]:
        value = self._settings.value("last_user_id")
        return value if isinstance(value, str) else None

    # 更新 --------------------------------------------------------------
    def set_last_user_id(self, user_id: Optional[str]) -> None:
        if user_id is None:
            self._settings.remove("last_user_id")
        else:
            self._settings.setValue("last_user_id", user_id)
        self._settings.sync()

    def upsert_account(self, user_id: str, display_name: str, password: Optional[str]) -> None:
        self._settings.beginGroup("users")
        self._settings.beginGroup(user_id)
        self._settings.setValue("display_name", display_name)
        if password:
            self._settings.setValue("password_hash", hash_password(password))
        elif not self._settings.contains("password_hash"):
            self._settings.setValue("password_hash", hash_password(""))
        self._settings.endGroup()
        self._settings.endGroup()
        self._settings.sync()

    def remove_account(self, user_id: str) -> None:
        self._settings.beginGroup("users")
        self._settings.remove(user_id)
        self._settings.endGroup()
        if self.last_user_id() == user_id:
            self.set_last_user_id(None)
        self._settings.sync()
