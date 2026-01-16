"""ツール起動環境の構成ダイアログ。"""

from __future__ import annotations

import ctypes
import json
import os
import uuid
from pathlib import Path
from typing import Optional

from qtpy import QtCore, QtWidgets

Qt = QtCore.Qt
QDialog = QtWidgets.QDialog
QDialogButtonBox = QtWidgets.QDialogButtonBox
QFormLayout = QtWidgets.QFormLayout
QHBoxLayout = QtWidgets.QHBoxLayout
QLabel = QtWidgets.QLabel
QLineEdit = QtWidgets.QLineEdit
QListWidget = QtWidgets.QListWidget
QListWidgetItem = QtWidgets.QListWidgetItem
QPlainTextEdit = QtWidgets.QPlainTextEdit
QPushButton = QtWidgets.QPushButton
QComboBox = QtWidgets.QComboBox
QVBoxLayout = QtWidgets.QVBoxLayout
QWidget = QtWidgets.QWidget
QMessageBox = QtWidgets.QMessageBox
QFileDialog = QtWidgets.QFileDialog

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

        required_label = QLabel("要求プラグインの設定", self)
        layout.addWidget(required_label)

        self._required_plugin_list = QListWidget(self)
        layout.addWidget(self._required_plugin_list)

        plugin_button_layout = QHBoxLayout()
        self._add_plugin_button = QPushButton("追加", self)
        self._add_plugin_button.clicked.connect(self._open_plugin_dialog)
        plugin_button_layout.addWidget(self._add_plugin_button)
        plugin_button_layout.addStretch(1)
        layout.addLayout(plugin_button_layout)

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
        self._required_plugin_list.clear()
        if self._environment_path is None:
            self._name_edit.setText("")
            return
        self._name_edit.setText(self._environment_path.stem)

    def _open_plugin_dialog(self) -> None:
        selected_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "要求プラグインを選択",
            "",
            "プラグインファイル (*.dll *.so *.dylib *.plugin *.bundle *.exe);;すべてのファイル (*)",
        )
        if not selected_paths:
            return
        paths = [Path(path) for path in selected_paths]
        if self._has_mixed_extensions(paths):
            QMessageBox.warning(
                self,
                "拡張子の統一が必要です",
                "複数選択する場合は同じ拡張子のファイルのみ選択してください。",
            )
            return
        for path in paths:
            record = self._build_plugin_record(path)
            item = QListWidgetItem(self._format_plugin_label(record), self._required_plugin_list)
            item.setData(Qt.UserRole, record)

    @staticmethod
    def _has_mixed_extensions(paths: list[Path]) -> bool:
        if len(paths) <= 1:
            return False
        extensions = {path.suffix.lower() for path in paths}
        return len(extensions) > 1

    def _build_plugin_record(self, path: Path) -> dict[str, object]:
        resolved = path.expanduser().resolve()
        record = {
            "name": resolved.stem,
            "path": self._build_path_record(resolved),
        }
        return record

    def _format_plugin_label(self, record: dict[str, object]) -> str:
        name = record.get("name") or ""
        path_record = record.get("path")
        display_path = ""
        if isinstance(path_record, dict):
            display_path = path_record.get("display", "")
        return f"{name} - {display_path}" if display_path else str(name)

    def _build_path_record(self, path: Path) -> dict[str, str]:
        known = self._resolve_known_folder(path)
        if known:
            return {
                "attribute": "known",
                "folder_id": known["folder_id"],
                "relative_path": known["relative_path"],
                "display": str(path),
            }
        return {
            "attribute": "absolute",
            "path": str(path),
            "display": str(path),
        }

    def _resolve_known_folder(self, path: Path) -> Optional[dict[str, str]]:
        if os.name != "nt":
            return None
        for folder_id, folder_path in self._known_folder_paths():
            try:
                relative = path.relative_to(folder_path)
            except ValueError:
                continue
            return {
                "folder_id": folder_id,
                "relative_path": str(relative),
            }
        return None

    def _known_folder_paths(self) -> list[tuple[str, Path]]:
        folders = []
        for folder_id in self._known_folder_ids():
            folder_path = self._get_known_folder_path(folder_id)
            if folder_path is None:
                continue
            folders.append((folder_id, folder_path))
        return folders

    @staticmethod
    def _known_folder_ids() -> list[str]:
        return [
            "FDD39AD0-238F-46AF-ADB4-6C85480369C7",  # Documents
            "B4BFCC3A-DB2C-424C-B029-7FE99A87C641",  # Desktop
            "F1B32785-6FBA-4FCF-9D55-7B8E7F157091",  # LocalAppData
            "3EB685DB-65F9-4CF6-A03A-E3EF65729F3D",  # RoamingAppData
            "62AB5D82-FDC1-4DC3-A9DD-070D1D495D97",  # ProgramData
        ]

    @staticmethod
    def _get_known_folder_path(folder_id: str) -> Optional[Path]:
        if os.name != "nt":
            return None

        class GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", ctypes.c_ulong),
                ("Data2", ctypes.c_ushort),
                ("Data3", ctypes.c_ushort),
                ("Data4", ctypes.c_ubyte * 8),
            ]

        def build_guid(value: str) -> GUID:
            parsed = uuid.UUID(value)
            data4 = (ctypes.c_ubyte * 8).from_buffer_copy(parsed.bytes[8:])
            return GUID(parsed.time_low, parsed.time_mid, parsed.time_hi_version, data4)

        path_ptr = ctypes.c_wchar_p()
        flags = 0
        result = ctypes.windll.shell32.SHGetKnownFolderPath(  # type: ignore[attr-defined]
            ctypes.byref(build_guid(folder_id)),
            flags,
            None,
            ctypes.byref(path_ptr),
        )
        if result != 0:
            return None
        try:
            path_value = Path(path_ptr.value).resolve()
        finally:
            ctypes.windll.ole32.CoTaskMemFree(path_ptr)  # type: ignore[attr-defined]
        return path_value

    def _collect_plugin_records(self) -> list[dict[str, object]]:
        records = []
        for index in range(self._required_plugin_list.count()):
            item = self._required_plugin_list.item(index)
            data = item.data(Qt.UserRole)
            if isinstance(data, dict):
                records.append(data)
        return records

    def _print_environment(self) -> None:
        package = self._package_combo.currentData()
        payload = {
            "name": self._name_edit.text().strip() or "無名の環境",
            "package": package.name if isinstance(package, RezPackageSpec) else None,
            "package_version": package.version if isinstance(package, RezPackageSpec) else None,
            "required_plugins": self._collect_plugin_records(),
            "environment_variables": self._env_vars_edit.toPlainText().strip(),
            "launch_arguments": self._launch_args_edit.toPlainText().strip(),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
