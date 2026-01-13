"""ツール起動環境の構成ダイアログ。"""

from __future__ import annotations

from typing import Optional

from qtpy import QtCore, QtGui, QtWidgets

Qt = QtCore.Qt
QAbstractItemView = QtWidgets.QAbstractItemView
QComboBox = QtWidgets.QComboBox
QDialog = QtWidgets.QDialog
QDialogButtonBox = QtWidgets.QDialogButtonBox
QFont = QtGui.QFont
QFormLayout = QtWidgets.QFormLayout
QFrame = QtWidgets.QFrame
QGroupBox = QtWidgets.QGroupBox
QHBoxLayout = QtWidgets.QHBoxLayout
QHeaderView = QtWidgets.QHeaderView
QLabel = QtWidgets.QLabel
QLineEdit = QtWidgets.QLineEdit
QMessageBox = QtWidgets.QMessageBox
QPlainTextEdit = QtWidgets.QPlainTextEdit
QPushButton = QtWidgets.QPushButton
QSplitter = QtWidgets.QSplitter
QTableWidget = QtWidgets.QTableWidget
QTableWidgetItem = QtWidgets.QTableWidgetItem
QTabWidget = QtWidgets.QTabWidget
QVBoxLayout = QtWidgets.QVBoxLayout
QWidget = QtWidgets.QWidget

from ...domain.tooling import ToolEnvironmentService


class ToolEnvironmentManagerDialog(QDialog):
    """ツール起動環境の構成を行うダイアログ。"""

    def __init__(self, service: ToolEnvironmentService, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._service = service
        self._refresh_on_accept = False
        self._rez_editor: Optional[QPlainTextEdit] = None
        self._rez_line_numbers: Optional[QPlainTextEdit] = None
        self._package_combo: Optional[QComboBox] = None
        self._name_edit: Optional[QLineEdit] = None
        self._desc_edit: Optional[QLineEdit] = None
        self._author_edit: Optional[QLineEdit] = None
        self._preview_output: Optional[QPlainTextEdit] = None
        self._raw_json_editor: Optional[QPlainTextEdit] = None

        self.setWindowTitle("ツール起動環境の構成")
        self.setModal(True)
        self.resize(1120, 760)

        self._build_ui()

    def refresh_requested(self) -> bool:
        return self._refresh_on_accept

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        title = QLabel("ツール起動環境の構成", self)
        title.setProperty("class", "dialog-title")
        subtitle = QLabel(
            "ワークフロー設計者向けに、Rez 環境と起動引数テンプレを編集してノードカタログへ登録します。",
            self,
        )
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        layout.addWidget(self._build_target_panel())

        tabs = QTabWidget(self)
        tabs.addTab(self._build_rez_tab(), "Rez commands (環境)")
        tabs.addTab(self._build_args_tab(), "起動引数コネクタ")
        layout.addWidget(tabs, 1)

        layout.addWidget(self._build_footer())

        self._update_rez_line_numbers()

    def _build_target_panel(self) -> QWidget:
        panel = QGroupBox("保存単位 (ツール起動環境ノード定義)", self)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(12, 10, 12, 12)
        panel_layout.setSpacing(8)

        form = QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)

        package_row = QHBoxLayout()
        self._package_combo = QComboBox(panel)
        self._package_combo.setEditable(True)
        self._package_combo.setInsertPolicy(QComboBox.NoInsert)
        self._package_combo.lineEdit().setPlaceholderText("例: maya2023")
        self._package_combo.addItem("maya2023")
        self._package_combo.addItem("houdini20")
        self._package_combo.addItem("nuke14")
        self._package_combo.setToolTip("原子パッケージ名を選択または入力します。")
        package_row.addWidget(self._package_combo, 1)
        package_row.addWidget(QPushButton("検索", panel))
        package_row.addWidget(QPushButton("候補一覧", panel))
        form.addRow("原子パッケージ", package_row)

        self._name_edit = QLineEdit(panel)
        self._name_edit.setPlaceholderText("ノードカタログで表示する名前")
        form.addRow("テンプレ名", self._name_edit)

        self._desc_edit = QLineEdit(panel)
        self._desc_edit.setPlaceholderText("用途や注意事項を短く記載")
        form.addRow("説明", self._desc_edit)

        meta_row = QHBoxLayout()
        schema_label = QLabel("schema_version: 1", panel)
        updated_label = QLabel("最終更新: -", panel)
        self._author_edit = QLineEdit(panel)
        self._author_edit.setPlaceholderText("作成者")
        meta_row.addWidget(schema_label)
        meta_row.addWidget(updated_label)
        meta_row.addStretch(1)
        meta_row.addWidget(QLabel("作成者", panel))
        meta_row.addWidget(self._author_edit)
        form.addRow("メタ情報", meta_row)

        panel_layout.addLayout(form)
        return panel

    def _build_rez_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        hint = QLabel(
            "ここは Rez 環境 (commands) の編集領域です。起動引数の定義は別タブで行います。",
            tab,
        )
        hint.setWordWrap(True)
        hint.setProperty("class", "info")
        layout.addWidget(hint)

        search_row = QHBoxLayout()
        search_edit = QLineEdit(tab)
        search_edit.setPlaceholderText("検索")
        search_row.addWidget(search_edit, 1)
        search_row.addWidget(QPushButton("検索", tab))
        search_row.addWidget(QPushButton("前へ", tab))
        search_row.addWidget(QPushButton("次へ", tab))
        search_row.addWidget(QPushButton("コピー", tab))
        layout.addLayout(search_row)

        editor_frame = QFrame(tab)
        editor_frame.setFrameShape(QFrame.StyledPanel)
        editor_layout = QHBoxLayout(editor_frame)
        editor_layout.setContentsMargins(6, 6, 6, 6)
        editor_layout.setSpacing(6)

        line_numbers = QPlainTextEdit(editor_frame)
        line_numbers.setReadOnly(True)
        line_numbers.setFixedWidth(48)
        line_numbers.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        line_numbers.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        line_numbers.setStyleSheet("background: #1f1f1f; color: #888; border: none;")

        rez_editor = QPlainTextEdit(editor_frame)
        rez_editor.setPlaceholderText(
            "Rez commands() 相当の内容を入力します。\n例:\n  env.MAYA_MODULE_PATH.append('{root}/modules')"
        )
        rez_editor.setLineWrapMode(QPlainTextEdit.NoWrap)
        rez_editor.textChanged.connect(self._update_rez_line_numbers)

        mono_font = QFont("Consolas")
        mono_font.setStyleHint(QFont.Monospace)
        rez_editor.setFont(mono_font)
        line_numbers.setFont(mono_font)

        editor_layout.addWidget(line_numbers)
        editor_layout.addWidget(rez_editor, 1)

        layout.addWidget(editor_frame, 1)

        warning = QLabel(
            "※ 起動引数で同名の環境変数を扱う場合は、衝突に注意してください。",
            tab,
        )
        warning.setWordWrap(True)
        warning.setProperty("class", "warning")
        layout.addWidget(warning)

        self._rez_editor = rez_editor
        self._rez_line_numbers = line_numbers

        return tab

    def _build_args_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        description = QLabel(
            "起動引数のテンプレ定義を編集します。Rez 化せず、コメント JSON として保存されます。",
            tab,
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        splitter = QSplitter(Qt.Vertical, tab)

        upper_splitter = QSplitter(Qt.Horizontal, splitter)
        upper_splitter.addWidget(self._build_connectors_table())
        upper_splitter.addWidget(self._build_connector_details())
        upper_splitter.setStretchFactor(0, 3)
        upper_splitter.setStretchFactor(1, 2)

        lower_panel = QWidget(splitter)
        lower_layout = QVBoxLayout(lower_panel)
        lower_layout.setContentsMargins(0, 0, 0, 0)
        lower_layout.setSpacing(10)
        lower_layout.addWidget(self._build_preview_box())
        lower_layout.addWidget(self._build_raw_json_box())

        splitter.addWidget(upper_splitter)
        splitter.addWidget(lower_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        layout.addWidget(splitter, 1)
        return tab

    def _build_connectors_table(self) -> QWidget:
        panel = QWidget(self)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        header_row = QHBoxLayout()
        header_row.addWidget(QLabel("起動引数コネクタ一覧", panel))
        header_row.addStretch(1)
        header_row.addWidget(QPushButton("追加", panel))
        header_row.addWidget(QPushButton("複製", panel))
        header_row.addWidget(QPushButton("削除", panel))
        header_row.addWidget(QPushButton("上へ", panel))
        header_row.addWidget(QPushButton("下へ", panel))
        layout.addLayout(header_row)

        table = QTableWidget(0, 7, panel)
        table.setHorizontalHeaderLabels(
            ["flag", "type", "form", "multiple", "required", "default", "multi_mode"]
        )
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        example_row = [
            QTableWidgetItem("-proj"),
            QTableWidgetItem("path"),
            QTableWidgetItem("flag_value"),
            QTableWidgetItem("false"),
            QTableWidgetItem("true"),
            QTableWidgetItem(""),
            QTableWidgetItem(""),
        ]
        table.setRowCount(1)
        for col, item in enumerate(example_row):
            table.setItem(0, col, item)

        layout.addWidget(table, 1)
        return panel

    def _build_connector_details(self) -> QWidget:
        panel = QGroupBox("選択中コネクタ詳細", self)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(8)

        form = QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)

        flag_edit = QLineEdit(panel)
        flag_edit.setPlaceholderText("例: -proj / --project / (positional の場合は空)")
        form.addRow("flag", flag_edit)

        type_combo = QComboBox(panel)
        type_combo.addItems(["string", "path", "bool", "int", "float", "enum", "pathlist"])
        form.addRow("type", type_combo)

        form_combo = QComboBox(panel)
        form_combo.addItems(["flag_value", "equals", "flag_only", "positional"])
        form.addRow("form", form_combo)

        multiple_combo = QComboBox(panel)
        multiple_combo.addItems(["false", "true"])
        form.addRow("multiple", multiple_combo)

        multi_mode_combo = QComboBox(panel)
        multi_mode_combo.addItems(["", "repeat_flag", "join_os_pathsep", "join_comma", "join_space"])
        form.addRow("multi_mode", multi_mode_combo)

        required_combo = QComboBox(panel)
        required_combo.addItems(["false", "true"])
        form.addRow("required", required_combo)

        default_edit = QLineEdit(panel)
        default_edit.setPlaceholderText("既定値 (未入力時に使用)")
        form.addRow("default_value", default_edit)

        layout.addLayout(form)

        validation = QLabel(
            "警告: multiple=true の場合は multi_mode を指定してください。",
            panel,
        )
        validation.setWordWrap(True)
        validation.setProperty("class", "warning")
        layout.addWidget(validation)

        help_text = QLabel(
            "未入力時の挙動: required=true & default_value なしの場合はエラー扱い。"
            " bool 型の default_value=true は flag_only を出力します。",
            panel,
        )
        help_text.setWordWrap(True)
        layout.addWidget(help_text)

        return panel

    def _build_preview_box(self) -> QWidget:
        box = QGroupBox("組み立て結果プレビュー", self)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(6)

        self._preview_output = QPlainTextEdit(box)
        self._preview_output.setReadOnly(True)
        self._preview_output.setPlaceholderText("例: maya -proj <project> -file <scene>")
        self._preview_output.setMinimumHeight(80)
        layout.addWidget(self._preview_output)

        return box

    def _build_raw_json_box(self) -> QWidget:
        box = QGroupBox("コメント JSON (raw)", self)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(6)

        warning = QLabel(
            "JSON パースに失敗した場合は警告表示し、ここで直接修復します。"
            " 実行時は引数テンプレなし/起動停止のいずれかを選ぶ仕様を明示します。",
            box,
        )
        warning.setWordWrap(True)
        warning.setProperty("class", "warning")
        layout.addWidget(warning)

        self._raw_json_editor = QPlainTextEdit(box)
        self._raw_json_editor.setPlaceholderText(
            "{\n  \"schema_version\": 1,\n  \"connectors\": []\n}"
        )
        self._raw_json_editor.setLineWrapMode(QPlainTextEdit.NoWrap)
        layout.addWidget(self._raw_json_editor)

        return box

    def _build_footer(self) -> QWidget:
        footer = QWidget(self)
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        destination = QLineEdit(footer)
        destination.setReadOnly(True)
        destination.setPlaceholderText("保存先: ノードカタログ / テンプレ")
        layout.addWidget(destination, 1)

        create_button = QPushButton("環境を作成", footer)
        create_button.clicked.connect(self._show_environment_summary)
        layout.addWidget(create_button)
        layout.addWidget(QPushButton("登録 / 更新", footer))

        buttons = QDialogButtonBox(QDialogButtonBox.Close, Qt.Horizontal, footer)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        return footer

    def _update_rez_line_numbers(self) -> None:
        if self._rez_editor is None or self._rez_line_numbers is None:
            return
        text = self._rez_editor.toPlainText()
        line_count = max(1, text.count("\n") + 1)
        numbers = "\n".join(str(index) for index in range(1, line_count + 1))
        self._rez_line_numbers.blockSignals(True)
        self._rez_line_numbers.setPlainText(numbers)
        self._rez_line_numbers.blockSignals(False)

    def _show_environment_summary(self) -> None:
        package = self._package_combo.currentText().strip() if self._package_combo else ""
        name = self._name_edit.text().strip() if self._name_edit else ""
        description = self._desc_edit.text().strip() if self._desc_edit else ""
        author = self._author_edit.text().strip() if self._author_edit else ""
        rez_commands = self._rez_editor.toPlainText().strip() if self._rez_editor else ""
        preview = self._preview_output.toPlainText().strip() if self._preview_output else ""
        raw_json = self._raw_json_editor.toPlainText().strip() if self._raw_json_editor else ""

        message = "\n".join(
            [
                f"原子パッケージ: {package or '-'}",
                f"テンプレ名: {name or '-'}",
                f"説明: {description or '-'}",
                f"作成者: {author or '-'}",
                "",
                "[Rez commands]",
                rez_commands or "-",
                "",
                "[起動引数プレビュー]",
                preview or "-",
                "",
                "[コメント JSON]",
                raw_json or "-",
            ]
        )
        QMessageBox.information(self, "環境定義の確認", message)
