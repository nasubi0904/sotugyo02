"""ツール起動環境の構成ダイアログ。"""

from __future__ import annotations

import json
import os
import re
import uuid
import ctypes
from datetime import datetime
from pathlib import Path
from typing import Optional

from qtpy import QtCore, QtWidgets

Qt = QtCore.Qt
QDialog = QtWidgets.QDialog
QDialogButtonBox = QtWidgets.QDialogButtonBox
QFormLayout = QtWidgets.QFormLayout
QHBoxLayout = QtWidgets.QHBoxLayout
QCheckBox = QtWidgets.QCheckBox
QLabel = QtWidgets.QLabel
QLineEdit = QtWidgets.QLineEdit
QListWidget = QtWidgets.QListWidget
QListWidgetItem = QtWidgets.QListWidgetItem
QPlainTextEdit = QtWidgets.QPlainTextEdit
QPushButton = QtWidgets.QPushButton
QComboBox = QtWidgets.QComboBox
QVBoxLayout = QtWidgets.QVBoxLayout
QWidget = QtWidgets.QWidget
QFileDialog = QtWidgets.QFileDialog
QMessageBox = QtWidgets.QMessageBox
QInputDialog = QtWidgets.QInputDialog

from ...domain.tooling.models import RezPackageSpec
from ...domain.tooling import ToolEnvironmentService
from ...domain.tooling.payloads import (
    collect_input_token_names,
    contains_input_token,
    normalize_input_name,
    normalize_input_plugs,
)
from ...infrastructure.paths.storage import get_tool_environment_dir


class ToolEnvironmentManagerDialog(QDialog):
    """ツール起動環境の構成を行うダイアログ。"""

    def __init__(self, service: ToolEnvironmentService, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._service = service
        self._refresh_on_accept = False
        self._environment_dir = get_tool_environment_dir()
        self._environment_items: list[Path] = []

        self.setWindowTitle("ツール起動環境の構成")
        self.resize(760, 520)

        self._build_ui()
        self._load_environment_list()

    def refresh_requested(self) -> bool:
        return self._refresh_on_accept

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        description = QLabel(
            "ツールパッケージをもとに起動環境を構成し、KDMenvs に保存された環境を一覧します。",
            self,
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        list_label = QLabel("現在参照可能な環境 (KDMenvs)", self)
        layout.addWidget(list_label)

        self._environment_list = QListWidget(self)
        self._environment_list.itemSelectionChanged.connect(self._update_edit_state)
        layout.addWidget(self._environment_list, 1)

        action_layout = QHBoxLayout()
        self._add_button = QPushButton("追加", self)
        self._add_button.clicked.connect(self._open_add_dialog)
        action_layout.addWidget(self._add_button)

        self._edit_button = QPushButton("編集", self)
        self._edit_button.setEnabled(False)
        self._edit_button.clicked.connect(self._open_edit_dialog)
        action_layout.addWidget(self._edit_button)
        action_layout.addStretch(1)
        layout.addLayout(action_layout)

        buttons = QDialogButtonBox(QDialogButtonBox.Close, Qt.Horizontal, self)
        buttons.rejected.connect(self._handle_close)
        layout.addWidget(buttons)

    def _load_environment_list(self) -> None:
        self._environment_dir.mkdir(parents=True, exist_ok=True)
        self._environment_list.clear()
        self._environment_items.clear()

        files = self._collect_environment_files(self._environment_dir)
        if not files:
            placeholder = QListWidgetItem("環境がありません", self._environment_list)
            placeholder.setFlags(Qt.NoItemFlags)
            self._update_edit_state()
            return

        for entry in files:
            display_name = self._display_name_from_environment_file(entry)
            item = QListWidgetItem(display_name, self._environment_list)
            item.setData(Qt.UserRole, entry)
            self._environment_items.append(entry)
        self._environment_list.setCurrentRow(0)
        self._update_edit_state()

    @staticmethod
    def _collect_environment_files(root: Path) -> list[Path]:
        if not root.exists():
            return []
        try:
            entries = [entry for entry in root.iterdir() if entry.is_file()]
        except OSError:
            return []
        preferred = [
            entry
            for entry in entries
            if entry.suffix.lower() in {".json", ".yml", ".yaml", ".toml"}
        ]
        return sorted(preferred or entries)

    def _selected_environment_path(self) -> Optional[Path]:
        selected = self._environment_list.currentItem()
        if selected is None:
            return None
        data = selected.data(Qt.UserRole)
        if isinstance(data, Path):
            return data
        return None

    @staticmethod
    def _display_name_from_environment_file(path: Path) -> str:
        if path.suffix.lower() != ".json":
            return path.stem
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            return path.stem
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            return path.stem
        if isinstance(payload, dict):
            name = payload.get("name")
            if isinstance(name, str) and name.strip():
                return name.strip()
        return path.stem

    def _update_edit_state(self) -> None:
        self._edit_button.setEnabled(self._selected_environment_path() is not None)

    def _open_add_dialog(self) -> None:
        dialog = ToolEnvironmentEditorDialog(
            service=self._service,
            environment_dir=self._environment_dir,
            environment_path=None,
            parent=self,
        )
        dialog.exec()
        if dialog.refresh_requested():
            self._refresh_on_accept = True
            self._load_environment_list()

    def _open_edit_dialog(self) -> None:
        path = self._selected_environment_path()
        if path is None:
            return
        dialog = ToolEnvironmentEditorDialog(
            service=self._service,
            environment_dir=self._environment_dir,
            environment_path=path,
            parent=self,
        )
        dialog.exec()
        if dialog.refresh_requested():
            self._refresh_on_accept = True
            self._load_environment_list()

    def _handle_close(self) -> None:
        if self._refresh_on_accept:
            self.accept()
            return
        self.reject()


class ToolEnvironmentEditorDialog(QDialog):
    """ツール環境定義の編集ダイアログ。"""

    def __init__(
        self,
        *,
        service: ToolEnvironmentService,
        environment_dir: Path,
        environment_path: Optional[Path],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._environment_dir = environment_dir
        self._environment_path = environment_path
        self._environment_id: Optional[str] = None
        self._created_at: Optional[str] = None
        self._refresh_requested = False
        self._required_plugins: list[dict[str, str]] = []
        self._input_plugs: list[dict[str, str]] = []
        self._package_py_cache: dict[Path, str] = {}
        self._known_folders_cache: Optional[list[tuple[str, Path]]] = None

        self.setWindowTitle("ツール環境の編集")
        self.resize(640, 480)

        self._build_ui()
        self._populate_packages()
        self._load_existing()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        description = QLabel(
            "ツールパッケージを選び、環境変数と起動引数を手動で定義します。",
            self,
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)

        self._name_edit = QLineEdit(self)
        self._name_edit.setPlaceholderText("例: sRGB 環境")
        form.addRow("環境名", self._name_edit)

        self._package_combo = QComboBox(self)
        form.addRow("ツールパッケージ", self._package_combo)

        layout.addLayout(form)

        input_label = QLabel("入力プラグの設定", self)
        layout.addWidget(input_label)

        input_layout = QHBoxLayout()
        self._input_list = QListWidget(self)
        self._input_list.itemSelectionChanged.connect(self._update_input_buttons)
        input_layout.addWidget(self._input_list, 1)

        input_button_layout = QVBoxLayout()
        self._input_add_button = QPushButton("入力を追加", self)
        self._input_add_button.clicked.connect(self._add_input_plug)
        input_button_layout.addWidget(self._input_add_button)
        self._input_remove_button = QPushButton("入力を削除", self)
        self._input_remove_button.setEnabled(False)
        self._input_remove_button.clicked.connect(self._remove_selected_inputs)
        input_button_layout.addWidget(self._input_remove_button)
        input_button_layout.addStretch(1)
        input_layout.addLayout(input_button_layout)
        layout.addLayout(input_layout)

        plugin_label = QLabel("要求ファイルの設定 (Plugin,module,etc...)", self)
        layout.addWidget(plugin_label)

        plugin_layout = QHBoxLayout()
        self._plugin_list = QListWidget(self)
        self._plugin_list.itemSelectionChanged.connect(self._update_plugin_buttons)
        plugin_layout.addWidget(self._plugin_list, 1)

        plugin_button_layout = QVBoxLayout()
        self._plugin_add_button = QPushButton("追加", self)
        self._plugin_add_button.clicked.connect(self._open_plugin_dialog)
        plugin_button_layout.addWidget(self._plugin_add_button)
        self._plugin_add_input_button = QPushButton("ノード入力を追加", self)
        self._plugin_add_input_button.clicked.connect(self._add_input_required_plugin)
        plugin_button_layout.addWidget(self._plugin_add_input_button)
        self._plugin_remove_button = QPushButton("削除", self)
        self._plugin_remove_button.setEnabled(False)
        self._plugin_remove_button.clicked.connect(self._remove_selected_plugins)
        plugin_button_layout.addWidget(self._plugin_remove_button)
        self._plugin_relative_button = QPushButton("ツールから相対化", self)
        self._plugin_relative_button.setEnabled(False)
        self._plugin_relative_button.clicked.connect(self._convert_selected_plugins_to_tool_relative)
        plugin_button_layout.addWidget(self._plugin_relative_button)
        self._plugin_absolute_button = QPushButton("絶対パス化", self)
        self._plugin_absolute_button.setEnabled(False)
        self._plugin_absolute_button.clicked.connect(self._convert_selected_plugins_to_absolute)
        plugin_button_layout.addWidget(self._plugin_absolute_button)
        plugin_button_layout.addStretch(1)
        plugin_layout.addLayout(plugin_button_layout)
        layout.addLayout(plugin_layout)

        env_label = QLabel("環境変数の設定", self)
        layout.addWidget(env_label)
        self._known_path_checkbox = QCheckBox(
            "環境変数のパスを Known Folder で補完する",
            self,
        )
        self._known_path_checkbox.setChecked(True)
        layout.addWidget(self._known_path_checkbox)
        self._input_token_hint = QLabel(
            "入力プラグを参照する場合は {{input:プラグ名}} を記述してください。",
            self,
        )
        self._input_token_hint.setWordWrap(True)
        layout.addWidget(self._input_token_hint)
        self._env_vars_edit = QPlainTextEdit(self)
        self._env_vars_edit.setPlaceholderText("例:\nOCIO=path/to/config.ocio\nAPP_MODE=dev")
        layout.addWidget(self._env_vars_edit)

        args_label = QLabel("起動引数の設定", self)
        layout.addWidget(args_label)
        self._args_token_hint = QLabel(
            "入力プラグは {{input:プラグ名}} で参照できます。",
            self,
        )
        self._args_token_hint.setWordWrap(True)
        layout.addWidget(self._args_token_hint)
        self._launch_args_edit = QPlainTextEdit(self)
        self._launch_args_edit.setPlaceholderText("例:\n--project path/to/project\n--verbose")
        layout.addWidget(self._launch_args_edit)

        button_layout = QHBoxLayout()
        self._create_button = QPushButton("保存", self)
        self._create_button.clicked.connect(self._save_environment)
        button_layout.addWidget(self._create_button)
        button_layout.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.Close, Qt.Horizontal, self)
        buttons.rejected.connect(self.reject)
        button_layout.addWidget(buttons)
        layout.addLayout(button_layout)

    def _populate_packages(self) -> None:
        self._package_combo.clear()
        packages = self._service.list_rez_packages()
        if not packages:
            self._package_combo.addItem("パッケージがありません", None)
            self._package_combo.setEnabled(False)
            return
        for spec in sorted(packages, key=lambda item: (item.name, item.version or "")):
            label = f"{spec.name} ({spec.version})" if spec.version else spec.name
            self._package_combo.addItem(label, spec)
        self._package_combo.setEnabled(True)

    def _load_existing(self) -> None:
        self._env_vars_edit.setPlainText("")
        self._launch_args_edit.setPlainText("")
        self._required_plugins = []
        self._input_plugs = []
        self._environment_id = None
        self._created_at = None
        self._refresh_plugin_list()
        self._refresh_input_list()
        if self._environment_path is None:
            self._name_edit.setText("")
            return
        payload = self._read_environment_payload(self._environment_path)
        if payload:
            self._apply_environment_payload(payload)
            return
        self._name_edit.setText(self._environment_path.stem)

    def refresh_requested(self) -> bool:
        return self._refresh_requested

    def _read_environment_payload(self, path: Path) -> Optional[dict[str, object]]:
        if not path.exists():
            return None
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            return None
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            QMessageBox.warning(
                self,
                "環境定義の読み込み",
                "環境ファイルの解析に失敗しました。",
            )
            return None
        if isinstance(payload, dict):
            return payload
        return None

    def _apply_environment_payload(self, payload: dict[str, object]) -> None:
        self._environment_id = str(payload.get("environment_id", "")).strip() or None
        self._created_at = str(payload.get("created_at", "")).strip() or None
        self._name_edit.setText(str(payload.get("name", "")).strip())
        self._env_vars_edit.setPlainText(str(payload.get("environment_variables", "")).strip())
        self._launch_args_edit.setPlainText(str(payload.get("launch_arguments", "")).strip())
        package = str(payload.get("package", "")).strip()
        version = str(payload.get("package_version", "")).strip()
        if package:
            self._select_package_in_combo(package, version or None)
        raw_inputs = payload.get("input_plugs")
        if isinstance(raw_inputs, list):
            self._input_plugs = normalize_input_plugs(raw_inputs)
        raw_plugins = payload.get("required_plugins")
        if isinstance(raw_plugins, list):
            self._required_plugins = self._normalize_required_plugins(raw_plugins)
        input_names = {entry.get("name") for entry in self._input_plugs if entry.get("name")}
        for plugin in self._required_plugins:
            if plugin.get("path_type") != "node_input":
                continue
            input_name = normalize_input_name(plugin.get("input_name", ""))
            if not input_name or input_name in input_names:
                continue
            self._input_plugs.append({"name": input_name, "path_kind": "directory"})
            input_names.add(input_name)
        self._refresh_input_list()
        self._refresh_plugin_list()

    def _select_package_in_combo(self, name: str, version: Optional[str]) -> None:
        for index in range(self._package_combo.count()):
            spec = self._package_combo.itemData(index)
            if not isinstance(spec, RezPackageSpec):
                continue
            if spec.name == name and (spec.version or None) == (version or None):
                self._package_combo.setCurrentIndex(index)
                return

    def _normalize_required_plugins(self, entries: list[object]) -> list[dict[str, str]]:
        normalized: list[dict[str, str]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            path_type = str(entry.get("path_type", "")).strip()
            name = str(entry.get("name", "")).strip() or "入力"
            if path_type == "node_input":
                input_name = normalize_input_name(entry.get("input_name", "")) or name
                if not input_name:
                    continue
                normalized.append(
                    {
                        "name": name,
                        "path_type": "node_input",
                        "input_name": input_name,
                        "path_kind": "directory",
                    }
                )
                continue
            if path_type == "known":
                known_id = str(entry.get("known_id", "")).strip()
                relative = str(entry.get("relative_path", "")).strip()
                if known_id and relative:
                    normalized.append(
                        {
                            "name": name,
                            "path_type": "known",
                            "known_id": known_id,
                            "relative_path": relative,
                        }
                    )
                continue
            if path_type == "package":
                package = str(entry.get("package", "")).strip()
                relative = str(entry.get("relative_path", "")).strip()
                if package and relative:
                    normalized.append(
                        {
                            "name": name,
                            "path_type": "package",
                            "package": package,
                            "relative_path": relative,
                        }
                    )
                continue
            if path_type == "tool":
                relative = str(entry.get("relative_path", "")).strip()
                if relative:
                    normalized.append(
                        {
                            "name": name,
                            "path_type": "tool",
                            "relative_path": relative,
                        }
                    )
                continue
            path = str(entry.get("path", "")).strip()
            if path:
                normalized.append(
                    {
                        "name": name,
                        "path_type": "absolute",
                        "path": path,
                    }
                )
        return normalized

    def _save_environment(self) -> None:
        payload = self._build_environment_payload()
        if payload is None:
            return
        if not self._write_environment_payload(payload):
            QMessageBox.warning(
                self,
                "環境保存",
                "環境ファイルの保存に失敗しました。",
            )
            return
        self._refresh_requested = True
        QMessageBox.information(
            self,
            "環境保存",
            "環境ファイルを保存しました。",
        )
        self.accept()

    def _build_environment_payload(self) -> Optional[dict[str, object]]:
        package = self._package_combo.currentData()
        if not isinstance(package, RezPackageSpec):
            QMessageBox.warning(
                self,
                "パッケージ未選択",
                "ツールパッケージを選択してください。",
            )
            return None
        name = self._name_edit.text().strip() or "無名の環境"
        input_plugs = normalize_input_plugs(self._input_plugs)
        input_names = {entry["name"] for entry in input_plugs}
        tokens = self._collect_input_tokens()
        missing = [token for token in tokens if token not in input_names]
        if missing:
            QMessageBox.warning(
                self,
                "入力プラグ不足",
                "次の入力プラグが定義されていません:\n" + "\n".join(missing),
            )
            return None
        invalid_plugins = self._validate_required_plugins(input_names)
        if invalid_plugins:
            QMessageBox.warning(
                self,
                "入力プラグ不足",
                "要求ファイルで参照されている入力プラグが見つかりません:\n"
                + "\n".join(invalid_plugins),
            )
            return None
        env_vars = self._build_environment_variables()
        payload = {
            "environment_id": self._environment_id or str(uuid.uuid4()),
            "name": name,
            "package": package.name,
            "package_version": package.version or "",
            "environment_variables": env_vars,
            "launch_arguments": self._launch_args_edit.toPlainText().strip(),
            "required_plugins": list(self._required_plugins),
            "input_plugs": input_plugs,
        }
        now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
        payload["updated_at"] = now
        payload["created_at"] = self._created_at or now
        return payload

    def _write_environment_payload(self, payload: dict[str, object]) -> bool:
        if self._environment_path is None:
            filename = self._suggest_environment_filename(
                payload.get("name", "environment"),
                payload.get("environment_id", ""),
            )
            candidate = self._environment_dir / filename
            if candidate.exists():
                stem = candidate.stem
                suffix = candidate.suffix
                for index in range(1, 1000):
                    alt = self._environment_dir / f"{stem}_{index}{suffix}"
                    if not alt.exists():
                        candidate = alt
                        break
            self._environment_path = candidate
        self._environment_dir.mkdir(parents=True, exist_ok=True)
        try:
            self._environment_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            return False
        return True

    @staticmethod
    def _suggest_environment_filename(name: object, env_id: object) -> str:
        base = re.sub(r"[^A-Za-z0-9_-]+", "_", str(name)).strip("_")
        if not base:
            base = "environment"
        id_raw = str(env_id).strip() or uuid.uuid4().hex
        id_part = re.sub(r"[^A-Za-z0-9_-]+", "_", id_raw).strip("_") or uuid.uuid4().hex
        return f"{base}_{id_part}.json"

    def _collect_input_tokens(self) -> tuple[str, ...]:
        env_tokens = collect_input_token_names(self._env_vars_edit.toPlainText())
        arg_tokens = collect_input_token_names(self._launch_args_edit.toPlainText())
        combined = list(env_tokens)
        for token in arg_tokens:
            if token not in combined:
                combined.append(token)
        return tuple(combined)

    def _validate_required_plugins(self, input_names: set[str]) -> list[str]:
        missing: list[str] = []
        for entry in self._required_plugins:
            if entry.get("path_type") != "node_input":
                continue
            input_name = normalize_input_name(entry.get("input_name", ""))
            if not input_name:
                continue
            if input_name in input_names:
                continue
            if input_name not in missing:
                missing.append(input_name)
        return missing

    def _open_plugin_dialog(self) -> None:
        start_path = self._resolve_plugin_dialog_start_path()
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "要求プラグインを追加",
            start_path,
            "プラグインファイル (*.*)",
        )
        if not paths:
            return
        extensions = {Path(path).suffix.lower() for path in paths}
        if len(paths) > 1 and len(extensions) > 1:
            QMessageBox.warning(
                self,
                "拡張子の不一致",
                "複数選択する場合は同じ拡張子のファイルを選択してください。",
            )
            return
        for path in paths:
            self._append_required_plugin(Path(path))

    def _add_input_plug(self) -> None:
        name = self._prompt_input_plug_name()
        if not name:
            return
        if any(entry.get("name") == name for entry in self._input_plugs):
            QMessageBox.information(
                self,
                "入力プラグの追加",
                "同名の入力プラグが既に存在します。",
            )
            return
        self._input_plugs.append({"name": name, "path_kind": "directory"})
        self._refresh_input_list()

    def _remove_selected_inputs(self) -> None:
        selected_items = self._input_list.selectedItems()
        if not selected_items:
            return
        names = {item.data(Qt.UserRole) for item in selected_items}
        if not names:
            return
        self._input_plugs = [
            entry for entry in self._input_plugs if entry.get("name") not in names
        ]
        self._required_plugins = [
            entry
            for entry in self._required_plugins
            if not (
                entry.get("path_type") == "node_input"
                and entry.get("input_name") in names
            )
        ]
        self._refresh_input_list()
        self._refresh_plugin_list()

    def _prompt_input_plug_name(self) -> str:
        text, ok = QInputDialog.getText(
            self,
            "入力プラグ名",
            "入力プラグ名を入力してください。",
        )
        if not ok:
            return ""
        normalized = normalize_input_name(text)
        if not normalized:
            QMessageBox.warning(
                self,
                "入力プラグ名",
                "入力プラグ名が無効です。",
            )
        return normalized

    def _refresh_input_list(self) -> None:
        self._input_list.clear()
        for entry in self._input_plugs:
            name = entry.get("name")
            if not name:
                continue
            item = QListWidgetItem(name, self._input_list)
            item.setData(Qt.UserRole, name)
        self._update_input_buttons()

    def _update_input_buttons(self) -> None:
        self._input_remove_button.setEnabled(bool(self._input_list.selectedItems()))

    def _add_input_required_plugin(self) -> None:
        name = self._prompt_input_plug_name()
        if not name:
            return
        if not any(entry.get("name") == name for entry in self._input_plugs):
            self._input_plugs.append({"name": name, "path_kind": "directory"})
            self._refresh_input_list()
        for entry in self._required_plugins:
            if entry.get("path_type") == "node_input" and entry.get("input_name") == name:
                return
        self._required_plugins.append(
            {
                "name": name,
                "path_type": "node_input",
                "input_name": name,
                "path_kind": "directory",
            }
        )
        self._refresh_plugin_list()

    def _resolve_plugin_dialog_start_path(self) -> str:
        package = self._current_package_spec()
        if package is None:
            return str(Path.home())
        executable = self._resolve_execute_path_from_package(package)
        if executable and executable.exists():
            return str(executable)
        executable = self._service.rez_repository.resolve_executable(package)
        if executable and executable.exists():
            return str(executable)
        if package.path.exists():
            return str(package.path)
        return str(Path.home())

    def _resolve_execute_path_from_package(self, package: RezPackageSpec) -> Optional[Path]:
        content = self._read_package_py(package)
        if not content:
            return None
        matches = re.findall(
            r"EXECUTE_[A-Z0-9_]+_EXE[\"']\]\s*=\s*r?[\"']([^\"'\n]+)",
            content,
            flags=re.IGNORECASE,
        )
        for match in matches:
            candidate = Path(match)
            if candidate.exists():
                return candidate
        return None

    def _append_required_plugin(self, path: Path) -> None:
        if not path.exists():
            return
        tool_payload = self._try_build_tool_relative(path)
        if tool_payload:
            self._required_plugins.append(tool_payload)
            self._refresh_plugin_list()
            return
        package_payload = self._try_build_package_relative(path)
        if package_payload:
            self._required_plugins.append(package_payload)
            self._refresh_plugin_list()
            return
        payload = {
            "name": path.stem,
            "path_type": "absolute",
            "path": str(path),
        }
        known_payload = self._try_build_known_path(path)
        if known_payload:
            payload = {
                "name": path.stem,
                **known_payload,
            }
        self._required_plugins.append(payload)
        self._refresh_plugin_list()

    def _refresh_plugin_list(self) -> None:
        self._plugin_list.clear()
        for index, entry in enumerate(self._required_plugins):
            if entry.get("path_type") == "known":
                label = (
                    f"{entry['name']} ({entry['known_id']}:{entry['relative_path']})"
                )
            elif entry.get("path_type") == "package":
                label = (
                    f"{entry['name']} ({entry['package']}:{entry['relative_path']})"
                )
            elif entry.get("path_type") == "tool":
                label = (
                    f"{entry['name']} (tool:{entry['relative_path']})"
                )
            elif entry.get("path_type") == "node_input":
                input_name = entry.get("input_name", entry["name"])
                label = f"{entry['name']} (入力:{input_name})"
            else:
                label = f"{entry['name']} ({entry['path']})"
            item = QListWidgetItem(label, self._plugin_list)
            item.setData(Qt.UserRole, index)
        self._update_plugin_buttons()

    def _update_plugin_buttons(self) -> None:
        has_selection = bool(self._plugin_list.selectedItems())
        has_path_selection = False
        for item in self._plugin_list.selectedItems():
            index = item.data(Qt.UserRole)
            if isinstance(index, int) and 0 <= index < len(self._required_plugins):
                if self._required_plugins[index].get("path_type") != "node_input":
                    has_path_selection = True
                    break
        self._plugin_remove_button.setEnabled(has_selection)
        self._plugin_relative_button.setEnabled(has_path_selection)
        self._plugin_absolute_button.setEnabled(has_path_selection)

    def _remove_selected_plugins(self) -> None:
        selected_items = self._plugin_list.selectedItems()
        if not selected_items:
            return
        indices = {
            item.data(Qt.UserRole)
            for item in selected_items
            if isinstance(item.data(Qt.UserRole), int)
        }
        if not indices:
            return
        for index in sorted(indices, reverse=True):
            if 0 <= index < len(self._required_plugins):
                del self._required_plugins[index]
        self._refresh_plugin_list()

    def _convert_selected_plugins_to_tool_relative(self) -> None:
        indices = self._selected_plugin_indices()
        if not indices:
            return
        base_dir = self._resolve_tool_base_dir()
        if base_dir is None:
            QMessageBox.warning(
                self,
                "相対化できません",
                "ツール実体パスが取得できないため、相対化できませんでした。",
            )
            return
        for index in indices:
            entry = self._required_plugins[index]
            if entry.get("path_type") == "node_input":
                continue
            absolute = self._resolve_plugin_absolute_path(entry)
            if absolute is None:
                continue
            known_payload = self._try_build_known_path(absolute)
            if known_payload:
                entry.clear()
                entry.update(
                    {
                        "name": absolute.stem,
                        **known_payload,
                    }
                )
                continue
            try:
                relative = os.path.relpath(str(absolute), str(base_dir)).replace("\\", "/")
            except ValueError:
                entry.clear()
                entry.update(
                    {
                        "name": absolute.stem,
                        "path_type": "absolute",
                        "path": str(absolute),
                    }
                )
                continue
            normalized = self._normalize_relative_path(relative)
            if normalized is None:
                entry.clear()
                entry.update(
                    {
                        "name": absolute.stem,
                        "path_type": "absolute",
                        "path": str(absolute),
                    }
                )
                continue
            entry.clear()
            entry.update(
                {
                    "name": absolute.stem,
                    "path_type": "tool",
                    "relative_path": normalized,
                }
            )
        self._refresh_plugin_list()

    def _convert_selected_plugins_to_absolute(self) -> None:
        indices = self._selected_plugin_indices()
        if not indices:
            return
        failures: list[str] = []
        for index in indices:
            entry = self._required_plugins[index]
            if entry.get("path_type") == "node_input":
                continue
            absolute = self._resolve_plugin_absolute_path(entry)
            if absolute is None:
                failures.append(entry.get("name", "不明"))
                continue
            entry.clear()
            entry.update(
                {
                    "name": absolute.stem,
                    "path_type": "absolute",
                    "path": str(absolute),
                }
            )
        self._refresh_plugin_list()
        if failures:
            QMessageBox.information(
                self,
                "絶対パス化の結果",
                "次の項目は絶対パスを解決できませんでした:\n" + "\n".join(failures),
            )

    def _selected_plugin_indices(self) -> list[int]:
        selected_items = self._plugin_list.selectedItems()
        if not selected_items:
            return []
        indices: list[int] = []
        for item in selected_items:
            data = item.data(Qt.UserRole)
            if isinstance(data, int):
                indices.append(data)
        return indices

    def _resolve_tool_base_dir(self) -> Optional[Path]:
        package = self._current_package_spec()
        if package is None:
            return None
        executable = self._resolve_execute_path_from_package(package)
        if executable is None or not executable.exists():
            executable = self._service.rez_repository.resolve_executable(package)
        if executable is None or not executable.exists():
            return None
        return executable if executable.is_dir() else executable.parent

    def _try_build_tool_relative(self, path: Path) -> Optional[dict[str, str]]:
        base_dir = self._resolve_tool_base_dir()
        if base_dir is None:
            return None
        absolute = Path(os.path.abspath(path))
        if not self._is_under_base(absolute, base_dir):
            return None
        relative = os.path.relpath(str(absolute), str(base_dir)).replace("\\", "/")
        normalized = self._normalize_relative_path(relative)
        if normalized is None:
            return None
        return {
            "name": path.stem,
            "path_type": "tool",
            "relative_path": normalized,
        }

    def _resolve_plugin_absolute_path(self, entry: dict[str, str]) -> Optional[Path]:
        path_type = entry.get("path_type")
        if path_type == "absolute":
            raw = entry.get("path", "")
            if not raw:
                return None
            return Path(raw)
        if path_type == "known":
            known_id = entry.get("known_id")
            relative = entry.get("relative_path")
            if not known_id or not relative:
                return None
            base = self._resolve_known_folder_base(known_id)
            if base is None:
                return None
            return base / Path(relative.replace("/", os.sep))
        if path_type == "package":
            relative = entry.get("relative_path")
            if not relative:
                return None
            return self._resolve_package_relative_path(relative)
        if path_type == "tool":
            relative = entry.get("relative_path")
            if not relative:
                return None
            base_dir = self._resolve_tool_base_dir()
            if base_dir is None:
                return None
            return base_dir / Path(relative.replace("/", os.sep))
        if path_type == "node_input":
            return None
        return None

    def _resolve_known_folder_base(self, known_id: str) -> Optional[Path]:
        for name, base in self._collect_known_folders():
            if name == known_id:
                return base
        return None

    def _resolve_package_relative_path(self, relative: str) -> Optional[Path]:
        package = self._current_package_spec()
        if package is None:
            return None
        normalized = self._normalize_relative_path(relative)
        if normalized is None:
            return None
        reference_paths = self._collect_package_reference_paths(package)
        if not reference_paths:
            return None
        for reference in reference_paths:
            base = self._reference_base_dir(reference)
            candidate = base / Path(normalized.replace("/", os.sep))
            if candidate.exists():
                return candidate
        base = self._reference_base_dir(reference_paths[0])
        return base / Path(normalized.replace("/", os.sep))

    def _build_environment_variables(self) -> str:
        raw_text = self._env_vars_edit.toPlainText().strip()
        if not raw_text:
            return ""
        if not self._known_path_checkbox.isChecked():
            return raw_text
        if os.name != "nt":
            return raw_text
        lines = raw_text.splitlines()
        replaced_lines = [self._replace_known_paths_in_line(line) for line in lines]
        return "\n".join(replaced_lines).strip()

    def _replace_known_paths_in_line(self, line: str) -> str:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            return line
        key, value = line.split("=", 1)
        replaced_value = self._replace_known_paths(value)
        return f"{key}={replaced_value}"

    def _replace_known_paths(self, value: str) -> str:
        segments = value.split(";")
        replaced_segments = [
            self._replace_path_segment(segment) for segment in segments
        ]
        return ";".join(replaced_segments)

    def _replace_path_segment(self, segment: str) -> str:
        trimmed = segment.strip()
        if not trimmed:
            return segment
        if contains_input_token(trimmed):
            return segment
        candidate = Path(trimmed.strip('"'))
        if not candidate.is_absolute():
            return segment
        package_payload = self._try_build_package_relative(candidate)
        if package_payload:
            prefix = f"{package_payload['package']}:{package_payload['relative_path']}"
        else:
            tool_payload = self._try_build_tool_relative(candidate)
            if tool_payload:
                prefix = f"tool:{tool_payload['relative_path']}"
            else:
                known_payload = self._try_build_known_path(candidate)
                if not known_payload:
                    return segment
                known_id = known_payload["known_id"]
                relative = known_payload["relative_path"]
                prefix = f"{known_id}:{relative}"
        if trimmed.startswith('"') and trimmed.endswith('"'):
            return f'"{prefix}"'
        return prefix

    def _try_build_package_relative(self, path: Path) -> Optional[dict[str, str]]:
        package = self._current_package_spec()
        if package is None:
            return None
        absolute = Path(os.path.abspath(path))
        reference_paths = self._collect_package_reference_paths(package)
        if not reference_paths:
            return None
        relative = self._build_relative_from_reference_paths(absolute, reference_paths)
        if relative is None:
            return None
        normalized = self._normalize_relative_path(relative)
        if normalized is None:
            return None
        return {
            "name": path.stem,
            "path_type": "package",
            "package": package.name,
            "relative_path": normalized,
        }

    def _current_package_spec(self) -> Optional[RezPackageSpec]:
        package = self._package_combo.currentData()
        if isinstance(package, RezPackageSpec):
            return package
        return None

    def _collect_package_reference_paths(self, package: RezPackageSpec) -> list[Path]:
        content = self._read_package_py(package)
        if not content:
            return []
        matches = re.findall(r"([A-Za-z]:\\\\[^\"\n]+)", content, flags=re.IGNORECASE)
        return self._normalize_reference_paths(matches)

    def _normalize_reference_paths(self, raw_paths: list[str]) -> list[Path]:
        seen: set[str] = set()
        normalized: list[Path] = []
        for raw_path in raw_paths:
            candidate = Path(raw_path)
            if candidate.as_posix() in seen:
                continue
            seen.add(candidate.as_posix())
            normalized.append(candidate)
        return normalized

    def _build_relative_from_reference_paths(
        self,
        absolute: Path,
        reference_paths: list[Path],
    ) -> Optional[str]:
        for reference in reference_paths:
            anchor = self._reference_base_dir(reference)
            if not self._is_under_base(absolute, anchor):
                continue
            relative = os.path.relpath(str(absolute), str(anchor))
            normalized = self._normalize_relative_path(relative.replace("\\", "/"))
            if normalized is None:
                return None
            return normalized
        return None

    @staticmethod
    def _reference_base_dir(reference: Path) -> Path:
        if reference.is_dir():
            return reference
        return reference.parent

    def _try_build_known_path(self, path: Path) -> Optional[dict[str, str]]:
        if os.name != "nt":
            return None
        absolute = Path(os.path.abspath(path))
        for known_id, base in self._collect_known_folders():
            if self._is_under_base(absolute, base):
                relative = os.path.relpath(str(absolute), str(base))
                normalized = self._normalize_relative_path(relative.replace("\\", "/"))
                if normalized is None:
                    return None
                return {
                    "path_type": "known",
                    "known_id": known_id,
                    "relative_path": normalized,
                }
        return None

    def _collect_known_folders(self) -> list[tuple[str, Path]]:
        if self._known_folders_cache is not None:
            return list(self._known_folders_cache)
        known_folder_ids = {
            "FOLDERID_Documents": "{FDD39AD0-238F-46AF-ADB4-6C85480369C7}",
            "FOLDERID_Downloads": "{374DE290-123F-4565-9164-39C4925E467B}",
            "FOLDERID_Desktop": "{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}",
            "FOLDERID_RoamingAppData": "{3EB685DB-65F9-4CF6-A03A-E3EF65729F3D}",
            "FOLDERID_LocalAppData": "{F1B32785-6FBA-4FCF-9D55-7B8E7F157091}",
            "FOLDERID_ProgramFiles": "{905E63B6-C1BF-494E-B29C-65B732D3D21A}",
            "FOLDERID_ProgramFilesX64": "{6D809377-6AF0-444B-8957-A3773F02200E}",
            "FOLDERID_ProgramFilesX86": "{7C5A40EF-A0FB-4BFC-874A-C0F2E0B9FA8E}",
        }
        known_folders: list[tuple[str, Path]] = []
        for name, guid_text in known_folder_ids.items():
            resolved = self._resolve_known_folder(guid_text)
            if resolved is None:
                continue
            known_folders.append((name, resolved))
        self._known_folders_cache = list(known_folders)
        return list(known_folders)

    def _resolve_known_folder(self, guid_text: str) -> Optional[Path]:
        folder_id = self._guid_from_string(guid_text)
        if folder_id is None:
            return None
        path_ptr = ctypes.c_wchar_p()
        result = ctypes.windll.shell32.SHGetKnownFolderPath(
            ctypes.byref(folder_id), 0, None, ctypes.byref(path_ptr)
        )
        if result != 0 or not path_ptr.value:
            return None
        try:
            return Path(path_ptr.value)
        finally:
            ctypes.windll.ole32.CoTaskMemFree(path_ptr)

    def _guid_from_string(self, guid_text: str) -> Optional["_Guid"]:
        try:
            guid = uuid.UUID(guid_text)
        except ValueError:
            return None
        return _Guid.from_uuid(guid)

    def _read_package_py(self, package: RezPackageSpec) -> str:
        package_file = package.path / "package.py"
        cached = self._package_py_cache.get(package_file)
        if cached is not None:
            return cached
        if not package_file.exists():
            self._package_py_cache[package_file] = ""
            return ""
        try:
            content = package_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            self._package_py_cache[package_file] = ""
            return ""
        self._package_py_cache[package_file] = content
        return content

    @staticmethod
    def _normalize_relative_path(relative: str) -> Optional[str]:
        normalized = relative.replace("\\", "/").strip()
        if not normalized:
            return None
        if normalized.startswith(("/", "\\")):
            return None
        if ":" in normalized:
            return None
        parts = [part for part in normalized.split("/") if part]
        if any(part == ".." for part in parts):
            return None
        return "/".join(parts)

    @staticmethod
    def _is_under_base(path: Path, base: Path) -> bool:
        try:
            common = os.path.commonpath([str(path), str(base)])
        except ValueError:
            return False
        return os.path.normcase(common) == os.path.normcase(str(base))


class _Guid(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_ulong),
        ("Data2", ctypes.c_ushort),
        ("Data3", ctypes.c_ushort),
        ("Data4", ctypes.c_ubyte * 8),
    ]

    @classmethod
    def from_uuid(cls, value: uuid.UUID) -> "_Guid":
        data4 = (ctypes.c_ubyte * 8).from_buffer_copy(value.bytes[8:])
        return cls(
            value.time_low,
            value.time_mid,
            value.time_hi_version,
            data4,
        )
