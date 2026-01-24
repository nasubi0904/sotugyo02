"""ツール環境ファイルの読み取りを担当するリポジトリ。"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List, Tuple

from ....infrastructure.paths.storage import get_tool_environment_dir
from ..models import parse_environment_file_payload

LOGGER = logging.getLogger(__name__)


class ToolEnvironmentFileRepository:
    """KDMenvs 配下の環境定義ファイルを管理する。"""

    def __init__(self, root_dir: Path | None = None) -> None:
        self._root_dir = Path(root_dir) if root_dir is not None else get_tool_environment_dir()

    @property
    def root_dir(self) -> Path:
        return self._root_dir

    def list_files(self) -> List[Path]:
        if not self._root_dir.exists():
            return []
        try:
            entries = [entry for entry in self._root_dir.iterdir() if entry.is_file()]
        except OSError:
            return []
        preferred = [
            entry
            for entry in entries
            if entry.suffix.lower() in {".json", ".yml", ".yaml", ".toml"}
        ]
        return sorted(preferred or entries)

    def load_all(self) -> List[Tuple[Path, dict]]:
        payloads: List[Tuple[Path, dict]] = []
        for entry in self.list_files():
            payload = self.load(entry)
            if payload is not None:
                payloads.append((entry, payload))
        return payloads

    def load(self, path: Path) -> dict | None:
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            LOGGER.warning("環境ファイルの読み込みに失敗しました: %s", path, exc_info=True)
            return None
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            LOGGER.warning("環境ファイルの解析に失敗しました: %s", path, exc_info=True)
            return None
        payload = parse_environment_file_payload(data)
        if payload is None:
            LOGGER.warning("環境ファイルの形式が不正です: %s", path)
            return None
        return payload
