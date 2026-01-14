"""ツール起動環境の構成ダイアログ。"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
from typing import Iterable, Optional

from qtpy import QtCore, QtWidgets

Qt = QtCore.Qt
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
QVBoxLayout = QtWidgets.QVBoxLayout
QWidget = QtWidgets.QWidget

from ...domain.tooling import ToolEnvironmentService


SCHEMA_VERSION_LABEL = "args_schema_version: 1"


@dataclass(frozen=True)
class _ConnectorColumn:
    key: str
    label: str
    width: int
    advanced: bool
    kind: str
    options: tuple[str, ...] = ()


class ToolEnvironmentManagerDialog(QDialog):
    """ツール起動環境の構成を行うダイアログ。"""

    _CONNECTOR_COLUMNS: tuple[_ConnectorColumn, ...] = (
        _ConnectorColumn("key", "key", 140, False, "text"),
        _ConnectorColumn("flag", "flag", 140, False, "text"),
        _ConnectorColumn(
            "type",
            "type",
            120,
            False,
            "combo",
            (
                "string",
                "path",
                "bool",
                "int",
                "float",
                "enum",
                "list(path)",
                "list(string)",
            ),
        ),
        _ConnectorColumn("required", "必須", 70, False, "check"),
        _ConnectorColumn("default", "default", 180, False, "text"),
        _ConnectorColumn(
            "form",
            "form",
            140,
            False,
            "combo",
            ("flag_value", "equals", "flag_only", "positional"),
        ),
        _ConnectorColumn("multiple", "multiple", 90, False, "check"),
        _ConnectorColumn(
            "multi_mode",
            "multi_mode",
            160,
            False,
            "combo",
            ("repeat_flag", "join_os_pathsep", "join_comma", "join_space"),
        ),
        _ConnectorColumn(
            "dedupe",
            "dedupe",
            120,
            True,
            "combo",
            ("last_wins", "first_wins", "error"),
        ),
        _ConnectorColumn(
            "empty_policy",
            "empty_policy",
            140,
            True,
            "combo",
            ("omit", "use_default", "error"),
        ),
        _ConnectorColumn(
            "quote_policy",
            "quote_policy",
            120,
            True,
            "combo",
            ("none", "auto", "always"),
        ),
        _ConnectorColumn("description", "description", 220, True, "text"),
    )

    def __init__(self, service: ToolEnvironmentService, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._service = service
        self._refresh_on_accept = False
        self._node_id_auto = True
        self._rez_package_names: list[str] = []

        self.setWindowTitle("ツール起動環境の構成")
        self.resize(1180, 720)

        self._build_ui()

    def refresh_requested(self) -> bool:
        return self._refresh_on_accept

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        header = self._build_header()
        layout.addWidget(header)

        splitter = QSplitter(Qt.Horizontal, self)
        splitter.addWidget(self._build_rez_editor())
        splitter.addWidget(self._build_args_editor())
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Close, Qt.Horizontal, self)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _build_header(self) -> QGroupBox:
        group = QGroupBox("環境ノード情報", self)
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)

        self._display_name_input = QLineEdit(group)
        self._display_name_input.setPlaceholderText("例: Maya 2023 起動環境")
        self._display_name_input.textChanged.connect(self._handle_display_name_changed)
        form.addRow("環境ノード名", self._display_name_input)

        node_id_row = QWidget(group)
        node_id_layout = QHBoxLayout(node_id_row)
        node_id_layout.setContentsMargins(0, 0, 0, 0)
        node_id_layout.setSpacing(6)
        self._node_id_input = QLineEdit(node_id_row)
        self._node_id_input.setPlaceholderText("例: maya2023_env")
        self._node_id_input.textEdited.connect(self._handle_node_id_edited)
        node_id_layout.addWidget(self._node_id_input, 1)
        node_id_button = QPushButton("自動生成", node_id_row)
        node_id_button.clicked.connect(self._regenerate_node_id)
        node_id_layout.addWidget(node_id_button)
        form.addRow("ノードID", node_id_row)

        node_id_hint = QLabel("※重複チェック必須（保存時に検証）", group)
        node_id_hint.setStyleSheet("color: #777; font-size: 11px;")
        form.addRow("", node_id_hint)

        self._target_package_input = QComboBox(group)
        self._target_package_input.setEditable(True)
        self._target_package_input.setInsertPolicy(QComboBox.NoInsert)
        self._reload_rez_packages()
        form.addRow("対象原子パッケージ", self._target_package_input)

        target_hint = QLabel("候補一覧から選択、または手入力可能（存在チェックを実施）", group)
        target_hint.setStyleSheet("color: #777; font-size: 11px;")
        form.addRow("", target_hint)

        self._description_input = QPlainTextEdit(group)
        self._description_input.setPlaceholderText("任意: 用途や注意点のメモ")
        self._description_input.setFixedHeight(70)
        form.addRow("説明/メモ", self._description_input)

        self._schema_version_label = QLabel(f"{SCHEMA_VERSION_LABEL}（自動）", group)
        form.addRow("スキーマバージョン", self._schema_version_label)

        layout.addLayout(form)

        action_row = QHBoxLayout()
        action_row.addStretch(1)
        self._save_button = QPushButton("保存（カタログ登録）", group)
        self._save_button.clicked.connect(self._show_not_implemented)
        action_row.addWidget(self._save_button)
        self._draft_button = QPushButton("下書き保存", group)
        self._draft_button.clicked.connect(self._show_not_implemented)
        action_row.addWidget(self._draft_button)
        self._load_button = QPushButton("読み込み（既存テンプレ編集）", group)
        self._load_button.clicked.connect(self._show_not_implemented)
        action_row.addWidget(self._load_button)
        self._validate_button = QPushButton("検証（Validate）", group)
        self._validate_button.clicked.connect(self._validate_all)
        action_row.addWidget(self._validate_button)
        self._diff_button = QPushButton("差分表示", group)
        self._diff_button.clicked.connect(self._show_not_implemented)
        action_row.addWidget(self._diff_button)
        layout.addLayout(action_row)

        return group

    def _build_rez_editor(self) -> QGroupBox:
        group = QGroupBox("Rez commands 編集", self)
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        description = QLabel(
            "固定的な環境（PATH/プラグイン探索など）を定義します。\n"
            "起動ごとに変わる値は原則ここに入れないでください。\n"
            "この欄は Rez package.py の commands() に反映されます。",
            group,
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        snippet_row = QHBoxLayout()
        snippet_row.addWidget(QLabel("テンプレ挿入:", group))
        for label, snippet in (
            ("set", "env[\"VAR\"] = \"value\""),
            ("append", "env.append(\"VAR\", \"value\")"),
            ("prepend", "env.prepend(\"VAR\", \"value\")"),
            ("unset", "env.unset(\"VAR\")"),
        ):
            button = QPushButton(label, group)
            button.clicked.connect(lambda _checked, text=snippet: self._insert_rez_snippet(text))
            snippet_row.addWidget(button)
        snippet_row.addStretch(1)
        layout.addLayout(snippet_row)

        self._rez_commands_editor = QPlainTextEdit(group)
        self._rez_commands_editor.setPlaceholderText("# commands() 本文を入力")
        layout.addWidget(self._rez_commands_editor, 1)

        warning = QLabel("空欄でも保存可能です。危険な上書き（PATH 直指定など）は警告対象です。", group)
        warning.setStyleSheet("color: #777; font-size: 11px;")
        warning.setWordWrap(True)
        layout.addWidget(warning)

        return group

    def _build_args_editor(self) -> QGroupBox:
        group = QGroupBox("起動引数コネクタ定義", self)
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        description = QLabel(
            "起動ごとに変わる値（proj/scene/mode 等）を入力として定義します。\n"
            "ノードグラフの値を集めて起動引数へ組み立てます。",
            group,
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        controls = QHBoxLayout()
        add_button = QPushButton("追加", group)
        add_button.clicked.connect(self._add_connector_row)
        controls.addWidget(add_button)
        duplicate_button = QPushButton("複製", group)
        duplicate_button.clicked.connect(self._duplicate_connector_row)
        controls.addWidget(duplicate_button)
        remove_button = QPushButton("削除", group)
        remove_button.clicked.connect(self._remove_connector_row)
        controls.addWidget(remove_button)
        move_up_button = QPushButton("上へ", group)
        move_up_button.clicked.connect(lambda: self._move_connector_row(-1))
        controls.addWidget(move_up_button)
        move_down_button = QPushButton("下へ", group)
        move_down_button.clicked.connect(lambda: self._move_connector_row(1))
        controls.addWidget(move_down_button)
        controls.addStretch(1)

        self._detail_mode_toggle = QCheckBox("詳細モード", group)
        self._detail_mode_toggle.toggled.connect(self._toggle_detail_mode)
        controls.addWidget(self._detail_mode_toggle)
        layout.addLayout(controls)

        self._connector_table = QTableWidget(group)
        self._connector_table.setColumnCount(len(self._CONNECTOR_COLUMNS))
        self._connector_table.setHorizontalHeaderLabels(
            [column.label for column in self._CONNECTOR_COLUMNS]
        )
        self._connector_table.verticalHeader().setVisible(False)
        self._connector_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._connector_table.setSelectionMode(QTableWidget.SingleSelection)
        self._connector_table.setEditTriggers(
            QTableWidget.DoubleClicked
            | QTableWidget.EditKeyPressed
            | QTableWidget.AnyKeyPressed
        )
        header = self._connector_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        for idx, column in enumerate(self._CONNECTOR_COLUMNS):
            header.resizeSection(idx, column.width)
        self._connector_table.itemChanged.connect(self._on_connector_item_changed)
        layout.addWidget(self._connector_table, 1)

        preview_group = QGroupBox("プレビュー", group)
        preview_layout = QVBoxLayout(preview_group)
        preview_layout.setSpacing(6)
        preview_controls = QHBoxLayout()
        preview_controls.addStretch(1)
        preview_button = QPushButton("引数プレビュー更新", preview_group)
        preview_button.clicked.connect(self._rebuild_preview)
        preview_controls.addWidget(preview_button)
        preview_layout.addLayout(preview_controls)
        self._args_preview = QPlainTextEdit(preview_group)
        self._args_preview.setReadOnly(True)
        self._args_preview.setPlaceholderText("生成される引数列がここに表示されます")
        preview_layout.addWidget(self._args_preview)

        self._json_preview = QPlainTextEdit(preview_group)
        self._json_preview.setReadOnly(True)
        self._json_preview.setPlaceholderText("コメント JSON として保存される定義")
        self._json_preview.setFixedHeight(120)
        preview_layout.addWidget(QLabel("コメント JSON（固定スキーマ）", preview_group))
        preview_layout.addWidget(self._json_preview)

        layout.addWidget(preview_group)

        self._toggle_detail_mode(False)
        self._add_connector_row()
        return group

    def _reload_rez_packages(self) -> None:
        self._target_package_input.clear()
        try:
            packages = self._service.list_rez_packages()
        except Exception:
            packages = []
        self._rez_package_names = [spec.name for spec in packages]
        self._target_package_input.addItems(self._rez_package_names)

    def _handle_display_name_changed(self, value: str) -> None:
        if not self._node_id_auto:
            return
        self._node_id_input.setText(self._slugify(value))

    def _handle_node_id_edited(self) -> None:
        self._node_id_auto = False

    def _regenerate_node_id(self) -> None:
        self._node_id_auto = True
        self._node_id_input.setText(self._slugify(self._display_name_input.text()))

    def _slugify(self, value: str) -> str:
        normalized = re.sub(r"[^a-zA-Z0-9_]+", "_", value.strip())
        normalized = normalized.strip("_").lower()
        return normalized or "environment_node"

    def _insert_rez_snippet(self, snippet: str) -> None:
        cursor = self._rez_commands_editor.textCursor()
        if not cursor.atStart():
            cursor.insertText("\n")
        cursor.insertText(snippet)
        self._rez_commands_editor.setTextCursor(cursor)

    def _toggle_detail_mode(self, enabled: bool) -> None:
        for idx, column in enumerate(self._CONNECTOR_COLUMNS):
            if column.advanced:
                self._connector_table.setColumnHidden(idx, not enabled)

    def _add_connector_row(self) -> None:
        row = self._connector_table.rowCount()
        self._connector_table.blockSignals(True)
        self._connector_table.insertRow(row)
        for column_index, column in enumerate(self._CONNECTOR_COLUMNS):
            if column.kind == "check":
                item = QTableWidgetItem()
                item.setFlags(
                    Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable
                )
                item.setCheckState(Qt.Unchecked)
                self._connector_table.setItem(row, column_index, item)
            elif column.kind == "combo":
                combo = QComboBox(self._connector_table)
                combo.addItems(column.options)
                combo.currentIndexChanged.connect(self._on_connector_combo_changed)
                self._connector_table.setCellWidget(row, column_index, combo)
            else:
                item = QTableWidgetItem("")
                self._connector_table.setItem(row, column_index, item)
        self._connector_table.blockSignals(False)
        self._rebuild_preview()

    def _duplicate_connector_row(self) -> None:
        row = self._current_row()
        if row is None:
            return
        data = self._read_row(row)
        self._add_connector_row()
        self._apply_row_data(self._connector_table.rowCount() - 1, data)
        self._rebuild_preview()

    def _remove_connector_row(self) -> None:
        row = self._current_row()
        if row is None:
            return
        self._connector_table.removeRow(row)
        self._rebuild_preview()

    def _move_connector_row(self, delta: int) -> None:
        row = self._current_row()
        if row is None:
            return
        target = row + delta
        if target < 0 or target >= self._connector_table.rowCount():
            return
        current = self._read_row(row)
        destination = self._read_row(target)
        self._apply_row_data(row, destination)
        self._apply_row_data(target, current)
        self._connector_table.selectRow(target)
        self._rebuild_preview()

    def _current_row(self) -> Optional[int]:
        selection = self._connector_table.selectionModel()
        if selection is None or not selection.hasSelection():
            return None
        return selection.selectedRows()[0].row()

    def _read_row(self, row: int) -> dict[str, object]:
        data: dict[str, object] = {}
        for column_index, column in enumerate(self._CONNECTOR_COLUMNS):
            if column.kind == "check":
                item = self._connector_table.item(row, column_index)
                data[column.key] = bool(item and item.checkState() == Qt.Checked)
            elif column.kind == "combo":
                widget = self._connector_table.cellWidget(row, column_index)
                if isinstance(widget, QComboBox):
                    data[column.key] = widget.currentText()
                else:
                    data[column.key] = ""
            else:
                item = self._connector_table.item(row, column_index)
                data[column.key] = item.text().strip() if item else ""
        return data

    def _apply_row_data(self, row: int, data: dict[str, object]) -> None:
        self._connector_table.blockSignals(True)
        for column_index, column in enumerate(self._CONNECTOR_COLUMNS):
            value = data.get(column.key, "")
            if column.kind == "check":
                item = self._connector_table.item(row, column_index)
                if item is None:
                    item = QTableWidgetItem()
                    self._connector_table.setItem(row, column_index, item)
                item.setFlags(
                    Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable
                )
                item.setCheckState(Qt.Checked if value else Qt.Unchecked)
            elif column.kind == "combo":
                widget = self._connector_table.cellWidget(row, column_index)
                if isinstance(widget, QComboBox):
                    index = widget.findText(str(value))
                    widget.setCurrentIndex(index if index >= 0 else 0)
            else:
                item = self._connector_table.item(row, column_index)
                if item is None:
                    item = QTableWidgetItem()
                    self._connector_table.setItem(row, column_index, item)
                item.setText(str(value))
        self._connector_table.blockSignals(False)

    def _on_connector_item_changed(self, _item: QTableWidgetItem) -> None:
        self._rebuild_preview()

    def _on_connector_combo_changed(self) -> None:
        self._rebuild_preview()

    def _collect_connectors(self) -> list[dict[str, object]]:
        connectors: list[dict[str, object]] = []
        for row in range(self._connector_table.rowCount()):
            row_data = self._read_row(row)
            connectors.append(row_data)
        return connectors

    def _rebuild_preview(self) -> None:
        connectors = self._collect_connectors()
        args, warnings = self._build_args_preview(connectors)
        warning_text = "".join(f"⚠ {message}\n" for message in warnings)
        arg_line = " ".join(args)
        self._args_preview.setPlainText(f"{warning_text}{arg_line}")

        json_payload = json.dumps(connectors, ensure_ascii=False, indent=2)
        self._json_preview.setPlainText(json_payload)

    def _build_args_preview(self, connectors: Iterable[dict[str, object]]) -> tuple[list[str], list[str]]:
        args: list[str] = []
        warnings: list[str] = []
        for index, connector in enumerate(connectors, start=1):
            key = str(connector.get("key", "")).strip()
            flag = str(connector.get("flag", "")).strip()
            value_type = str(connector.get("type", "")).strip()
            required = bool(connector.get("required", False))
            default = str(connector.get("default", "")).strip()
            form = str(connector.get("form", "")).strip()
            multiple = bool(connector.get("multiple", False))
            multi_mode = str(connector.get("multi_mode", "")).strip()
            empty_policy = str(connector.get("empty_policy", "omit")).strip() or "omit"
            quote_policy = str(connector.get("quote_policy", "none")).strip() or "none"

            if not key:
                warnings.append(f"{index}行目: key が未入力です。")
            if required and not default:
                warnings.append(f"{index}行目: 必須入力に default がありません。")
            if value_type == "bool" and form and form != "flag_only":
                warnings.append(f"{index}行目: bool は flag_only を推奨します。")
            if multiple and not multi_mode:
                warnings.append(f"{index}行目: multiple=true なのに multi_mode が未設定です。")

            if not default:
                if required and empty_policy != "omit":
                    warnings.append(f"{index}行目: 必須入力が空です。")
                if empty_policy == "omit":
                    continue

            values = self._coerce_values(default, multiple, value_type)
            if not values:
                if empty_policy == "error":
                    warnings.append(f"{index}行目: 空入力はエラー扱いです。")
                continue

            if multiple:
                args.extend(
                    self._render_multiple_values(flag, values, form, multi_mode, quote_policy)
                )
            else:
                args.extend(self._render_single_value(flag, values[0], form, quote_policy))
        return args, warnings

    def _coerce_values(self, value: str, multiple: bool, value_type: str) -> list[str]:
        if multiple or value_type.startswith("list"):
            values = [entry.strip() for entry in value.split(",") if entry.strip()]
            return values
        return [value]

    def _render_single_value(
        self, flag: str, value: str, form: str, quote_policy: str
    ) -> list[str]:
        rendered = self._apply_quote_policy(value, quote_policy)
        if form == "equals":
            return [f"{flag}={rendered}" if flag else rendered]
        if form == "flag_only":
            return [flag] if self._truthy(value) else []
        if form == "positional" or not flag:
            return [rendered]
        return [flag, rendered]

    def _render_multiple_values(
        self,
        flag: str,
        values: Iterable[str],
        form: str,
        multi_mode: str,
        quote_policy: str,
    ) -> list[str]:
        rendered_values = [self._apply_quote_policy(val, quote_policy) for val in values]
        if multi_mode == "repeat_flag":
            rendered: list[str] = []
            for value in rendered_values:
                rendered.extend(self._render_single_value(flag, value, form, quote_policy))
            return rendered
        if multi_mode == "join_os_pathsep":
            joined = os.pathsep.join(rendered_values)
        elif multi_mode == "join_space":
            joined = " ".join(rendered_values)
        else:
            joined = ",".join(rendered_values)
        return self._render_single_value(flag, joined, form, quote_policy)

    def _apply_quote_policy(self, value: str, policy: str) -> str:
        if policy == "always":
            return f"\"{value}\""
        if policy == "auto" and " " in value:
            return f"\"{value}\""
        return value

    def _truthy(self, value: str) -> bool:
        return value.strip().lower() in {"1", "true", "yes", "on"}

    def _show_not_implemented(self) -> None:
        QtWidgets.QMessageBox.information(
            self,
            "未実装",
            "この操作は UI 実装のみのため未実装です。",
        )

    def _validate_all(self) -> None:
        errors: list[str] = []
        warnings: list[str] = []

        display_name = self._display_name_input.text().strip()
        node_id = self._node_id_input.text().strip()
        target_package = self._target_package_input.currentText().strip()

        if not display_name:
            errors.append("環境ノード名が未入力です。")
        if not node_id:
            errors.append("ノードIDが未入力です。")
        elif not re.match(r"^[a-z0-9_]+$", node_id):
            warnings.append("ノードIDは英小文字・数字・アンダースコア推奨です。")

        if not target_package:
            errors.append("対象原子パッケージが未入力です。")
        elif self._rez_package_names and target_package not in self._rez_package_names:
            warnings.append("対象原子パッケージが候補一覧に存在しません。")

        existing_ids = {env.environment_id for env in self._service.list_environments()}
        if node_id and node_id in existing_ids:
            errors.append("ノードIDが既存定義と重複しています。")

        connectors = self._collect_connectors()
        for index, connector in enumerate(connectors, start=1):
            key = str(connector.get("key", "")).strip()
            flag = str(connector.get("flag", "")).strip()
            value_type = str(connector.get("type", "")).strip()
            form = str(connector.get("form", "")).strip()
            default = str(connector.get("default", "")).strip()
            required = bool(connector.get("required", False))
            multiple = bool(connector.get("multiple", False))
            multi_mode = str(connector.get("multi_mode", "")).strip()

            if not key:
                errors.append(f"{index}行目: key が未入力です。")
            if not value_type:
                errors.append(f"{index}行目: type が未入力です。")
            if form != "positional" and not flag:
                errors.append(f"{index}行目: positional 以外は flag が必須です。")
            if required and not default:
                errors.append(f"{index}行目: required=true なのに default がありません。")
            if multiple and not multi_mode:
                errors.append(f"{index}行目: multiple=true なのに multi_mode が未指定です。")
            if value_type == "bool" and form and form != "flag_only":
                warnings.append(f"{index}行目: bool は flag_only が推奨です。")

        rez_commands = self._rez_commands_editor.toPlainText()
        if "PATH" in rez_commands and "=" in rez_commands:
            warnings.append("Rez commands 内で PATH の上書きが検出されました。")

        self._show_validation_result(errors, warnings)

    def _show_validation_result(self, errors: Iterable[str], warnings: Iterable[str]) -> None:
        error_text = "\n".join(f"・{message}" for message in errors)
        warning_text = "\n".join(f"・{message}" for message in warnings)
        if errors:
            message = "検証エラーが見つかりました。\n\n" + error_text
            if warnings:
                message += "\n\n警告:\n" + warning_text
            QtWidgets.QMessageBox.warning(self, "検証エラー", message)
            return

        if warnings:
            message = "検証は完了しましたが、警告があります。\n\n" + warning_text
            QtWidgets.QMessageBox.warning(self, "検証警告", message)
            return

        QtWidgets.QMessageBox.information(self, "検証完了", "検証は成功しました。")
