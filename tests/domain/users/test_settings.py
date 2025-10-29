"""UserSettingsManager のユニットテスト。"""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

SRC_ROOT = Path(__file__).resolve().parents[3] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sotugyo.domain.users.settings import (  # noqa: E402
    UserSettingsManager,
    hash_password,
)
from sotugyo.infrastructure.settings import InMemorySettingsStore  # noqa: E402


@pytest.fixture()
def manager() -> UserSettingsManager:
    """インメモリストアを注入したマネージャ。"""

    store = InMemorySettingsStore()
    return UserSettingsManager(store)


def test_upsert_and_get_account(manager: UserSettingsManager) -> None:
    manager.upsert_account("alice", "Alice", "secret")

    account = manager.get_account("alice")
    assert account is not None
    assert account.display_name == "Alice"
    assert account.verify_password("secret")

    accounts = manager.list_accounts()
    assert len(accounts) == 1
    assert accounts[0].user_id == "alice"
    assert accounts[0].display_name == "Alice"


def test_upsert_without_password_uses_default_hash(manager: UserSettingsManager) -> None:
    manager.upsert_account("bob", "Bob", None)

    account = manager.get_account("bob")
    assert account is not None
    assert account.password_hash == hash_password("")

    manager.upsert_account("bob", "Bob", None)
    updated = manager.get_account("bob")
    assert updated is not None
    assert updated.password_hash == hash_password("")


def test_last_user_tracking(manager: UserSettingsManager) -> None:
    manager.upsert_account("carol", "Carol", "pass")
    manager.set_last_user_id("carol")

    assert manager.last_user_id() == "carol"

    manager.remove_account("carol")
    assert manager.last_user_id() is None
