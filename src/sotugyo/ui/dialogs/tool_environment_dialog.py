"""ツール起動環境の構成ダイアログ。"""

from __future__ import annotations

import ctypes
import json
import sys
from pathlib import Path
from typing import Optional

from qtpy import QtCore, QtWidgets

Qt = QtCore.Qt
QDialog = QtWidgets.QDialog
QDialogButtonBox = QtWidgets.QDialogButtonBox
QFormLayout = QtWidgets.QFormLayout
QHBoxLayout = QtWidgets.QHBoxLayout
QCheckBox = QtWidgets.QCheckBox
QFileDialog = QtWidgets.QFileDialog
QLabel = QtWidgets.QLabel
QLineEdit = QtWidgets.QLineEdit
QListWidget = QtWidgets.QListWidget
QListWidgetItem = QtWidgets.QListWidgetItem
QMessageBox = QtWidgets.QMessageBox
QPlainTextEdit = QtWidgets.QPlainTextEdit
QPushButton = QtWidgets.QPushButton
QComboBox = QtWidgets.QComboBox
QVBoxLayout = QtWidgets.QVBoxLayout
QWidget = QtWidgets.QWidget

from ...domain.tooling.models import RezPackageSpec
from ...domain.tooling import ToolEnvironmentService
from ...infrastructure.paths.storage import get_tool_environment_dir

_KNOWN_FOLDER_IDS = {
    "FOLDERID_RoamingAppData": "{3EB685DB-65F9-4CF6-A03A-E3EF65729F3D}",
    "FOLDERID_LocalAppData": "{F1B32785-6FBA-4FCF-9D55-7B8E7F157091}",
    "FOLDERID_ProgramData": "{62AB5D82-FDC1-4DC3-A9DD-070D1D495D97}",
    "FOLDERID_ProgramFiles": "{905E63B6-C1BF-494E-B29C-65B732D3D21A}",
    "FOLDERID_ProgramFilesX86": "{7C5A40EF-A0FB-4BFC-874A-C0F2E0B9FA8E}",
    "FOLDERID_Documents": "{FDD39AD0-238F-46AF-ADB4-6C85480369C7}",
    "FOLDERID_Desktop": "{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}",
}


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
        self._required_plugins: list[dict[str, dict[str, str] | str]] = []
        self._known_folder_cache: Optional[dict[str, Path]] = None

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

        self._plugin_list = QListWidget(self)
        layout.addWidget(self._plugin_list)

        plugin_action_layout = QHBoxLayout()
        self._known_folder_check = QCheckBox("Known Folder で相対化（推奨）", self)
        self._known_folder_check.setChecked(True)
        plugin_action_layout.addWidget(self._known_folder_check)

        self._add_plugin_button = QPushButton("追加", self)
        self._add_plugin_button.clicked.connect(self._open_plugin_dialog)
        plugin_action_layout.addWidget(self._add_plugin_button)
        plugin_action_layout.addStretch(1)
        layout.addLayout(plugin_action_layout)

        env_label = QLabel("環境変数の設定", self)
        layout.addWidget(env_label)
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
        self._required_plugins.clear()
        self._plugin_list.clear()
        if self._environment_path is None:
            self._name_edit.setText("")
            return
        self._name_edit.setText(self._environment_path.stem)

    def _open_plugin_dialog(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "要求プラグインの追加",
            "",
            "プラグインファイル (*);;すべてのファイル (*)",
        )
        if not paths:
            return
        extensions = {Path(path).suffix.lower() for path in paths}
        if len(extensions) > 1:
            QMessageBox.warning(
                self,
                "拡張子の不一致",
                "複数選択する場合は拡張子を統一してください。",
            )
            return
        use_known_folder = self._known_folder_check.isChecked()
        for path in paths:
            entry = self._build_plugin_entry(Path(path), use_known_folder)
            self._required_plugins.append(entry)
            self._add_plugin_item(entry)

    def _build_plugin_entry(self, path: Path, use_known_folder: bool) -> dict[str, dict[str, str] | str]:
        name = path.stem
        known_payload = self._resolve_known_folder_payload(path) if use_known_folder else None
        if known_payload is None:
            return {
                "name": name,
                "path": {"type": "absolute", "value": str(path)},
            }
        return {"name": name, "path": known_payload}

    def _resolve_known_folder_payload(self, path: Path) -> Optional[dict[str, str]]:
        candidates = self._known_folder_paths()
        if not candidates:
            return None
        resolved_path = path.resolve()
        for identifier, base in candidates.items():
            try:
                relative_path = resolved_path.relative_to(base.resolve())
            except ValueError:
                continue
            return {
                "type": "known",
                "identifier": identifier,
                "relative_path": relative_path.as_posix(),
            }
        return None

    def _known_folder_paths(self) -> dict[str, Path]:
        if self._known_folder_cache is None:
            self._known_folder_cache = _load_known_folder_paths()
        return self._known_folder_cache

    def _add_plugin_item(self, entry: dict[str, dict[str, str] | str]) -> None:
        path_info = entry["path"]
        if isinstance(path_info, dict) and path_info.get("type") == "known":
            path_label = f"{path_info['identifier']}:{path_info['relative_path']}"
        elif isinstance(path_info, dict):
            path_label = path_info.get("value", "")
        else:
            path_label = str(path_info)
        text = f"{entry['name']} ({path_label})"
        item = QListWidgetItem(text, self._plugin_list)
        item.setData(Qt.UserRole, entry)

    def _print_environment(self) -> None:
        package = self._package_combo.currentData()
        payload = {
            "name": self._name_edit.text().strip() or "無名の環境",
            "package": package.name if isinstance(package, RezPackageSpec) else None,
            "package_version": package.version if isinstance(package, RezPackageSpec) else None,
            "required_plugins": self._required_plugins,
            "environment_variables": self._env_vars_edit.toPlainText().strip(),
            "launch_arguments": self._launch_args_edit.toPlainText().strip(),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))


def _load_known_folder_paths() -> dict[str, Path]:
    if not sys.platform.startswith("win"):
        return {}
    shell32 = ctypes.windll.shell32
    ole32 = ctypes.windll.ole32

    class _Guid(ctypes.Structure):
        _fields_ = [
            ("Data1", ctypes.c_ulong),
            ("Data2", ctypes.c_ushort),
            ("Data3", ctypes.c_ushort),
            ("Data4", ctypes.c_ubyte * 8),
        ]

    def _guid_from_string(value: str) -> _Guid:
        hex_value = value.strip("{}")
        bytes_value = bytes.fromhex(hex_value.replace("-", ""))
        data1 = int.from_bytes(bytes_value[0:4], "little")
        data2 = int.from_bytes(bytes_value[4:6], "little")
        data3 = int.from_bytes(bytes_value[6:8], "little")
        data4 = (ctypes.c_ubyte * 8).from_buffer_copy(bytes_value[8:])
        return _Guid(data1, data2, data3, data4)

    paths: dict[str, Path] = {}
    for name, guid in _KNOWN_FOLDER_IDS.items():
        folder_id = _guid_from_string(guid)
        path_ptr = ctypes.c_wchar_p()
        result = shell32.SHGetKnownFolderPath(ctypes.byref(folder_id), 0, 0, ctypes.byref(path_ptr))
        if result != 0:
            continue
        try:
            if not path_ptr.value:
                continue
            paths[name] = Path(path_ptr.value)
        finally:
            ole32.CoTaskMemFree(path_ptr)
    return paths
