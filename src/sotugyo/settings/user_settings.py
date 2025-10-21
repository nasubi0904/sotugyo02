"""ユーザーアカウントを管理するためのユーティリティ。"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import List, Optional

from PySide6.QtCore import QSettings

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
