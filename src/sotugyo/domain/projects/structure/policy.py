"""プロジェクト構造ポリシー。"""

from __future__ import annotations

from typing import Dict, List

__all__ = ["DEFAULT_DIRECTORIES", "DEFAULT_FILES", "DEFAULT_FILE_CONTENT"]

# プロジェクトルート配下に必須となるディレクトリとファイル
DEFAULT_DIRECTORIES: List[str] = [
    "assets",
    "assets/source",
    "assets/published",
    "renders",
    "reviews",
    "config",
    "config/rez_packages",
]
DEFAULT_FILES: List[str] = [
    "config/project_settings.json",
    "config/node_graph.json",
]
DEFAULT_FILE_CONTENT: Dict[str, str] = {
    "config/project_settings.json": "{}\n",
    "config/node_graph.json": "{\n  \"nodes\": [],\n  \"connections\": []\n}\n",
}
