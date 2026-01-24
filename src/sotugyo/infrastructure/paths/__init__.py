"""設定ファイルの保存先など、パス関連のユーティリティ。"""

from __future__ import annotations

from .file_node_paths import (
    FILE_NODE_DIR_SCHEME,
    FILE_NODE_SCHEME,
    FileNodePathSpec,
    encode_file_node_path,
    encode_structured_file_node_path,
    parse_file_node_path,
)
from .project_paths import (
    PROJECT_PATH_SCHEME,
    ProjectPathSpec,
    encode_project_relative_path,
    encode_structured_absolute_path,
    encode_structured_project_path,
    is_project_relative_path,
    normalize_project_relative_path,
    parse_project_path,
    resolve_project_relative_path,
    safe_basename,
)
from .storage import get_app_config_dir, get_machine_config_dir

__all__ = [
    "FILE_NODE_DIR_SCHEME",
    "FILE_NODE_SCHEME",
    "FileNodePathSpec",
    "PROJECT_PATH_SCHEME",
    "ProjectPathSpec",
    "encode_file_node_path",
    "encode_project_relative_path",
    "encode_structured_absolute_path",
    "encode_structured_file_node_path",
    "encode_structured_project_path",
    "get_app_config_dir",
    "get_machine_config_dir",
    "is_project_relative_path",
    "normalize_project_relative_path",
    "parse_file_node_path",
    "parse_project_path",
    "resolve_project_relative_path",
    "safe_basename",
]
