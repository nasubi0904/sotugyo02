"""プロジェクトレジストリ操作の責務を分離したサービス。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from .models import ProjectRecord
from .store import ProjectRegistry


@dataclass(slots=True)
class ProjectRegistryService:
    """プロジェクトレジストリの永続化操作を担当する。"""

    registry: ProjectRegistry

    def records(self) -> list[ProjectRecord]:
        """現在登録されているプロジェクト一覧を返す。"""

        return self.registry.records()

    def last_project(self) -> Optional[Path]:
        """最後に選択されたプロジェクトルートを返す。"""

        return self.registry.last_project()

    def register(self, record: ProjectRecord, *, set_last: bool = False) -> None:
        """プロジェクトを登録し、必要に応じて最終選択を更新する。"""

        self.registry.register_project(record)
        if set_last:
            self.registry.set_last_project(record.root)

    def register_many(self, records: Iterable[ProjectRecord]) -> None:
        """複数のレコードを登録する。"""

        for record in records:
            self.registry.register_project(record)

    def remove(self, root: Path) -> None:
        """指定ルートのプロジェクト登録を解除する。"""

        self.registry.remove_project(root)

    def set_last(self, root: Path) -> None:
        """最後に選択したプロジェクトルートを更新する。"""

        self.registry.set_last_project(root)
