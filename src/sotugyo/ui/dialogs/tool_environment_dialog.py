"""ツール起動環境の構成ダイアログ。"""

from __future__ import annotations

from pathlib import Path
import json
import re
from typing import Dict, Iterable, List, Optional, Tuple

from qtpy import QtCore, QtWidgets

Qt = QtCore.Qt
QAbstractItemView = QtWidgets.QAbstractItemView
QComboBox = QtWidgets.QComboBox
QDialog = QtWidgets.QDialog
QDialogButtonBox = QtWidgets.QDialogButtonBox
QFormLayout = QtWidgets.QFormLayout
QGroupBox = QtWidgets.QGroupBox
QHBoxLayout = QtWidgets.QHBoxLayout
QHeaderView = QtWidgets.QHeaderView
QLabel = QtWidgets.QLabel
QLineEdit = QtWidgets.QLineEdit
QListWidget = QtWidgets.QListWidget
QListWidgetItem = QtWidgets.QListWidgetItem
QMessageBox = QtWidgets.QMessageBox
QPushButton = QtWidgets.QPushButton
QTableWidget = QtWidgets.QTableWidget
QTableWidgetItem = QtWidgets.QTableWidgetItem
QVBoxLayout = QtWidgets.QVBoxLayout
QWidget = QtWidgets.QWidget

from ...domain.tooling import RegisteredTool, ToolEnvironmentService
from ...infrastructure.paths.storage import get_tool_environment_dir


class ToolEnvironmentManagerDialog(QDialog):
    """ツール起動環境の構成を行うダイアログ。"""

    def __init__(self, service: ToolEnvironmentService, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._service = service
        self._environment_list: Optional[QListWidget] = None
        self._edit_button: Optional[QPushButton] = None
        self._status_label: Optional[QLabel] = None
        self._refresh_on_accept = False

        self.setWindowTitle("ツール起動環境の構成")
        self.resize(620, 460)

        self._build_ui()
        self._refresh_environment_list()

    def refresh_requested(self) -> bool:
        return self._refresh_on_accept

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        description = QLabel(
            "ツールパッケージに基づいた起動環境を管理します。環境定義は KDMenvs で管理されます。",
            self,
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        environment_list = QListWidget(self)
        environment_list.setSelectionMode(QAbstractItemView.SingleSelection)
        environment_list.setAlternatingRowColors(True)
        environment_list.itemSelectionChanged.connect(self._on_selection_changed)
        environment_list.itemDoubleClicked.connect(self._open_edit_dialog)
        layout.addWidget(environment_list, 1)
        self._environment_list = environment_list

        button_row = QHBoxLayout()
        add_button = QPushButton("環境を追加")
        add_button.clicked.connect(self._open_add_dialog)
        edit_button = QPushButton("選択環境を編集")
        edit_button.setEnabled(False)
        edit_button.clicked.connect(self._open_edit_dialog)
        refresh_button = QPushButton("一覧を更新")
        refresh_button.clicked.connect(self._refresh_environment_list)
        button_row.addWidget(add_button)
        button_row.addWidget(edit_button)
        button_row.addWidget(refresh_button)
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

    def _on_selection_changed(self) -> None:
        if self._edit_button is None or self._environment_list is None:
            return
        self._edit_button.setEnabled(self._environment_list.currentItem() is not None)

    def _open_add_dialog(self) -> None:
        dialog = ToolEnvironmentEditorDialog(self._service, self)
        if dialog.exec() == QDialog.Accepted:
            self._refresh_on_accept = True

    def _open_edit_dialog(self) -> None:
        if self._environment_list is None:
            return
        current = self._environment_list.currentItem()
        if current is None:
            QMessageBox.information(self, "編集", "編集する環境を選択してください。")
            return
        environment_name = current.text()
        dialog = ToolEnvironmentEditorDialog(
            self._service,
            self,
            environment_name=environment_name,
        )
        if dialog.exec() == QDialog.Accepted:
            self._refresh_on_accept = True

    def _refresh_environment_list(self) -> None:
        if self._environment_list is None:
            return
        self._environment_list.clear()
        env_dir = get_tool_environment_dir()
        try:
            env_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass

        entries = self._collect_environment_entries(env_dir)
        for entry in entries:
            item = QListWidgetItem(entry)
            item.setData(Qt.UserRole, entry)
            self._environment_list.addItem(item)

        if self._status_label is not None:
            self._status_label.setText(
                f"登録されている環境数: {len(entries)} | KDMenvs: {env_dir}"
            )

    @staticmethod
    def _collect_environment_entries(env_dir: Path) -> List[str]:
        if not env_dir.exists():
            return []
        entries: List[str] = []
        try:
            candidates = list(env_dir.iterdir())
        except OSError:
            return []
        for entry in sorted(candidates, key=lambda item: item.name.lower()):
            if entry.is_dir():
                entries.append(entry.name)
            elif entry.is_file() and entry.suffix.lower() in {".json", ".env"}:
                entries.append(entry.stem)
        return entries


class ToolEnvironmentEditorDialog(QDialog):
    """ツール起動環境の内容を編集するダイアログ。"""

    def __init__(
        self,
        service: ToolEnvironmentService,
        parent: Optional[QWidget] = None,
        *,
        environment_name: Optional[str] = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._tool_combo: Optional[QComboBox] = None
        self._colorspace_combo: Optional[QComboBox] = None
        self._colorspace_env_name: Optional[QLineEdit] = None
        self._environment_name: Optional[QLineEdit] = None
        self._env_table: Optional[QTableWidget] = None
        self._arg_table: Optional[QTableWidget] = None
        self._tools: Dict[str, RegisteredTool] = {}

        title = "起動環境の編集" if environment_name else "起動環境の追加"
        self.setWindowTitle(title)
        self.resize(700, 560)

        self._build_ui(environment_name)
        self._populate_tools()

    def _build_ui(self, environment_name: Optional[str]) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        description = QLabel(
            "ツールパッケージを指定し、環境変数と起動引数のコネクタを定義します。",
            self,
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        basic_group = QGroupBox("基本設定", self)
        basic_form = QFormLayout(basic_group)
        basic_form.setLabelAlignment(Qt.AlignLeft)

        environment_name_edit = QLineEdit(basic_group)
        if environment_name:
            environment_name_edit.setText(environment_name)
        basic_form.addRow("環境名", environment_name_edit)
        self._environment_name = environment_name_edit

        tool_combo = QComboBox(basic_group)
        tool_combo.currentIndexChanged.connect(self._on_tool_changed)
        basic_form.addRow("ツールパッケージ", tool_combo)
        self._tool_combo = tool_combo

        colorspace_combo = QComboBox(basic_group)
        colorspace_combo.currentIndexChanged.connect(self._on_colorspace_changed)
        add_colorspace_button = QPushButton("環境変数へ追加", basic_group)
        add_colorspace_button.clicked.connect(self._add_colorspace_to_env)
        colorspace_row = QWidget(basic_group)
        colorspace_layout = QHBoxLayout(colorspace_row)
        colorspace_layout.setContentsMargins(0, 0, 0, 0)
        colorspace_layout.addWidget(colorspace_combo, 1)
        colorspace_layout.addWidget(add_colorspace_button)
        basic_form.addRow("色空間", colorspace_row)
        self._colorspace_combo = colorspace_combo

        colorspace_env_name = QLineEdit(basic_group)
        colorspace_env_name.setReadOnly(True)
        basic_form.addRow("色空間の環境変数名", colorspace_env_name)
        self._colorspace_env_name = colorspace_env_name

        layout.addWidget(basic_group)

        env_group = QGroupBox("環境変数", self)
        env_layout = QVBoxLayout(env_group)
        env_table = QTableWidget(0, 2, env_group)
        env_table.setHorizontalHeaderLabels(["変数名", "値"])
        env_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        env_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        env_table.setSelectionMode(QAbstractItemView.SingleSelection)
        env_layout.addWidget(env_table)
        self._env_table = env_table

        env_button_row = QHBoxLayout()
        add_env_button = QPushButton("行を追加")
        add_env_button.clicked.connect(lambda: self._append_row(env_table))
        remove_env_button = QPushButton("行を削除")
        remove_env_button.clicked.connect(lambda: self._remove_selected_row(env_table))
        env_button_row.addWidget(add_env_button)
        env_button_row.addWidget(remove_env_button)
        env_button_row.addStretch(1)
        env_layout.addLayout(env_button_row)
        layout.addWidget(env_group)

        arg_group = QGroupBox("起動引数コネクタ", self)
        arg_layout = QVBoxLayout(arg_group)
        arg_table = QTableWidget(0, 2, arg_group)
        arg_table.setHorizontalHeaderLabels(["引数名", "値"])
        arg_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        arg_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        arg_table.setSelectionMode(QAbstractItemView.SingleSelection)
        arg_layout.addWidget(arg_table)
        self._arg_table = arg_table

        arg_button_row = QHBoxLayout()
        add_arg_button = QPushButton("行を追加")
        add_arg_button.clicked.connect(lambda: self._append_row(arg_table))
        remove_arg_button = QPushButton("行を削除")
        remove_arg_button.clicked.connect(lambda: self._remove_selected_row(arg_table))
        arg_button_row.addWidget(add_arg_button)
        arg_button_row.addWidget(remove_arg_button)
        arg_button_row.addStretch(1)
        arg_layout.addLayout(arg_button_row)
        layout.addWidget(arg_group)

        action_row = QHBoxLayout()
        action_row.addStretch(1)
        create_button = QPushButton("環境作成")
        create_button.clicked.connect(self._submit)
        cancel_button = QPushButton("キャンセル")
        cancel_button.clicked.connect(self.reject)
        action_row.addWidget(create_button)
        action_row.addWidget(cancel_button)
        layout.addLayout(action_row)

    def _populate_tools(self) -> None:
        if self._tool_combo is None:
            return
        try:
            tools = self._service.list_tools()
        except OSError as exc:
            QMessageBox.critical(self, "読み込み失敗", f"ツール一覧の取得に失敗しました: {exc}")
            tools = []
        self._tool_combo.clear()
        self._tool_combo.addItem("ツールを選択してください", None)
        self._tools = {}
        for tool in tools:
            label = tool.display_name
            if tool.version:
                label = f"{label} ({tool.version})"
            self._tool_combo.addItem(label, tool.tool_id)
            self._tools[tool.tool_id] = tool
        self._tool_combo.setEnabled(bool(tools))
        self._update_colorspaces([])

    def _on_tool_changed(self) -> None:
        if self._tool_combo is None:
            return
        tool_id = self._tool_combo.currentData()
        if not isinstance(tool_id, str):
            self._update_colorspaces([])
            return
        tool = self._tools.get(tool_id)
        if tool is None:
            self._update_colorspaces([])
            return
        colorspaces = self._scan_colorspaces(tool)
        self._update_colorspaces(colorspaces)

    def _on_colorspace_changed(self) -> None:
        if self._colorspace_combo is None or self._colorspace_env_name is None:
            return
        env_name = self._colorspace_combo.currentData()
        self._colorspace_env_name.setText(env_name or "")

    def _update_colorspaces(self, colorspaces: Iterable[Tuple[str, str]]) -> None:
        if self._colorspace_combo is None or self._colorspace_env_name is None:
            return
        self._colorspace_combo.clear()
        if not colorspaces:
            self._colorspace_combo.addItem("未検出（既定の色空間を利用）", None)
            self._colorspace_env_name.setText("")
            return
        for label, env_name in colorspaces:
            self._colorspace_combo.addItem(f"{label} ({env_name})", env_name)
        self._colorspace_combo.setCurrentIndex(0)
        self._colorspace_env_name.setText(self._colorspace_combo.currentData() or "")

    def _scan_colorspaces(self, tool: RegisteredTool) -> List[Tuple[str, str]]:
        executable = Path(tool.executable_path)
        if not executable.exists():
            return []
        search_dirs = [
            executable.parent,
            executable.parent / "color",
            executable.parent / "colorspaces",
            executable.parent / "config",
            executable.parent / "resources",
            executable.parent / "ocio",
        ]
        extensions = {".ocio", ".cube", ".icc", ".icm"}
        names: List[str] = []
        for directory in search_dirs:
            if not directory.exists() or not directory.is_dir():
                continue
            try:
                entries = list(directory.iterdir())
            except OSError:
                continue
            for entry in entries:
                if not entry.is_file():
                    continue
                if entry.suffix.lower() not in extensions:
                    continue
                names.append(entry.stem)
        unique_names = sorted({name for name in names if name})
        return [(name, self._to_env_name(name)) for name in unique_names]

    @staticmethod
    def _to_env_name(name: str) -> str:
        cleaned = re.sub(r"[^0-9A-Za-z]+", "_", name).strip("_")
        if not cleaned:
            return "COLORSPACE"
        return f"COLORSPACE_{cleaned.upper()}"

    def _add_colorspace_to_env(self) -> None:
        if self._colorspace_combo is None or self._env_table is None:
            return
        env_name = self._colorspace_combo.currentData()
        label = self._colorspace_combo.currentText()
        if not env_name:
            QMessageBox.information(self, "色空間", "追加する色空間が見つかりませんでした。")
            return
        self._append_row(self._env_table, values=(env_name, label))

    @staticmethod
    def _append_row(table: QTableWidget, values: Tuple[str, str] | None = None) -> None:
        row = table.rowCount()
        table.insertRow(row)
        for column in range(table.columnCount()):
            value = values[column] if values and column < len(values) else ""
            table.setItem(row, column, QTableWidgetItem(value))

    @staticmethod
    def _remove_selected_row(table: QTableWidget) -> None:
        row = table.currentRow()
        if row < 0:
            return
        table.removeRow(row)

    def _collect_table_data(self, table: QTableWidget) -> List[Tuple[str, str]]:
        rows: List[Tuple[str, str]] = []
        for row in range(table.rowCount()):
            key_item = table.item(row, 0)
            value_item = table.item(row, 1)
            key = key_item.text().strip() if key_item else ""
            value = value_item.text().strip() if value_item else ""
            if key or value:
                rows.append((key, value))
        return rows

    def _submit(self) -> None:
        name = self._environment_name.text().strip() if self._environment_name else ""
        if not name:
            QMessageBox.warning(self, "入力不足", "環境名を入力してください。")
            return
        tool_id = self._tool_combo.currentData() if self._tool_combo else None
        tool = self._tools.get(tool_id) if isinstance(tool_id, str) else None
        colorspace_label = self._colorspace_combo.currentText() if self._colorspace_combo else ""
        colorspace_env = self._colorspace_combo.currentData() if self._colorspace_combo else None
        env_rows = self._collect_table_data(self._env_table) if self._env_table else []
        arg_rows = self._collect_table_data(self._arg_table) if self._arg_table else []

        payload = {
            "name": name,
            "tool": {
                "tool_id": tool.tool_id if tool else None,
                "display_name": tool.display_name if tool else None,
                "executable": str(tool.executable_path) if tool else None,
            },
            "colorspace": {
                "label": colorspace_label,
                "env_name": colorspace_env,
            },
            "environment_variables": {key: value for key, value in env_rows if key},
            "argument_connectors": [
                {"name": key, "value": value} for key, value in arg_rows if key
            ],
        }

        print("[起動環境データ]\n" + json.dumps(payload, ensure_ascii=False, indent=2))
        self.accept()
