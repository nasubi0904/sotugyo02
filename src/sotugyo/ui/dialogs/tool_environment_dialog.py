"""ツール起動環境の構成ダイアログ。"""

from __future__ import annotations

import json
import os
import uuid
import ctypes
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

from ...domain.tooling.models import RezPackageSpec
from ...domain.tooling import ToolEnvironmentService
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
        buttons.rejected.connect(self.reject)
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
            item = QListWidgetItem(entry.stem, self._environment_list)
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
        self._required_plugins: list[dict[str, str]] = []

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

        plugin_label = QLabel("要求プラグインの設定", self)
        layout.addWidget(plugin_label)

        plugin_layout = QHBoxLayout()
        self._plugin_list = QListWidget(self)
        self._plugin_list.itemSelectionChanged.connect(self._update_plugin_buttons)
        plugin_layout.addWidget(self._plugin_list, 1)

        plugin_button_layout = QVBoxLayout()
        self._plugin_add_button = QPushButton("追加", self)
        self._plugin_add_button.clicked.connect(self._open_plugin_dialog)
        plugin_button_layout.addWidget(self._plugin_add_button)
        self._plugin_remove_button = QPushButton("削除", self)
        self._plugin_remove_button.setEnabled(False)
        self._plugin_remove_button.clicked.connect(self._remove_selected_plugins)
        plugin_button_layout.addWidget(self._plugin_remove_button)
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
        self._env_vars_edit = QPlainTextEdit(self)
        self._env_vars_edit.setPlaceholderText("例:\nOCIO=path/to/config.ocio\nAPP_MODE=dev")
        layout.addWidget(self._env_vars_edit)

        args_label = QLabel("起動引数の設定", self)
        layout.addWidget(args_label)
        self._launch_args_edit = QPlainTextEdit(self)
        self._launch_args_edit.setPlaceholderText("例:\n--project path/to/project\n--verbose")
        layout.addWidget(self._launch_args_edit)

        button_layout = QHBoxLayout()
        self._create_button = QPushButton("環境作成", self)
        self._create_button.clicked.connect(self._print_environment)
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
        self._refresh_plugin_list()
        if self._environment_path is None:
            self._name_edit.setText("")
            return
        self._name_edit.setText(self._environment_path.stem)

    def _print_environment(self) -> None:
        package = self._package_combo.currentData()
        payload = {
            "name": self._name_edit.text().strip() or "無名の環境",
            "package": package.name if isinstance(package, RezPackageSpec) else None,
            "package_version": package.version if isinstance(package, RezPackageSpec) else None,
            "environment_variables": self._build_environment_variables(),
            "launch_arguments": self._launch_args_edit.toPlainText().strip(),
            "required_plugins": list(self._required_plugins),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))

    def _open_plugin_dialog(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "要求プラグインを追加",
            str(Path.home()),
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

    def _append_required_plugin(self, path: Path) -> None:
        if not path.exists():
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
            else:
                label = f"{entry['name']} ({entry['path']})"
            item = QListWidgetItem(label, self._plugin_list)
            item.setData(Qt.UserRole, index)
        self._update_plugin_buttons()

    def _update_plugin_buttons(self) -> None:
        has_selection = bool(self._plugin_list.selectedItems())
        self._plugin_remove_button.setEnabled(has_selection)

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
        candidate = Path(trimmed.strip('"'))
        if not candidate.is_absolute():
            return segment
        package_payload = self._try_build_package_relative(candidate)
        if package_payload:
            prefix = f"{package_payload['package']}:{package_payload['relative_path']}"
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
        package_root = package.path
        package_anchor = package_root.parent
        if len(package_root.parents) > 1:
            package_anchor = package_root.parents[1]
        absolute = Path(os.path.abspath(path))
        if not self._is_under_base(absolute, package_anchor):
            return None
        if not self._is_under_base(absolute, package_root):
            return None
        relative = os.path.relpath(str(absolute), str(package_root))
        return {
            "name": path.stem,
            "path_type": "package",
            "package": package.name,
            "relative_path": relative.replace("\\", "/"),
        }

    def _current_package_spec(self) -> Optional[RezPackageSpec]:
        package = self._package_combo.currentData()
        if isinstance(package, RezPackageSpec):
            return package
        return None

    def _try_build_known_path(self, path: Path) -> Optional[dict[str, str]]:
        if os.name != "nt":
            return None
        absolute = Path(os.path.abspath(path))
        for known_id, base in self._collect_known_folders():
            if self._is_under_base(absolute, base):
                relative = os.path.relpath(str(absolute), str(base))
                return {
                    "path_type": "known",
                    "known_id": known_id,
                    "relative_path": relative.replace("\\", "/"),
                }
        return None

    def _collect_known_folders(self) -> list[tuple[str, Path]]:
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
        return known_folders

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
