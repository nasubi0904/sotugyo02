"""ツール起動環境の構成ダイアログ。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from qtpy import QtCore, QtWidgets

Qt = QtCore.Qt
QAbstractItemView = QtWidgets.QAbstractItemView
QComboBox = QtWidgets.QComboBox
QDialog = QtWidgets.QDialog
QDialogButtonBox = QtWidgets.QDialogButtonBox
QFormLayout = QtWidgets.QFormLayout
QGroupBox = QtWidgets.QGroupBox
QHBoxLayout = QtWidgets.QHBoxLayout
QLabel = QtWidgets.QLabel
QLineEdit = QtWidgets.QLineEdit
QPushButton = QtWidgets.QPushButton
QTableWidget = QtWidgets.QTableWidget
QTableWidgetItem = QtWidgets.QTableWidgetItem
QTreeWidget = QtWidgets.QTreeWidget
QTreeWidgetItem = QtWidgets.QTreeWidgetItem
QVBoxLayout = QtWidgets.QVBoxLayout
QWidget = QtWidgets.QWidget

from ...domain.tooling import RegisteredTool, ToolEnvironmentDefinition, ToolEnvironmentService
from ...infrastructure.paths.storage import get_rez_package_dir


class ToolEnvironmentManagerDialog(QDialog):
    """ツール起動環境の構成を行うダイアログ。"""

    def __init__(self, service: ToolEnvironmentService, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._service = service
        self._refresh_on_accept = False
        self._environment_list: Optional[QTreeWidget] = None
        self._edit_button: Optional[QPushButton] = None

        self.setWindowTitle("ツール起動環境の構成")
        self.resize(520, 420)

        self._build_ui()

    def refresh_requested(self) -> bool:
        return self._refresh_on_accept

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        description = QLabel(
            "ツールパッケージをもとに起動環境の構成を行います。"
            "環境定義は KDMenvs で管理されます。",
            self,
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        path_label = QLabel(f"環境定義フォルダ: {self._get_environment_root()}", self)
        path_label.setObjectName("environmentPathLabel")
        layout.addWidget(path_label)

        environment_list = QTreeWidget(self)
        environment_list.setColumnCount(4)
        environment_list.setHeaderLabels(["環境名", "ツール", "バージョン", "更新日時"])
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
        add_button = QPushButton("環境を追加")
        add_button.clicked.connect(self._open_add_dialog)
        edit_button = QPushButton("選択環境を編集")
        edit_button.setEnabled(False)
        edit_button.clicked.connect(self._open_edit_dialog)
        button_row.addWidget(add_button)
        button_row.addWidget(edit_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)
        self._edit_button = edit_button

        self._refresh_environment_list()

        buttons = QDialogButtonBox(QDialogButtonBox.Close, Qt.Horizontal, self)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _get_environment_root(self) -> Path:
        rez_root = get_rez_package_dir()
        return rez_root.parent / "KDMenvs"

    def _refresh_environment_list(self) -> None:
        if self._environment_list is None:
            return
        self._environment_list.clear()
        tools = self._safe_list_tools()
        tool_map = {tool.tool_id: tool.display_name for tool in tools}
        environments = self._safe_list_environments()
        for environment in environments:
            tool_label = tool_map.get(environment.tool_id, "不明")
            updated_at = environment.updated_at.strftime("%Y-%m-%d %H:%M")
            item = QTreeWidgetItem(
                [environment.name, tool_label, environment.version_label, updated_at]
            )
            item.setData(0, Qt.UserRole, environment.environment_id)
            self._environment_list.addTopLevelItem(item)
        for column in range(3):
            self._environment_list.resizeColumnToContents(column)
        self._update_edit_button_state()

    def _safe_list_environments(self) -> List[ToolEnvironmentDefinition]:
        try:
            return self._service.list_environments()
        except OSError:
            return []

    def _safe_list_tools(self) -> List[RegisteredTool]:
        try:
            return self._service.list_tools()
        except OSError:
            return []

    def _update_edit_button_state(self) -> None:
        if self._edit_button is None or self._environment_list is None:
            return
        self._edit_button.setEnabled(self._environment_list.currentItem() is not None)

    def _open_add_dialog(self) -> None:
        dialog = ToolEnvironmentEditorDialog(self._service, parent=self)
        if dialog.exec() == QDialog.Accepted:
            self._refresh_on_accept = True
            self._refresh_environment_list()

    def _open_edit_dialog(self) -> None:
        if self._environment_list is None:
            return
        current = self._environment_list.currentItem()
        if current is None:
            return
        env_id = current.data(0, Qt.UserRole)
        if not isinstance(env_id, str):
            return
        environment = self._find_environment_by_id(env_id)
        dialog = ToolEnvironmentEditorDialog(self._service, parent=self, environment=environment)
        if dialog.exec() == QDialog.Accepted:
            self._refresh_on_accept = True
            self._refresh_environment_list()

    def _find_environment_by_id(self, environment_id: str) -> Optional[ToolEnvironmentDefinition]:
        for environment in self._safe_list_environments():
            if environment.environment_id == environment_id:
                return environment
        return None


class ToolEnvironmentEditorDialog(QDialog):
    """ツール起動環境の編集ダイアログ。"""

    def __init__(
        self,
        service: ToolEnvironmentService,
        parent: Optional[QWidget] = None,
        *,
        environment: Optional[ToolEnvironmentDefinition] = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._environment = environment
        self._tool_map: Dict[str, RegisteredTool] = {}
        self._tool_combo: Optional[QComboBox] = None
        self._color_space_combo: Optional[QComboBox] = None
        self._name_input: Optional[QLineEdit] = None
        self._version_input: Optional[QLineEdit] = None
        self._env_table: Optional[QTableWidget] = None
        self._arg_table: Optional[QTableWidget] = None

        self.setWindowTitle("起動環境の編集")
        self.resize(620, 560)
        self._build_ui()
        self._populate_from_environment()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        form_box = QGroupBox("基本情報", self)
        form_layout = QFormLayout(form_box)
        form_layout.setContentsMargins(10, 10, 10, 10)
        name_input = QLineEdit(form_box)
        form_layout.addRow("環境名", name_input)
        self._name_input = name_input

        version_input = QLineEdit(form_box)
        form_layout.addRow("バージョンラベル", version_input)
        self._version_input = version_input

        tool_combo = QComboBox(form_box)
        tool_combo.currentIndexChanged.connect(self._on_tool_changed)
        form_layout.addRow("ツールパッケージ", tool_combo)
        self._tool_combo = tool_combo

        color_space_combo = QComboBox(form_box)
        form_layout.addRow("色空間", color_space_combo)
        self._color_space_combo = color_space_combo

        layout.addWidget(form_box)

        env_box = QGroupBox("環境変数コネクタ", self)
        env_layout = QVBoxLayout(env_box)
        env_layout.setContentsMargins(10, 10, 10, 10)
        env_table = QTableWidget(0, 2, env_box)
        env_table.setHorizontalHeaderLabels(["変数名", "値"])
        env_table.horizontalHeader().setStretchLastSection(True)
        env_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        env_table.setSelectionMode(QAbstractItemView.SingleSelection)
        env_layout.addWidget(env_table)
        env_buttons = QHBoxLayout()
        add_env = QPushButton("行を追加")
        add_env.clicked.connect(self._add_env_row)
        remove_env = QPushButton("選択行を削除")
        remove_env.clicked.connect(self._remove_env_row)
        env_buttons.addWidget(add_env)
        env_buttons.addWidget(remove_env)
        env_buttons.addStretch(1)
        env_layout.addLayout(env_buttons)
        self._env_table = env_table
        layout.addWidget(env_box)

        arg_box = QGroupBox("起動引数コネクタ", self)
        arg_layout = QVBoxLayout(arg_box)
        arg_layout.setContentsMargins(10, 10, 10, 10)
        arg_table = QTableWidget(0, 1, arg_box)
        arg_table.setHorizontalHeaderLabels(["起動引数"])
        arg_table.horizontalHeader().setStretchLastSection(True)
        arg_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        arg_table.setSelectionMode(QAbstractItemView.SingleSelection)
        arg_layout.addWidget(arg_table)
        arg_buttons = QHBoxLayout()
        add_arg = QPushButton("行を追加")
        add_arg.clicked.connect(self._add_arg_row)
        remove_arg = QPushButton("選択行を削除")
        remove_arg.clicked.connect(self._remove_arg_row)
        arg_buttons.addWidget(add_arg)
        arg_buttons.addWidget(remove_arg)
        arg_buttons.addStretch(1)
        arg_layout.addLayout(arg_buttons)
        self._arg_table = arg_table
        layout.addWidget(arg_box)

        action_layout = QHBoxLayout()
        action_layout.addStretch(1)
        create_button = QPushButton("環境作成")
        create_button.clicked.connect(self._submit_environment)
        cancel_button = QPushButton("キャンセル")
        cancel_button.clicked.connect(self.reject)
        action_layout.addWidget(create_button)
        action_layout.addWidget(cancel_button)
        layout.addLayout(action_layout)

    def _populate_from_environment(self) -> None:
        tools = self._load_tools()
        if self._tool_combo is None:
            return
        if not tools:
            self._tool_combo.addItem("登録済みツールがありません", None)
            self._tool_combo.setEnabled(False)
        else:
            for tool in tools:
                self._tool_combo.addItem(tool.display_name, tool.tool_id)
        if self._environment is None:
            self._update_color_spaces()
            return
        if self._name_input is not None:
            self._name_input.setText(self._environment.name)
        if self._version_input is not None:
            self._version_input.setText(self._environment.version_label)
        self._select_tool(self._environment.tool_id)
        if self._env_table is not None:
            for key, value in self._environment.rez_environment.items():
                self._append_env_row(key, value)

    def _load_tools(self) -> List[RegisteredTool]:
        try:
            tools = self._service.list_tools()
        except OSError:
            tools = []
        self._tool_map = {tool.tool_id: tool for tool in tools}
        return tools

    def _select_tool(self, tool_id: str) -> None:
        if self._tool_combo is None:
            return
        index = self._tool_combo.findData(tool_id)
        if index >= 0:
            self._tool_combo.setCurrentIndex(index)

    def _on_tool_changed(self) -> None:
        self._update_color_spaces()

    def _update_color_spaces(self) -> None:
        if self._color_space_combo is None or self._tool_combo is None:
            return
        self._color_space_combo.blockSignals(True)
        self._color_space_combo.clear()
        tool_id = self._tool_combo.currentData()
        tool = self._tool_map.get(tool_id) if isinstance(tool_id, str) else None
        color_spaces = self._scan_color_spaces(tool)
        if not color_spaces:
            color_spaces = ["未検出"]
        for entry in color_spaces:
            self._color_space_combo.addItem(entry)
        self._color_space_combo.blockSignals(False)

    def _scan_color_spaces(self, tool: Optional[RegisteredTool]) -> List[str]:
        if tool is None:
            return []
        search_roots = [tool.executable_path.parent]
        unique = set()
        for root in search_roots:
            unique.update(self._scan_color_space_files(root))
        if unique:
            return sorted(unique)
        return ["sRGB", "Rec.709", "ACEScg"]

    def _scan_color_space_files(self, root: Path) -> List[str]:
        if not root.exists():
            return []
        entries: List[str] = []
        for item in root.glob("*.ocio"):
            if item.is_file():
                entries.append(item.stem)
        return entries

    def _add_env_row(self) -> None:
        self._append_env_row("", "")

    def _append_env_row(self, key: str, value: str) -> None:
        if self._env_table is None:
            return
        row = self._env_table.rowCount()
        self._env_table.insertRow(row)
        self._env_table.setItem(row, 0, QTableWidgetItem(key))
        self._env_table.setItem(row, 1, QTableWidgetItem(value))

    def _remove_env_row(self) -> None:
        if self._env_table is None:
            return
        row = self._env_table.currentRow()
        if row >= 0:
            self._env_table.removeRow(row)

    def _add_arg_row(self) -> None:
        if self._arg_table is None:
            return
        row = self._arg_table.rowCount()
        self._arg_table.insertRow(row)
        self._arg_table.setItem(row, 0, QTableWidgetItem(""))

    def _remove_arg_row(self) -> None:
        if self._arg_table is None:
            return
        row = self._arg_table.currentRow()
        if row >= 0:
            self._arg_table.removeRow(row)

    def _submit_environment(self) -> None:
        payload = self._build_payload()
        print("ツール起動環境データ(デモ):", payload)
        self.accept()

    def _build_payload(self) -> dict:
        env_vars: Dict[str, str] = {}
        if self._env_table is not None:
            for row in range(self._env_table.rowCount()):
                key_item = self._env_table.item(row, 0)
                value_item = self._env_table.item(row, 1)
                key = key_item.text().strip() if key_item else ""
                value = value_item.text().strip() if value_item else ""
                if key:
                    env_vars[key] = value
        args: List[str] = []
        if self._arg_table is not None:
            for row in range(self._arg_table.rowCount()):
                arg_item = self._arg_table.item(row, 0)
                if arg_item:
                    text = arg_item.text().strip()
                    if text:
                        args.append(text)
        tool_id = None
        if self._tool_combo is not None:
            data = self._tool_combo.currentData()
            if isinstance(data, str):
                tool_id = data
        color_space = None
        if self._color_space_combo is not None:
            color_space = self._color_space_combo.currentText()
        return {
            "environment_id": self._environment.environment_id if self._environment else None,
            "name": self._name_input.text().strip() if self._name_input else "",
            "version_label": self._version_input.text().strip() if self._version_input else "",
            "tool_id": tool_id,
            "color_space": color_space,
            "env": env_vars,
            "args": args,
            "timestamp": datetime.utcnow().isoformat(timespec="seconds"),
        }
