"""ツール起動環境の構成ダイアログ。"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Dict, List, Optional, Tuple

from qtpy import QtCore, QtWidgets

Qt = QtCore.Qt
QAbstractItemView = QtWidgets.QAbstractItemView
QComboBox = QtWidgets.QComboBox
QDialog = QtWidgets.QDialog
QDialogButtonBox = QtWidgets.QDialogButtonBox
QGridLayout = QtWidgets.QGridLayout
QGroupBox = QtWidgets.QGroupBox
QHBoxLayout = QtWidgets.QHBoxLayout
QHeaderView = QtWidgets.QHeaderView
QLabel = QtWidgets.QLabel
QLineEdit = QtWidgets.QLineEdit
QMessageBox = QtWidgets.QMessageBox
QPushButton = QtWidgets.QPushButton
QTableWidget = QtWidgets.QTableWidget
QTableWidgetItem = QtWidgets.QTableWidgetItem
QTreeWidget = QtWidgets.QTreeWidget
QTreeWidgetItem = QtWidgets.QTreeWidgetItem
QVBoxLayout = QtWidgets.QVBoxLayout
QWidget = QtWidgets.QWidget

from ...domain.tooling import RezPackageSpec, ToolEnvironmentDefinition, ToolEnvironmentService


@dataclass(slots=True)
class _ColorSpaceEntry:
    label: str
    env_name: str


class ToolEnvironmentManagerDialog(QDialog):
    """ツール起動環境の構成を行うダイアログ。"""

    def __init__(self, service: ToolEnvironmentService, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._service = service
        self._refresh_on_accept = False
        self._environment_list: Optional[QTreeWidget] = None
        self._edit_button: Optional[QPushButton] = None
        self._status_label: Optional[QLabel] = None
        self._environment_map: Dict[str, ToolEnvironmentDefinition] = {}

        self.setWindowTitle("ツール起動環境の構成")
        self.resize(720, 480)

        self._build_ui()
        self._refresh_environment_list()

    def refresh_requested(self) -> bool:
        return self._refresh_on_accept

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        description = QLabel(
            "登録済みツールの起動環境を一覧表示し、環境変数や起動引数コネクタを定義します。",
            self,
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        environment_list = QTreeWidget(self)
        environment_list.setColumnCount(4)
        environment_list.setHeaderLabels(["環境名", "ツール", "バージョン", "Rez パッケージ"])
        environment_list.setRootIsDecorated(False)
        environment_list.setAlternatingRowColors(True)
        environment_list.setSelectionMode(QAbstractItemView.SingleSelection)
        environment_list.setSelectionBehavior(QAbstractItemView.SelectRows)
        environment_list.setUniformRowHeights(True)
        environment_list.setAllColumnsShowFocus(True)
        environment_list.itemSelectionChanged.connect(self._update_edit_button_state)
        layout.addWidget(environment_list, 1)
        self._environment_list = environment_list

        button_row = QHBoxLayout()
        add_button = QPushButton("環境を追加", self)
        add_button.clicked.connect(self._open_add_dialog)
        edit_button = QPushButton("選択環境を編集", self)
        edit_button.setEnabled(False)
        edit_button.clicked.connect(self._open_edit_dialog)
        button_row.addWidget(add_button)
        button_row.addWidget(edit_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)
        self._edit_button = edit_button

        status_label = QLabel("登録されている環境数: 0", self)
        status_label.setObjectName("statusLabel")
        layout.addWidget(status_label)
        self._status_label = status_label

        buttons = QDialogButtonBox(QDialogButtonBox.Close, Qt.Horizontal, self)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _refresh_environment_list(self) -> None:
        if self._environment_list is None:
            return
        try:
            environments = self._service.list_environments()
            tools = self._service.list_tools()
        except OSError as exc:
            QMessageBox.critical(self, "エラー", f"環境の読み込みに失敗しました: {exc}")
            environments = []
            tools = []

        tool_map = {tool.tool_id: tool.display_name for tool in tools}
        self._environment_map = {env.environment_id: env for env in environments}

        self._environment_list.clear()
        for env in environments:
            tool_label = tool_map.get(env.tool_id, env.tool_id)
            packages_label = ", ".join(env.rez_packages) if env.rez_packages else "-"
            item = QTreeWidgetItem(
                [
                    env.name,
                    tool_label,
                    env.version_label or "-",
                    packages_label,
                ]
            )
            item.setData(0, Qt.UserRole, env.environment_id)
            self._environment_list.addTopLevelItem(item)

        for column in range(3):
            self._environment_list.resizeColumnToContents(column)

        if self._status_label is not None:
            self._status_label.setText(f"登録されている環境数: {len(environments)}")
        self._update_edit_button_state()

    def _current_environment_id(self) -> Optional[str]:
        if self._environment_list is None:
            return None
        item = self._environment_list.currentItem()
        if item is None:
            return None
        env_id = item.data(0, Qt.UserRole)
        return env_id if isinstance(env_id, str) else None

    def _update_edit_button_state(self) -> None:
        if self._edit_button is None:
            return
        self._edit_button.setEnabled(self._current_environment_id() is not None)

    def _open_add_dialog(self) -> None:
        dialog = ToolEnvironmentEditorDialog(self._service, self)
        dialog.exec()

    def _open_edit_dialog(self) -> None:
        env_id = self._current_environment_id()
        if env_id is None:
            QMessageBox.information(self, "編集", "編集する環境を選択してください。")
            return
        environment = self._environment_map.get(env_id)
        if environment is None:
            QMessageBox.warning(self, "編集", "選択した環境が見つかりませんでした。")
            return
        dialog = ToolEnvironmentEditorDialog(self._service, self, environment=environment)
        dialog.exec()


class ToolEnvironmentEditorDialog(QDialog):
    """環境定義を編集するためのモーダルダイアログ。"""

    def __init__(
        self,
        service: ToolEnvironmentService,
        parent: Optional[QWidget] = None,
        *,
        environment: ToolEnvironmentDefinition | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._environment = environment
        self._name_field: Optional[QLineEdit] = None
        self._package_combo: Optional[QComboBox] = None
        self._color_combo: Optional[QComboBox] = None
        self._env_table: Optional[QTableWidget] = None
        self._arg_table: Optional[QTableWidget] = None
        self._packages: List[RezPackageSpec] = []
        self._confirmed_payload: Optional[Dict[str, object]] = None

        title = "環境定義の編集" if environment else "環境定義の追加"
        self.setWindowTitle(title)
        self.resize(620, 560)

        self._build_ui()
        self._load_packages()
        self._load_environment_values()

    def confirmed_payload(self) -> Optional[Dict[str, object]]:
        return self._confirmed_payload

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        header = QLabel(
            "環境変数と起動引数コネクタを定義し、環境ノードとして登録します（デモ）。",
            self,
        )
        header.setWordWrap(True)
        layout.addWidget(header)

        form = QGridLayout()
        form.setColumnStretch(1, 1)

        name_label = QLabel("環境名", self)
        name_field = QLineEdit(self)
        form.addWidget(name_label, 0, 0)
        form.addWidget(name_field, 0, 1)
        self._name_field = name_field

        package_label = QLabel("ツールパッケージ", self)
        package_combo = QComboBox(self)
        package_combo.currentIndexChanged.connect(self._handle_package_changed)
        form.addWidget(package_label, 1, 0)
        form.addWidget(package_combo, 1, 1)
        self._package_combo = package_combo

        color_label = QLabel("色空間（環境変数名）", self)
        color_combo = QComboBox(self)
        form.addWidget(color_label, 2, 0)
        form.addWidget(color_combo, 2, 1)
        self._color_combo = color_combo

        layout.addLayout(form)

        env_group = self._build_table_group(
            title="環境変数",
            headers=("変数名", "値"),
            add_label="環境変数を追加",
        )
        self._env_table = env_group.table
        layout.addWidget(env_group.container)

        arg_group = self._build_table_group(
            title="起動引数コネクタ",
            headers=("引数名", "値"),
            add_label="起動引数を追加",
        )
        self._arg_table = arg_group.table
        layout.addWidget(arg_group.container)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        create_button = QPushButton("環境を作成（デモ）", self)
        create_button.clicked.connect(self._confirm_payload)
        close_button = QPushButton("閉じる", self)
        close_button.clicked.connect(self.reject)
        button_row.addWidget(create_button)
        button_row.addWidget(close_button)
        layout.addLayout(button_row)

    def _build_table_group(
        self,
        *,
        title: str,
        headers: Tuple[str, str],
        add_label: str,
    ) -> "_TableGroup":
        group = QGroupBox(title, self)
        layout = QVBoxLayout(group)
        table = QTableWidget(0, 2, group)
        table.setHorizontalHeaderLabels(list(headers))
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        layout.addWidget(table)

        buttons = QHBoxLayout()
        add_button = QPushButton(add_label, group)
        remove_button = QPushButton("選択行を削除", group)
        add_button.clicked.connect(lambda: self._add_table_row(table))
        remove_button.clicked.connect(lambda: self._remove_table_row(table))
        buttons.addWidget(add_button)
        buttons.addWidget(remove_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        return _TableGroup(container=group, table=table)

    def _load_packages(self) -> None:
        if self._package_combo is None:
            return
        try:
            packages = self._service.list_rez_packages()
        except OSError:
            packages = []
        self._packages = packages
        self._package_combo.clear()
        if not packages:
            self._package_combo.addItem("利用可能なパッケージがありません", None)
            self._package_combo.setEnabled(False)
            self._refresh_color_spaces(None)
            return

        self._package_combo.setEnabled(True)
        for spec in packages:
            label = spec.name
            if spec.version:
                label = f"{spec.name} ({spec.version})"
            self._package_combo.addItem(label, spec)
        self._refresh_color_spaces(self._current_package())

    def _load_environment_values(self) -> None:
        if self._environment is None:
            return
        if self._name_field is not None:
            self._name_field.setText(self._environment.name)
        if self._package_combo is not None and self._environment.rez_packages:
            target = self._environment.rez_packages[0]
            for index in range(self._package_combo.count()):
                spec = self._package_combo.itemData(index)
                if isinstance(spec, RezPackageSpec) and spec.name == target:
                    self._package_combo.setCurrentIndex(index)
                    break
        if self._env_table is not None:
            for key, value in self._environment.rez_environment.items():
                self._add_table_row(self._env_table, key, value)

    def _current_package(self) -> Optional[RezPackageSpec]:
        if self._package_combo is None:
            return None
        data = self._package_combo.currentData()
        return data if isinstance(data, RezPackageSpec) else None

    def _handle_package_changed(self) -> None:
        self._refresh_color_spaces(self._current_package())

    def _refresh_color_spaces(self, spec: Optional[RezPackageSpec]) -> None:
        if self._color_combo is None:
            return
        self._color_combo.clear()
        if spec is None:
            self._color_combo.addItem("パッケージを選択してください", None)
            self._color_combo.setEnabled(False)
            return

        entries = self._scan_color_spaces(spec)
        if not entries:
            self._color_combo.addItem("色空間を検出できませんでした", None)
            self._color_combo.setEnabled(False)
            return

        self._color_combo.setEnabled(True)
        for entry in entries:
            self._color_combo.addItem(entry.env_name, entry)

    def _scan_color_spaces(self, spec: RezPackageSpec) -> List[_ColorSpaceEntry]:
        names = self._scan_color_spaces_from_files(spec.path)
        entries: List[_ColorSpaceEntry] = []
        seen: set[str] = set()
        for name in names:
            env_name = self._normalize_env_var_name(name)
            if not env_name or env_name in seen:
                continue
            seen.add(env_name)
            entries.append(_ColorSpaceEntry(label=name, env_name=env_name))
        return entries

    def _scan_color_spaces_from_files(self, root: Path) -> List[str]:
        if not root.exists():
            return []
        ocio_files: List[Path] = []
        try:
            for path in root.rglob("*.ocio"):
                ocio_files.append(path)
                if len(ocio_files) >= 4:
                    break
        except OSError:
            return []

        patterns = [
            re.compile(r"colorspace\s*\"([^\"]+)\"", re.IGNORECASE),
            re.compile(r"colorspace\s*[:=]\s*\"?([^\"\n]+)\"?", re.IGNORECASE),
        ]
        results: List[str] = []
        for config in ocio_files:
            try:
                content = config.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for pattern in patterns:
                for match in pattern.finditer(content):
                    value = match.group(1).strip()
                    if value and value not in results:
                        results.append(value)
                    if len(results) >= 20:
                        break
                if len(results) >= 20:
                    break
        return results

    @staticmethod
    def _normalize_env_var_name(value: str) -> str:
        normalized = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_")
        return normalized.upper()

    @staticmethod
    def _add_table_row(table: QTableWidget, key: str = "", value: str = "") -> None:
        row = table.rowCount()
        table.insertRow(row)
        table.setItem(row, 0, QTableWidgetItem(key))
        table.setItem(row, 1, QTableWidgetItem(value))

    @staticmethod
    def _remove_table_row(table: QTableWidget) -> None:
        row = table.currentRow()
        if row < 0:
            return
        table.removeRow(row)

    def _collect_table_values(self, table: Optional[QTableWidget]) -> Dict[str, str]:
        if table is None:
            return {}
        values: Dict[str, str] = {}
        for row in range(table.rowCount()):
            key_item = table.item(row, 0)
            value_item = table.item(row, 1)
            key = key_item.text().strip() if key_item else ""
            value = value_item.text().strip() if value_item else ""
            if key:
                values[key] = value
        return values

    def _collect_arg_values(self, table: Optional[QTableWidget]) -> List[Dict[str, str]]:
        if table is None:
            return []
        values: List[Dict[str, str]] = []
        for row in range(table.rowCount()):
            key_item = table.item(row, 0)
            value_item = table.item(row, 1)
            key = key_item.text().strip() if key_item else ""
            value = value_item.text().strip() if value_item else ""
            if key or value:
                values.append({"name": key, "value": value})
        return values

    def _confirm_payload(self) -> None:
        name = self._name_field.text().strip() if self._name_field else ""
        spec = self._current_package()
        package_name = spec.name if spec is not None else ""
        color_entry = None
        if self._color_combo is not None:
            current = self._color_combo.currentData()
            if isinstance(current, _ColorSpaceEntry):
                color_entry = current
        payload: Dict[str, object] = {
            "name": name or "(未設定)",
            "package": package_name or "(未選択)",
            "color_space_env": color_entry.env_name if color_entry else "(未選択)",
            "color_space_label": color_entry.label if color_entry else "(未検出)",
            "environment_variables": self._collect_table_values(self._env_table),
            "argument_connectors": self._collect_arg_values(self._arg_table),
        }
        print("[起動環境デモ]", json.dumps(payload, ensure_ascii=False, indent=2))
        self._confirmed_payload = payload
        self.accept()


@dataclass(slots=True)
class _TableGroup:
    container: QGroupBox
    table: QTableWidget
