"""設定ストアの実装と抽象。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, MutableMapping, Optional, Protocol, cast


class SettingsStore(Protocol):
    """設定ストアに必要な最小インターフェース。"""

    def begin_group(self, prefix: str) -> None:
        """設定グループのネームスペースへ移動する。"""

    def end_group(self) -> None:
        """現在の設定グループを終了する。"""

    def child_groups(self) -> List[str]:
        """現在のグループ直下のサブグループ一覧を返す。"""

    def value(self, key: str, default: object | None = None) -> object | None:
        """キーに紐づく値を取得する。"""

    def set_value(self, key: str, value: object) -> None:
        """キーへ値を書き込む。"""

    def contains(self, key: str) -> bool:
        """キーが存在するかを返す。"""

    def remove(self, key: str) -> None:
        """キーまたはグループを削除する。"""

    def sync(self) -> None:
        """ストアへ変更を確定する。"""


@dataclass(slots=True)
class InMemorySettingsStore:
    """Qt へ依存しないインメモリ設定ストア。"""

    _store: MutableMapping[str, Any]
    _group_stack: List[str]

    def __init__(self) -> None:
        self._store = {}
        self._group_stack = []

    # グループ操作 -----------------------------------------------------
    def begin_group(self, prefix: str) -> None:
        self._ensure_group(prefix)
        self._group_stack.append(prefix)

    def end_group(self) -> None:
        if self._group_stack:
            self._group_stack.pop()

    def child_groups(self) -> List[str]:
        current = self._resolve_group(create=False)
        return [name for name, value in current.items() if isinstance(value, dict)]

    # 値アクセス -------------------------------------------------------
    def value(self, key: str, default: object | None = None) -> object | None:
        current = self._resolve_group(create=False)
        return current.get(key, default)

    def set_value(self, key: str, value: object) -> None:
        current = self._resolve_group(create=True)
        current[key] = value

    def contains(self, key: str) -> bool:
        current = self._resolve_group(create=False)
        return key in current

    def remove(self, key: str) -> None:
        current = self._resolve_group(create=False)
        current.pop(key, None)

    def sync(self) -> None:
        # インメモリ実装では同期処理は不要。
        return None

    # 内部ユーティリティ ---------------------------------------------
    def _resolve_group(self, *, create: bool) -> MutableMapping[str, Any]:
        group: MutableMapping[str, Any] = self._store
        for name in self._group_stack:
            next_group = group.get(name)
            if not isinstance(next_group, MutableMapping):
                if not create:
                    return {}
                next_group = {}
                group[name] = next_group
            group = next_group
        return cast(MutableMapping[str, Any], group)

    def _ensure_group(self, name: str) -> None:
        group = self._resolve_group(create=True)
        if name not in group or not isinstance(group[name], MutableMapping):
            group[name] = {}


@dataclass(slots=True)
class QtSettingsStore:
    """Qt の :class:`QSettings` をラップしたストア。"""

    _settings: Any

    def begin_group(self, prefix: str) -> None:
        self._settings.beginGroup(prefix)

    def end_group(self) -> None:
        self._settings.endGroup()

    def child_groups(self) -> List[str]:
        return list(self._settings.childGroups())

    def value(self, key: str, default: object | None = None) -> object | None:
        return self._settings.value(key, default)

    def set_value(self, key: str, value: object) -> None:
        self._settings.setValue(key, value)

    def contains(self, key: str) -> bool:
        return bool(self._settings.contains(key))

    def remove(self, key: str) -> None:
        self._settings.remove(key)

    def sync(self) -> None:
        self._settings.sync()


def _load_qsettings_class() -> Optional[type[Any]]:
    """QtPy から ``QSettings`` を遅延インポートする。"""

    try:
        from qtpy import QtCore
    except Exception:  # pragma: no cover - QtPy が利用できない環境向け
        return None
    qsettings = getattr(QtCore, "QSettings", None)
    if qsettings is None:
        return None
    return qsettings


def create_settings_store(organization: str, application: str) -> SettingsStore:
    """利用可能なバックエンドに応じて設定ストアを生成する。"""

    qsettings_cls = _load_qsettings_class()
    if qsettings_cls is None:
        return InMemorySettingsStore()
    settings = qsettings_cls(organization, application)
    return QtSettingsStore(settings)


__all__ = [
    "InMemorySettingsStore",
    "QtSettingsStore",
    "SettingsStore",
    "create_settings_store",
]
