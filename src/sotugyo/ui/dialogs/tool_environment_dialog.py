"""ツール起動環境の構成ダイアログ。"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
from typing import Iterable, Optional

from qtpy import QtCore, QtWidgets

from ...domain.tooling import ToolEnvironmentService

Qt = QtCore.Qt
QAbstractItemView = QtWidgets.QAbstractItemView
QCheckBox = QtWidgets.QCheckBox
QComboBox = QtWidgets.QComboBox
QDialog = QtWidgets.QDialog
QDialogButtonBox = QtWidgets.QDialogButtonBox
QFormLayout = QtWidgets.QFormLayout
QGroupBox = QtWidgets.QGroupBox
QHBoxLayout = QtWidgets.QHBoxLayout
QHeaderView = QtWidgets.QHeaderView
QLabel = QtWidgets.QLabel
QLineEdit = QtWidgets.QLineEdit
QPlainTextEdit = QtWidgets.QPlainTextEdit
QPushButton = QtWidgets.QPushButton
QSplitter = QtWidgets.QSplitter
QTableWidget = QtWidgets.QTableWidget
QTableWidgetItem = QtWidgets.QTableWidgetItem
QTextEdit = QtWidgets.QTextEdit
QVBoxLayout = QtWidgets.QVBoxLayout
QWidget = QtWidgets.QWidget


@dataclass(slots=True)
class ConnectorRowData:
    key: str
    flag: str
    value_type: str
    required: bool
    default: str
    form: str
    multiple: bool
    multi_mode: str
    dedupe: str
    empty_policy: str
    quote_policy: str
    description: str


class ToolEnvironmentManagerDialog(QDialog):
    """ツール起動環境の構成を行うダイアログ。"""

    _SCHEMA_VERSION = "args_schema_version: 1"

    _TYPE_OPTIONS = (
        "string",
        "path",
        "bool",
        "int",
        "float",
        "enum",
        "list(path)",
        "list(string)",
    )
    _FORM_OPTIONS = ("flag_value", "equals", "flag_only", "positional")
    _MULTI_MODE_OPTIONS = (
        "repeat_flag",
        "join_os_pathsep",
        "join_comma",
        "join_space",
    )
    _DEDUPE_OPTIONS = ("last_wins", "first_wins", "error")
    _EMPTY_POLICY_OPTIONS = ("omit", "use_default", "error")
    _QUOTE_POLICY_OPTIONS = ("none", "auto", "always")

    def __init__(
        self, service: ToolEnvironmentService, parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._refresh_on_accept = False
        self._auto_id_enabled = True
        self._existing_ids = self._collect_existing_ids()

        self.setWindowTitle("ツール起動環境の構成")
        self.resize(1080, 720)

        self._build_ui()
        self._refresh_preview()

    def refresh_requested(self) -> bool:
        return self._refresh_on_accept

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        layout.addWidget(self._build_header())
        layout.addWidget(self._build_editor_splitter(), 1)
        layout.addWidget(self._build_footer())

    def _build_header(self) -> QWidget:
        header_box = QGroupBox("環境ノード情報", self)
        header_layout = QVBoxLayout(header_box)
        header_layout.setContentsMargins(12, 12, 12, 12)
        header_layout.setSpacing(8)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form.setFormAlignment(Qt.AlignTop)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)

        self._display_name_input = QLineEdit(header_box)
        self._display_name_input.setPlaceholderText("例: Maya 2023 起動環境")
        self._display_name_input.textChanged.connect(self._handle_display_name_changed)
        form.addRow("環境ノード名", self._display_name_input)

        self._node_id_input = QLineEdit(header_box)
        self._node_id_input.setPlaceholderText("例: maya2023_env")
        self._node_id_input.textEdited.connect(self._handle_node_id_manual)

        self._node_id_state = QLabel("自動生成待ち", header_box)
        self._node_id_state.setStyleSheet("color: #999;")
        self._node_id_regen = QPushButton("自動生成", header_box)
        self._node_id_regen.clicked.connect(self._regenerate_node_id)
        node_id_layout = QHBoxLayout()
        node_id_layout.setContentsMargins(0, 0, 0, 0)
        node_id_layout.addWidget(self._node_id_input, 1)
        node_id_layout.addWidget(self._node_id_regen)
        node_id_wrapper = QWidget(header_box)
        node_id_wrapper.setLayout(node_id_layout)
        form.addRow("ノードID", node_id_wrapper)
        form.addRow("", self._node_id_state)

        self._package_input = QComboBox(header_box)
        self._package_input.setEditable(True)
        self._package_input.addItems(self._collect_rez_packages())
        self._package_input.setInsertPolicy(QComboBox.InsertAtTop)
        self._package_input.currentTextChanged.connect(self._refresh_validation_state)
        form.addRow("対象原子パッケージ", self._package_input)

        self._description_input = QPlainTextEdit(header_box)
        self._description_input.setPlaceholderText("必要に応じて説明やメモを記入してください。")
        self._description_input.setFixedHeight(60)
        form.addRow("説明/メモ", self._description_input)

        self._schema_label = QLabel(self._SCHEMA_VERSION, header_box)
        form.addRow("スキーマバージョン", self._schema_label)

        header_layout.addLayout(form)

        header_layout.addWidget(self._build_header_actions())
        return header_box

    def _build_header_actions(self) -> QWidget:
        actions = QWidget(self)
        action_layout = QHBoxLayout(actions)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(8)

        self._save_button = QPushButton("保存（カタログ登録）", actions)
        self._save_button.clicked.connect(self._notify_not_implemented)
        self._draft_button = QPushButton("下書き保存", actions)
        self._draft_button.clicked.connect(self._notify_not_implemented)
        self._load_button = QPushButton("読み込み（既存テンプレ編集）", actions)
        self._load_button.clicked.connect(self._notify_not_implemented)
        self._validate_button = QPushButton("検証（Validate）", actions)
        self._validate_button.clicked.connect(self._validate_current)
        self._diff_button = QPushButton("差分表示（任意）", actions)
        self._diff_button.clicked.connect(self._notify_not_implemented)

        action_layout.addWidget(self._save_button)
        action_layout.addWidget(self._draft_button)
        action_layout.addWidget(self._load_button)
        action_layout.addStretch(1)
        action_layout.addWidget(self._validate_button)
        action_layout.addWidget(self._diff_button)
        return actions

    def _build_editor_splitter(self) -> QWidget:
        splitter = QSplitter(Qt.Horizontal, self)
        splitter.addWidget(self._build_rez_commands_panel())
        splitter.addWidget(self._build_args_panel())
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        return splitter

    def _build_rez_commands_panel(self) -> QWidget:
        panel = QWidget(self)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        title = QLabel("Rez commands 編集（環境変数）", panel)
        title.setStyleSheet("font-weight: bold;")
        layout.addWidget(title)

        description = QLabel(
            "固定的な環境（PATH/プラグイン探索など）を定義。"
            "起動ごとに変わる値は原則ここに入れない。",
            panel,
        )
        description.setWordWrap(True)
        description.setStyleSheet("color: #666;")
        layout.addWidget(description)

        hint = QLabel("この欄は Rez package.py の commands() に反映されます。", panel)
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self._rez_commands_editor = QPlainTextEdit(panel)
        self._rez_commands_editor.setPlaceholderText(
            "例: env.PATH.prepend(\"C:/tool/bin\")\n"
            "    env.MAYA_MODULE_PATH.append(\"C:/modules\")"
        )
        self._rez_commands_editor.textChanged.connect(self._refresh_validation_state)
        layout.addWidget(self._rez_commands_editor, 1)

        snippet_row = QHBoxLayout()
        snippet_row.setSpacing(6)
        snippet_row.addWidget(self._snippet_button("prepend", 'env.PATH.prepend("C:/path")'))
        snippet_row.addWidget(self._snippet_button("append", 'env.PATH.append("C:/path")'))
        snippet_row.addWidget(self._snippet_button("set", 'env.MY_ENV.set("value")'))
        snippet_row.addWidget(self._snippet_button("unset", "env.MY_ENV.unset()"))
        snippet_row.addStretch(1)
        layout.addLayout(snippet_row)
        return panel

    def _build_args_panel(self) -> QWidget:
        panel = QWidget(self)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        title = QLabel("起動引数コネクタ定義", panel)
        title.setStyleSheet("font-weight: bold;")
        layout.addWidget(title)

        description = QLabel(
            "起動ごとに変わる値（proj/scene/mode等）を入力として定義。"
            "起動時にノードグラフから値を集めて組み立てる。",
            panel,
        )
        description.setWordWrap(True)
        description.setStyleSheet("color: #666;")
        layout.addWidget(description)

        self._detail_toggle = QCheckBox("詳細モードを表示", panel)
        self._detail_toggle.setChecked(False)
        self._detail_toggle.toggled.connect(self._toggle_detail_mode)
        layout.addWidget(self._detail_toggle)

        self._connectors_table = QTableWidget(0, 12, panel)
        self._connectors_table.setHorizontalHeaderLabels(
            [
                "key",
                "flag",
                "type",
                "required",
                "default",
                "form",
                "multiple",
                "multi_mode",
                "dedupe",
                "empty_policy",
                "quote_policy",
                "description",
            ]
        )
        self._connectors_table.verticalHeader().setVisible(False)
        self._connectors_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._connectors_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._connectors_table.setEditTriggers(
            QAbstractItemView.DoubleClicked | QAbstractItemView.SelectedClicked
        )
        self._connectors_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeToContents
        )
        self._connectors_table.horizontalHeader().setStretchLastSection(True)
        self._connectors_table.cellChanged.connect(self._refresh_preview)
        layout.addWidget(self._connectors_table, 1)

        actions = QHBoxLayout()
        actions.setSpacing(6)
        add_button = QPushButton("追加", panel)
        add_button.clicked.connect(self._add_connector_row)
        duplicate_button = QPushButton("複製", panel)
        duplicate_button.clicked.connect(self._duplicate_connector_row)
        delete_button = QPushButton("削除", panel)
        delete_button.clicked.connect(self._delete_connector_row)
        move_up_button = QPushButton("上へ", panel)
        move_up_button.clicked.connect(lambda: self._move_connector_row(-1))
        move_down_button = QPushButton("下へ", panel)
        move_down_button.clicked.connect(lambda: self._move_connector_row(1))
        actions.addWidget(add_button)
        actions.addWidget(duplicate_button)
        actions.addWidget(delete_button)
        actions.addWidget(move_up_button)
        actions.addWidget(move_down_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        preview_label = QLabel("プレビュー（組み立て後の引数列）", panel)
        preview_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(preview_label)

        self._preview_output = QTextEdit(panel)
        self._preview_output.setReadOnly(True)
        self._preview_output.setFixedHeight(110)
        layout.addWidget(self._preview_output)

        self._toggle_detail_mode(False)
        self._add_connector_row()
        return panel

    def _build_footer(self) -> QWidget:
        footer = QWidget(self)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.setSpacing(8)
        footer_layout.addStretch(1)

        close_buttons = QDialogButtonBox(QDialogButtonBox.Close, Qt.Horizontal, footer)
        close_buttons.rejected.connect(self.reject)
        footer_layout.addWidget(close_buttons)
        return footer

    def _snippet_button(self, label: str, text: str) -> QPushButton:
        button = QPushButton(label, self)
        button.clicked.connect(lambda: self._insert_snippet(text))
        return button

    def _insert_snippet(self, text: str) -> None:
        cursor = self._rez_commands_editor.textCursor()
        if cursor.atBlockStart() and cursor.block().text():
            cursor.insertText("\n")
        cursor.insertText(text)
        cursor.insertText("\n")
        self._rez_commands_editor.setTextCursor(cursor)

    def _add_connector_row(self, data: Optional[ConnectorRowData] = None) -> None:
        row = self._connectors_table.rowCount()
        self._connectors_table.insertRow(row)
        row_data = data or ConnectorRowData(
            key="",
            flag="",
            value_type="string",
            required=False,
            default="",
            form="flag_value",
            multiple=False,
            multi_mode="",
            dedupe="last_wins",
            empty_policy="omit",
            quote_policy="auto",
            description="",
        )
        self._set_text_item(row, 0, row_data.key)
        self._set_text_item(row, 1, row_data.flag)
        self._set_combo_cell(row, 2, row_data.value_type, self._TYPE_OPTIONS)
        self._set_check_item(row, 3, row_data.required)
        self._set_text_item(row, 4, row_data.default)
        self._set_combo_cell(row, 5, row_data.form, self._FORM_OPTIONS)
        self._set_check_item(row, 6, row_data.multiple)
        self._set_combo_cell(
            row, 7, row_data.multi_mode, ("",) + self._MULTI_MODE_OPTIONS
        )
        self._set_combo_cell(row, 8, row_data.dedupe, self._DEDUPE_OPTIONS)
        self._set_combo_cell(row, 9, row_data.empty_policy, self._EMPTY_POLICY_OPTIONS)
        self._set_combo_cell(
            row, 10, row_data.quote_policy, self._QUOTE_POLICY_OPTIONS
        )
        self._set_text_item(row, 11, row_data.description)

    def _duplicate_connector_row(self) -> None:
        row = self._current_row()
        if row is None:
            return
        self._add_connector_row(self._read_row_data(row))

    def _delete_connector_row(self) -> None:
        row = self._current_row()
        if row is None:
            return
        self._connectors_table.removeRow(row)
        self._refresh_preview()

    def _move_connector_row(self, offset: int) -> None:
        row = self._current_row()
        if row is None:
            return
        target = row + offset
        if target < 0 or target >= self._connectors_table.rowCount():
            return
        current_data = self._read_row_data(row)
        target_data = self._read_row_data(target)
        self._apply_row_data(row, target_data)
        self._apply_row_data(target, current_data)
        self._connectors_table.selectRow(target)
        self._refresh_preview()

    def _toggle_detail_mode(self, enabled: bool) -> None:
        advanced_columns = (8, 9, 10, 11)
        for column in advanced_columns:
            self._connectors_table.setColumnHidden(column, not enabled)

    def _set_text_item(self, row: int, column: int, text: str) -> None:
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() | Qt.ItemIsEditable)
        self._connectors_table.setItem(row, column, item)

    def _set_check_item(self, row: int, column: int, checked: bool) -> None:
        item = QTableWidgetItem()
        item.setFlags(
            Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable
        )
        item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
        self._connectors_table.setItem(row, column, item)

    def _set_combo_cell(
        self, row: int, column: int, current: str, options: Iterable[str]
    ) -> None:
        combo = QComboBox(self._connectors_table)
        combo.addItems(list(options))
        if current in options:
            combo.setCurrentText(current)
        else:
            combo.setCurrentText(options[0])
        combo.currentTextChanged.connect(self._refresh_preview)
        self._connectors_table.setCellWidget(row, column, combo)

    def _current_row(self) -> Optional[int]:
        selection = self._connectors_table.selectionModel()
        if not selection:
            return None
        indexes = selection.selectedRows()
        if not indexes:
            return None
        return indexes[0].row()

    def _read_row_data(self, row: int) -> ConnectorRowData:
        return ConnectorRowData(
            key=self._read_text(row, 0),
            flag=self._read_text(row, 1),
            value_type=self._read_combo(row, 2),
            required=self._read_checked(row, 3),
            default=self._read_text(row, 4),
            form=self._read_combo(row, 5),
            multiple=self._read_checked(row, 6),
            multi_mode=self._read_combo(row, 7),
            dedupe=self._read_combo(row, 8),
            empty_policy=self._read_combo(row, 9),
            quote_policy=self._read_combo(row, 10),
            description=self._read_text(row, 11),
        )

    def _apply_row_data(self, row: int, data: ConnectorRowData) -> None:
        self._set_text_item(row, 0, data.key)
        self._set_text_item(row, 1, data.flag)
        self._set_combo_cell(row, 2, data.value_type, self._TYPE_OPTIONS)
        self._set_check_item(row, 3, data.required)
        self._set_text_item(row, 4, data.default)
        self._set_combo_cell(row, 5, data.form, self._FORM_OPTIONS)
        self._set_check_item(row, 6, data.multiple)
        self._set_combo_cell(row, 7, data.multi_mode, ("",) + self._MULTI_MODE_OPTIONS)
        self._set_combo_cell(row, 8, data.dedupe, self._DEDUPE_OPTIONS)
        self._set_combo_cell(row, 9, data.empty_policy, self._EMPTY_POLICY_OPTIONS)
        self._set_combo_cell(row, 10, data.quote_policy, self._QUOTE_POLICY_OPTIONS)
        self._set_text_item(row, 11, data.description)

    def _read_text(self, row: int, column: int) -> str:
        item = self._connectors_table.item(row, column)
        return item.text().strip() if item else ""

    def _read_checked(self, row: int, column: int) -> bool:
        item = self._connectors_table.item(row, column)
        return bool(item and item.checkState() == Qt.Checked)

    def _read_combo(self, row: int, column: int) -> str:
        widget = self._connectors_table.cellWidget(row, column)
        if isinstance(widget, QComboBox):
            return widget.currentText().strip()
        return ""

    def _collect_existing_ids(self) -> set[str]:
        environments = self._service.list_environments()
        return {env.environment_id for env in environments if env.environment_id}

    def _collect_rez_packages(self) -> list[str]:
        packages = self._service.list_rez_packages()
        names = sorted({package.name for package in packages})
        return names

    def _handle_display_name_changed(self, text: str) -> None:
        if not self._auto_id_enabled:
            return
        self._node_id_input.setText(self._generate_node_id(text))
        self._refresh_validation_state()

    def _handle_node_id_manual(self, _text: str) -> None:
        self._auto_id_enabled = False
        self._refresh_validation_state()

    def _regenerate_node_id(self) -> None:
        self._auto_id_enabled = True
        self._node_id_input.setText(self._generate_node_id(self._display_name_input.text()))
        self._refresh_validation_state()

    def _generate_node_id(self, text: str) -> str:
        normalized = re.sub(r"\s+", "_", text.strip().lower())
        normalized = re.sub(r"[^a-z0-9_]+", "", normalized)
        return normalized or "environment_node"

    def _refresh_validation_state(self) -> None:
        node_id = self._node_id_input.text().strip()
        if not node_id:
            self._node_id_state.setText("ノードIDを入力してください。")
            self._node_id_state.setStyleSheet("color: #c0392b;")
            return
        if node_id in self._existing_ids:
            self._node_id_state.setText("既存のノードIDと重複しています。")
            self._node_id_state.setStyleSheet("color: #e67e22;")
            return
        self._node_id_state.setText("ノードIDは使用可能です。")
        self._node_id_state.setStyleSheet("color: #27ae60;")

    def _validate_current(self) -> None:
        header_errors, header_warnings = self._validate_header()
        connector_errors, connector_warnings = self._validate_connectors()
        errors = header_errors + connector_errors
        warnings = header_warnings + connector_warnings
        message = []
        if errors:
            message.append("エラー:")
            message.extend(f"  - {item}" for item in errors)
        if warnings:
            if message:
                message.append("")
            message.append("警告:")
            message.extend(f"  - {item}" for item in warnings)
        if not message:
            message.append("重大な問題は見つかりませんでした。")
        QtWidgets.QMessageBox.information(self, "検証結果", "\n".join(message))

    def _validate_header(self) -> tuple[list[str], list[str]]:
        errors: list[str] = []
        warnings: list[str] = []
        if not self._display_name_input.text().strip():
            errors.append("環境ノード名が未入力です。")
        node_id = self._node_id_input.text().strip()
        if not node_id:
            errors.append("ノードIDが未入力です。")
        elif node_id in self._existing_ids:
            errors.append("ノードIDが既存定義と重複しています。")
        package_name = self._package_input.currentText().strip()
        if not package_name:
            errors.append("対象原子パッケージが未入力です。")
        elif package_name not in self._collect_rez_packages():
            warnings.append("対象原子パッケージが一覧に存在しません。")
        return errors, warnings

    def _validate_connectors(self) -> tuple[list[str], list[str]]:
        errors: list[str] = []
        warnings: list[str] = []
        for row in range(self._connectors_table.rowCount()):
            data = self._read_row_data(row)
            label = data.key or f"行 {row + 1}"
            if not data.key:
                warnings.append(f"{label}: key が未入力です。")
            if not data.flag and data.form != "positional":
                warnings.append(f"{label}: flag が未入力です。")
            if data.value_type == "bool" and data.form != "flag_only":
                warnings.append(f"{label}: bool 型は flag_only 以外が警告対象です。")
            if data.multiple and not data.multi_mode:
                errors.append(f"{label}: multiple=true に対して multi_mode が未指定です。")
            if data.required and not data.default:
                warnings.append(f"{label}: required=true かつ default が未設定です。")
        return errors, warnings

    def _refresh_preview(self) -> None:
        preview = self._build_preview_tokens()
        payload = {
            "args_connectors_json": self._export_connectors_json(),
            "preview": preview,
        }
        formatted = json.dumps(payload, ensure_ascii=False, indent=2)
        self._preview_output.setPlainText(formatted)

    def _build_preview_tokens(self) -> list[str]:
        tokens: list[str] = []
        for row in range(self._connectors_table.rowCount()):
            data = self._read_row_data(row)
            value = self._preview_value_for(data)
            tokens.extend(self._format_tokens(data, value))
        return tokens

    def _preview_value_for(self, data: ConnectorRowData) -> object:
        if data.default:
            if data.value_type.startswith("list"):
                return [entry.strip() for entry in data.default.split(",") if entry.strip()]
            return data.default
        if data.value_type in ("int", "float"):
            return "1"
        if data.value_type == "bool":
            return True
        if data.value_type.startswith("list"):
            return ["A", "B"]
        if data.value_type == "path":
            return "/path/to/item"
        return "value"

    def _format_tokens(self, data: ConnectorRowData, value: object) -> list[str]:
        if data.form == "flag_only":
            return [data.flag] if value else []
        if data.multiple and isinstance(value, list):
            return self._format_multi_tokens(data, value)
        return self._apply_form(data, self._format_value(value, data.quote_policy))

    def _format_multi_tokens(self, data: ConnectorRowData, values: list[object]) -> list[str]:
        if data.multi_mode == "repeat_flag":
            tokens: list[str] = []
            for entry in values:
                tokens.extend(
                    self._apply_form(
                        data, self._format_value(entry, data.quote_policy)
                    )
                )
            return tokens
        if data.multi_mode == "join_os_pathsep":
            joined = os.pathsep.join(
                self._format_value(entry, data.quote_policy, raw=True) for entry in values
            )
            return self._apply_form(data, self._format_value(joined, data.quote_policy))
        if data.multi_mode == "join_comma":
            joined = ",".join(
                self._format_value(entry, data.quote_policy, raw=True) for entry in values
            )
            return self._apply_form(data, self._format_value(joined, data.quote_policy))
        if data.multi_mode == "join_space":
            joined = " ".join(
                self._format_value(entry, data.quote_policy, raw=True) for entry in values
            )
            return self._apply_form(data, self._format_value(joined, data.quote_policy))
        return self._apply_form(data, self._format_value(values[0], data.quote_policy))

    def _apply_form(self, data: ConnectorRowData, value: str) -> list[str]:
        if data.form == "positional":
            return [value]
        flag = data.flag or "<flag>"
        if data.form == "equals":
            return [f"{flag}={value}"]
        return [flag, value]

    def _format_value(self, value: object, policy: str, *, raw: bool = False) -> str:
        text = str(value)
        if raw:
            return text
        if policy == "always":
            return f"\"{text}\""
        if policy == "auto" and re.search(r"\s", text):
            return f"\"{text}\""
        return text

    def _export_connectors_json(self) -> list[dict[str, object]]:
        connectors = []
        for row in range(self._connectors_table.rowCount()):
            data = self._read_row_data(row)
            connectors.append(
                {
                    "key": data.key,
                    "flag": data.flag,
                    "type": data.value_type,
                    "required": data.required,
                    "default": data.default,
                    "form": data.form,
                    "multiple": data.multiple,
                    "multi_mode": data.multi_mode or None,
                    "dedupe": data.dedupe,
                    "empty_policy": data.empty_policy,
                    "quote_policy": data.quote_policy,
                    "description": data.description,
                }
            )
        return connectors

    def _notify_not_implemented(self) -> None:
        QtWidgets.QMessageBox.information(
            self,
            "未実装",
            "保存や読み込みは後続の実装で対応します。UI では入力内容のみ編集できます。",
        )
