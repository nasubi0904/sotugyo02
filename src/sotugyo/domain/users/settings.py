"""ユーザーアカウントを管理するためのユーティリティ。"""

from __future__ import annotations

import hashlib
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator, List, Optional

from ...infrastructure.settings import SettingsStore, create_settings_store

__all__ = ["UserAccount", "UserSettingsManager", "hash_password"]


@dataclass(slots=True)
class UserAccount:
    """永続化されたユーザー情報。"""

    user_id: str
    display_name: str
    password_hash: str

    def verify_password(self, password: str) -> bool:
        """平文パスワードと保存済みハッシュを比較する。"""

        return self.password_hash == hash_password(password)


def hash_password(password: str) -> str:
    """SHA-256 を用いてパスワードハッシュを生成する。"""

    digest = hashlib.sha256()
    digest.update(password.encode("utf-8"))
    return digest.hexdigest()


@contextmanager
def _settings_group(store: SettingsStore, name: str) -> Iterator[None]:
    """`SettingsStore` の `begin_group`/`end_group` を安全に扱う。"""

    store.begin_group(name)
    try:
        yield
    finally:
        store.end_group()


class UserSettingsManager:
    """設定ストアを介してユーザー情報を永続化する。"""

    def __init__(self, store: Optional[SettingsStore] = None) -> None:
        self._store: SettingsStore = store or create_settings_store(
            "Sotugyo", "UserSettings"
        )

    # 読み込み ----------------------------------------------------------
    def list_accounts(self) -> List[UserAccount]:
        accounts: List[UserAccount] = []
        with _settings_group(self._store, "users"):
            for user_id in self._store.child_groups():
                with _settings_group(self._store, user_id):
                    display_name = self._store.value("display_name", user_id)
                    password_hash = self._store.value("password_hash", "")
                if not isinstance(display_name, str) or not isinstance(
                    password_hash, str
                ):
                    continue
                accounts.append(
                    UserAccount(
                        user_id=user_id,
                        display_name=display_name,
                        password_hash=password_hash,
                    )
                )
        return accounts

    def get_account(self, user_id: str) -> Optional[UserAccount]:
        with _settings_group(self._store, "users"):
            with _settings_group(self._store, user_id):
                display_name = self._store.value("display_name")
                password_hash = self._store.value("password_hash")
        if isinstance(display_name, str) and isinstance(password_hash, str):
            return UserAccount(
                user_id=user_id,
                display_name=display_name,
                password_hash=password_hash,
            )
        return None

    def last_user_id(self) -> Optional[str]:
        value = self._store.value("last_user_id")
        return value if isinstance(value, str) else None

    # 更新 --------------------------------------------------------------
    def set_last_user_id(self, user_id: Optional[str]) -> None:
        if user_id is None:
            self._store.remove("last_user_id")
        else:
            self._store.set_value("last_user_id", user_id)
        self._store.sync()

    def upsert_account(
        self, user_id: str, display_name: str, password: Optional[str]
    ) -> None:
        with _settings_group(self._store, "users"):
            with _settings_group(self._store, user_id):
                self._store.set_value("display_name", display_name)
                if password:
                    self._store.set_value(
                        "password_hash", hash_password(password)
                    )
                elif not self._store.contains("password_hash"):
                    self._store.set_value(
                        "password_hash", hash_password("")
                    )
        self._store.sync()

    def remove_account(self, user_id: str) -> None:
        with _settings_group(self._store, "users"):
            self._store.remove(user_id)
        if self.last_user_id() == user_id:
            self.set_last_user_id(None)
        self._store.sync()
