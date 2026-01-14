"""ツール起動環境の構成ダイアログ。"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterable, List, Optional

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
QMessageBox = QtWidgets.QMessageBox
QPushButton = QtWidgets.QPushButton
QTreeWidget = QtWidgets.QTreeWidget
QTreeWidgetItem = QtWidgets.QTreeWidgetItem
QVBoxLayout = QtWidgets.QVBoxLayout
QWidget = QtWidgets.QWidget

from ...domain.tooling import RegisteredTool, ToolEnvironmentDefinition, ToolEnvironmentService


class ToolEnvironmentManagerDialog(QDialog):
    """ツール起動環境の構成を行うダイアログ。"""

    def __init__(self, service: ToolEnvironmentService, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._service = service
        self._refresh_on_accept = False
        self._environment_list: Optional[QTreeWidget] = None
        self._edit_button: Optional[QPushButton] = None
        self._status_label: Optional[QLabel] = None

        self.setWindowTitle("ツール起動環境の構成")
        self.resize(640, 480)

        self._build_ui()
        self._refresh_environment_list()

    def refresh_requested(self) -> bool:
        return self._refresh_on_accept

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        description = QLabel(
            "登録済みツールを基に起動環境ノード用の定義を作成します。",
            self,
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        environment_list = QTreeWidget(self)
        environment_list.setColumnCount(4)
        environment_list.setHeaderLabels(["環境名", "ツール", "バージョン", "最終更新"])
        environment_list.setRootIsDecorated(False)
        environment_list.setAlternatingRowColors(True)
        environment_list.setSelectionMode(QAbstractItemView.SingleSelection)
        environment_list.setSelectionBehavior(QAbstractItemView.SelectRows)
        environment_list.setUniformRowHeights(True)
        environment_list.setAllColumnsShowFocus(True)
        environment_list.itemSelectionChanged.connect(self._on_selection_changed)
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

        tool_map = {tool.tool_id: tool for tool in tools}
        self._environment_list.clear()
        for environment in environments:
            tool = tool_map.get(environment.tool_id)
            tool_label = tool.display_name if tool else environment.tool_id
            updated = environment.updated_at.strftime("%Y-%m-%d %H:%M")
            item = QTreeWidgetItem(
                [
                    environment.name,
                    tool_label,
                    environment.version_label or "-",
                    updated,
                ]
            )
            item.setData(0, Qt.UserRole, environment.environment_id)
            self._environment_list.addTopLevelItem(item)

        for index in range(3):
            self._environment_list.resizeColumnToContents(index)

        if self._status_label is not None:
            self._status_label.setText(f"登録されている環境数: {len(environments)}")
        self._on_selection_changed()

    def _on_selection_changed(self) -> None:
        if self._edit_button is None or self._environment_list is None:
            return
        has_selection = self._environment_list.currentItem() is not None
        self._edit_button.setEnabled(has_selection)

    def _open_add_dialog(self) -> None:
        dialog = ToolEnvironmentEditorDialog(self._service, self)
        if dialog.exec() == QDialog.Accepted:
            self._refresh_on_accept = True
            self._refresh_environment_list()

    def _open_edit_dialog(self) -> None:
        if self._environment_list is None:
            return
        current = self._environment_list.currentItem()
        if current is None:
            QMessageBox.information(self, "編集", "編集する環境を選択してください。")
            return
        environment_id = current.data(0, Qt.UserRole)
        if not isinstance(environment_id, str):
            return
        try:
            environments = self._service.list_environments()
        except OSError as exc:
            QMessageBox.critical(self, "エラー", f"環境の読み込みに失敗しました: {exc}")
            return
        target = next(
            (env for env in environments if env.environment_id == environment_id),
            None,
        )
        if target is None:
            QMessageBox.warning(self, "編集", "指定された環境が見つかりませんでした。")
            return

        dialog = ToolEnvironmentEditorDialog(self._service, self, environment=target)
        if dialog.exec() == QDialog.Accepted:
            self._refresh_on_accept = True
            self._refresh_environment_list()


class ToolEnvironmentEditorDialog(QDialog):
    """起動環境を新規作成・編集するダイアログ。"""

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
        self._tools: List[RegisteredTool] = []
        self._tool_combo: Optional[QComboBox] = None
        self._color_combo: Optional[QComboBox] = None
        self._name_input: Optional[QLineEdit] = None
        self._env_var_name_input: Optional[QLineEdit] = None
        self._env_value_input: Optional[QLineEdit] = None
        self._arg_connector_input: Optional[QLineEdit] = None
        self._arg_value_input: Optional[QLineEdit] = None

        title = "起動環境を編集" if environment else "起動環境を追加"
        self.setWindowTitle(title)
        self.resize(560, 420)

        self._build_ui()
        self._load_tools()
        self._apply_environment()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        description = QLabel("環境変数と起動引数のコネクタを定義します。", self)
        description.setWordWrap(True)
        layout.addWidget(description)

        form_box = QGroupBox("基本情報", self)
        form_layout = QFormLayout(form_box)
        form_layout.setLabelAlignment(Qt.AlignLeft)
        form_layout.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        form_layout.setHorizontalSpacing(12)
        form_layout.setVerticalSpacing(8)

        name_input = QLineEdit(form_box)
        name_input.setPlaceholderText("例: Nuke 用 ACES 環境")
        form_layout.addRow("環境名", name_input)
        self._name_input = name_input

        tool_combo = QComboBox(form_box)
        tool_combo.currentIndexChanged.connect(self._update_color_spaces)
        form_layout.addRow("ツールパッケージ", tool_combo)
        self._tool_combo = tool_combo

        color_combo = QComboBox(form_box)
        color_combo.currentIndexChanged.connect(self._on_color_space_changed)
        form_layout.addRow("色空間", color_combo)
        self._color_combo = color_combo

        layout.addWidget(form_box)

        env_box = QGroupBox("環境変数", self)
        env_layout = QFormLayout(env_box)
        env_layout.setHorizontalSpacing(12)
        env_layout.setVerticalSpacing(8)

        env_name_input = QLineEdit(env_box)
        env_name_input.setPlaceholderText("例: OCIO_COLORSPACE")
        env_layout.addRow("環境変数名", env_name_input)
        self._env_var_name_input = env_name_input

        env_value_input = QLineEdit(env_box)
        env_value_input.setPlaceholderText("色空間名が自動入力されます")
        env_layout.addRow("環境変数値", env_value_input)
        self._env_value_input = env_value_input

        layout.addWidget(env_box)

        arg_box = QGroupBox("起動引数", self)
        arg_layout = QFormLayout(arg_box)
        arg_layout.setHorizontalSpacing(12)
        arg_layout.setVerticalSpacing(8)

        arg_connector_input = QLineEdit(arg_box)
        arg_connector_input.setPlaceholderText("例: --colorspace")
        arg_layout.addRow("起動引数コネクタ", arg_connector_input)
        self._arg_connector_input = arg_connector_input

        arg_value_input = QLineEdit(arg_box)
        arg_value_input.setPlaceholderText("例: ACEScg")
        arg_layout.addRow("起動引数値", arg_value_input)
        self._arg_value_input = arg_value_input

        layout.addWidget(arg_box)
        layout.addStretch(1)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        create_button = QPushButton("環境を作成")
        create_button.clicked.connect(self._emit_demo_payload)
        cancel_button = QPushButton("キャンセル")
        cancel_button.clicked.connect(self.reject)
        button_row.addWidget(create_button)
        button_row.addWidget(cancel_button)
        layout.addLayout(button_row)

    def _load_tools(self) -> None:
        if self._tool_combo is None:
            return
        try:
            self._tools = self._service.list_tools()
        except OSError as exc:
            QMessageBox.critical(self, "エラー", f"ツール一覧の取得に失敗しました: {exc}")
            self._tools = []

        self._tool_combo.clear()
        if not self._tools:
            self._tool_combo.addItem("ツール環境設定でツールを登録してください")
            self._tool_combo.setEnabled(False)
            return

        self._tool_combo.setEnabled(True)
        for tool in self._tools:
            label = tool.display_name
            if tool.version:
                label = f"{label} ({tool.version})"
            self._tool_combo.addItem(label, tool.tool_id)

        self._update_color_spaces()

    def _apply_environment(self) -> None:
        if self._environment is None:
            return
        if self._name_input is not None:
            self._name_input.setText(self._environment.name)
        if self._tool_combo is not None:
            index = self._tool_combo.findData(self._environment.tool_id)
            if index >= 0:
                self._tool_combo.setCurrentIndex(index)

    def _update_color_spaces(self) -> None:
        if self._tool_combo is None or self._color_combo is None:
            return
        tool_id = self._tool_combo.currentData()
        if not isinstance(tool_id, str):
            self._color_combo.clear()
            return
        tool = next((entry for entry in self._tools if entry.tool_id == tool_id), None)
        if tool is None:
            self._color_combo.clear()
            return

        color_spaces = self._scan_color_spaces(tool)
        self._color_combo.clear()
        if not color_spaces:
            self._color_combo.addItem("検出なし")
            self._color_combo.setEnabled(False)
            if self._env_value_input is not None:
                self._env_value_input.setText("")
            return

        self._color_combo.setEnabled(True)
        for name in color_spaces:
            self._color_combo.addItem(name)
        self._color_combo.setCurrentIndex(0)
        self._on_color_space_changed()

    def _on_color_space_changed(self) -> None:
        if self._color_combo is None or self._env_value_input is None:
            return
        if not self._color_combo.isEnabled():
            return
        self._env_value_input.setText(self._color_combo.currentText())

    def _scan_color_spaces(self, tool: RegisteredTool) -> List[str]:
        search_roots = self._collect_color_space_roots(tool.executable_path)
        names: set[str] = set()
        for root in search_roots:
            for path in self._iter_color_space_files(root, max_depth=3):
                env_name = self._normalize_color_space_name(path.stem)
                if env_name:
                    names.add(env_name)
        return sorted(names)

    def _collect_color_space_roots(self, executable_path: Path) -> List[Path]:
        base_dir = executable_path.parent
        candidates = [
            base_dir,
            base_dir / "resources",
            base_dir / "ocio",
            base_dir / "color",
            base_dir / "colorspace",
            base_dir / "colorspaces",
            base_dir / "color_spaces",
            base_dir / "color-management",
            base_dir / "config",
        ]
        return [path for path in candidates if path.exists()]

    def _iter_color_space_files(self, root: Path, *, max_depth: int) -> Iterable[Path]:
        extensions = {".ocio", ".cube", ".clf", ".ccc", ".cc"}
        root = root.resolve()
        for current_root, dirs, files in os.walk(root):
            current_path = Path(current_root)
            depth = len(current_path.relative_to(root).parts)
            if depth > max_depth:
                dirs[:] = []
                continue
            for filename in files:
                path = current_path / filename
                if path.suffix.lower() in extensions:
                    yield path

    @staticmethod
    def _normalize_color_space_name(name: str) -> str:
        normalized = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_")
        return normalized.upper()

    def _emit_demo_payload(self) -> None:
        payload = {
            "name": self._name_input.text() if self._name_input else "",
            "tool_id": self._current_tool_id(),
            "color_space": self._color_combo.currentText()
            if self._color_combo and self._color_combo.isEnabled()
            else "",
            "env_var_name": self._env_var_name_input.text() if self._env_var_name_input else "",
            "env_var_value": self._env_value_input.text() if self._env_value_input else "",
            "arg_connector": self._arg_connector_input.text()
            if self._arg_connector_input
            else "",
            "arg_value": self._arg_value_input.text() if self._arg_value_input else "",
        }
        print("[起動環境デモ]", payload)
        self.accept()

    def _current_tool_id(self) -> str:
        if self._tool_combo is None:
            return ""
        tool_id = self._tool_combo.currentData()
        return tool_id if isinstance(tool_id, str) else ""
