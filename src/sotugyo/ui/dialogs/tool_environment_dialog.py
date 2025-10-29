"""ツール環境定義を編集するダイアログ。"""

from __future__ import annotations

from typing import Dict, Optional

from qtpy import QtCore, QtWidgets

Qt = QtCore.Qt
QAbstractItemView = QtWidgets.QAbstractItemView
QComboBox = QtWidgets.QComboBox
QDialog = QtWidgets.QDialog
QDialogButtonBox = QtWidgets.QDialogButtonBox
QFormLayout = QtWidgets.QFormLayout
QHBoxLayout = QtWidgets.QHBoxLayout
QLabel = QtWidgets.QLabel
QLineEdit = QtWidgets.QLineEdit
QMessageBox = QtWidgets.QMessageBox
QPushButton = QtWidgets.QPushButton
QTreeWidget = QtWidgets.QTreeWidget
QTreeWidgetItem = QtWidgets.QTreeWidgetItem
QVBoxLayout = QtWidgets.QVBoxLayout
QWidget = QtWidgets.QWidget

from ...domain.tooling import (
    RegisteredTool,
    ToolEnvironmentDefinition,
    ToolEnvironmentService,
)


class ToolEnvironmentManagerDialog(QDialog):
    """ツール環境ノードの定義一覧を管理する。"""

    def __init__(self, service: ToolEnvironmentService, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._service = service
        self._environment_list: Optional[QTreeWidget] = None
        self._tool_cache: Dict[str, RegisteredTool] = {}
        self._refresh_on_accept = False

        self.setWindowTitle("ツール環境の編集")
        self.resize(520, 420)

        self._build_ui()
        self._refresh_listing()

    def refresh_requested(self) -> bool:
        return self._refresh_on_accept

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        description = QLabel(
            "登録済みツールを組み合わせた環境を定義します。定義した環境はコンテンツブラウザからノードとして利用できます。",
            self,
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        env_list = QTreeWidget(self)
        env_list.setColumnCount(4)
        env_list.setHeaderLabels(["環境名", "ツール", "バージョン", "実行ファイル"])
        env_list.setRootIsDecorated(False)
        env_list.setAlternatingRowColors(True)
        env_list.setSelectionMode(QAbstractItemView.SingleSelection)
        env_list.setSelectionBehavior(QAbstractItemView.SelectRows)
        env_list.setUniformRowHeights(True)
        env_list.setAllColumnsShowFocus(True)
        layout.addWidget(env_list, 1)
        self._environment_list = env_list

        button_row = QHBoxLayout()
        add_button = QPushButton("追加")
        add_button.clicked.connect(self._add_environment)
        edit_button = QPushButton("編集")
        edit_button.clicked.connect(self._edit_environment)
        remove_button = QPushButton("削除")
        remove_button.clicked.connect(self._remove_environment)
        button_row.addWidget(add_button)
        button_row.addWidget(edit_button)
        button_row.addWidget(remove_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        buttons = QDialogButtonBox(QDialogButtonBox.Close, Qt.Horizontal, self)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _refresh_listing(self) -> None:
        try:
            tools = self._service.list_tools()
        except OSError as exc:
            QMessageBox.critical(self, "エラー", f"ツール情報の取得に失敗しました: {exc}")
            tools = []
        self._tool_cache = {tool.tool_id: tool for tool in tools}
        try:
            environments = self._service.list_environments()
        except OSError as exc:
            QMessageBox.critical(self, "エラー", f"環境情報の取得に失敗しました: {exc}")
            environments = []
        if self._environment_list is None:
            return
        self._environment_list.clear()
        for environment in environments:
            tool = self._tool_cache.get(environment.tool_id)
            item = QTreeWidgetItem(
                [
                    environment.name,
                    tool.display_name if tool else "(未登録)",
                    environment.version_label,
                    str(tool.executable_path) if tool else "-",
                ]
            )
            item.setData(0, Qt.UserRole, environment.environment_id)
            self._environment_list.addTopLevelItem(item)
        self._environment_list.resizeColumnToContents(0)
        self._environment_list.resizeColumnToContents(1)
        self._environment_list.resizeColumnToContents(2)

    def _add_environment(self) -> None:
        if not self._tool_cache:
            QMessageBox.information(self, "環境の追加", "先にツールを登録してください。")
            return
        dialog = ToolEnvironmentEditDialog(self._tool_cache, parent=self)
        if dialog.exec() != QDialog.Accepted:
            return
        payload = dialog.result_payload()
        if not payload:
            return
        try:
            self._service.save_environment(**payload)
        except ValueError as exc:
            QMessageBox.warning(self, "保存に失敗", str(exc))
            return
        except OSError as exc:
            QMessageBox.critical(self, "保存に失敗", str(exc))
            return
        self._refresh_on_accept = True
        self._refresh_listing()

    def _current_environment_id(self) -> Optional[str]:
        if self._environment_list is None:
            return None
        current = self._environment_list.currentItem()
        if current is None:
            return None
        identifier = current.data(0, Qt.UserRole)
        return identifier if isinstance(identifier, str) else None

    def _edit_environment(self) -> None:
        env_id = self._current_environment_id()
        if not env_id:
            QMessageBox.information(self, "編集", "編集する環境を選択してください。")
            return
        try:
            environments = self._service.list_environments()
        except OSError as exc:
            QMessageBox.critical(self, "取得失敗", str(exc))
            return
        target = next((env for env in environments if env.environment_id == env_id), None)
        if target is None:
            QMessageBox.warning(self, "編集", "指定された環境が見つかりませんでした。")
            return
        dialog = ToolEnvironmentEditDialog(self._tool_cache, definition=target, parent=self)
        if dialog.exec() != QDialog.Accepted:
            return
        payload = dialog.result_payload()
        if not payload:
            return
        payload["environment_id"] = env_id
        try:
            self._service.save_environment(**payload)
        except ValueError as exc:
            QMessageBox.warning(self, "保存に失敗", str(exc))
            return
        except OSError as exc:
            QMessageBox.critical(self, "保存に失敗", str(exc))
            return
        self._refresh_on_accept = True
        self._refresh_listing()

    def _remove_environment(self) -> None:
        env_id = self._current_environment_id()
        if not env_id:
            QMessageBox.information(self, "削除", "削除する環境を選択してください。")
            return
        reply = QMessageBox.question(
            self,
            "確認",
            "選択した環境を削除しますか？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            removed = self._service.remove_environment(env_id)
        except OSError as exc:
            QMessageBox.critical(self, "削除に失敗", str(exc))
            return
        if not removed:
            QMessageBox.warning(self, "削除", "指定された環境が見つかりませんでした。")
            return
        self._refresh_on_accept = True
        self._refresh_listing()


class ToolEnvironmentEditDialog(QDialog):
    """単一のツール環境を編集するフォーム。"""

    def __init__(
        self,
        tool_cache: Dict[str, RegisteredTool],
        *,
        definition: Optional[ToolEnvironmentDefinition] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._tools = tool_cache
        self._definition = definition
        self._name_edit: Optional[QLineEdit] = None
        self._tool_combo: Optional[QComboBox] = None
        self._version_edit: Optional[QLineEdit] = None
        self._path_label: Optional[QLabel] = None
        self._result: Optional[dict] = None

        self.setWindowTitle("環境の設定")
        self.resize(420, 220)

        self._build_ui()
        if definition is not None:
            self._apply_definition(definition)

    def result_payload(self) -> Optional[dict]:
        return self._result

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(12)

        self._name_edit = QLineEdit(self)
        form.addRow("環境名", self._name_edit)

        self._tool_combo = QComboBox(self)
        for tool_id, tool in sorted(
            self._tools.items(), key=lambda item: item[1].display_name
        ):
            label = f"{tool.display_name}"
            if tool.version:
                label += f" ({tool.version})"
            self._tool_combo.addItem(label, tool_id)
        self._tool_combo.currentIndexChanged.connect(self._update_tool_path)
        form.addRow("利用するツール", self._tool_combo)

        self._version_edit = QLineEdit(self)
        form.addRow("バージョン表示", self._version_edit)

        self._path_label = QLabel("-", self)
        self._path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        form.addRow("実行ファイル", self._path_label)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal,
            self,
        )
        buttons.accepted.connect(self._handle_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._update_tool_path()

    def _apply_definition(self, definition: ToolEnvironmentDefinition) -> None:
        if self._name_edit is not None:
            self._name_edit.setText(definition.name)
        if self._tool_combo is not None:
            index = self._tool_combo.findData(definition.tool_id)
            if index >= 0:
                self._tool_combo.setCurrentIndex(index)
        if self._version_edit is not None:
            self._version_edit.setText(definition.version_label)
        self._update_tool_path()

    def _update_tool_path(self) -> None:
        if self._tool_combo is None or self._path_label is None:
            return
        tool_id = self._tool_combo.currentData()
        tool = self._tools.get(tool_id) if isinstance(tool_id, str) else None
        self._path_label.setText(str(tool.executable_path) if tool else "-")
        if (
            self._version_edit is not None
            and tool is not None
            and not self._version_edit.text().strip()
            and tool.version
        ):
            self._version_edit.setText(tool.version)

    def _handle_accept(self) -> None:
        if self._name_edit is None or self._tool_combo is None or self._version_edit is None:
            return
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "入力不備", "環境名を入力してください。")
            return
        tool_id = self._tool_combo.currentData()
        if not isinstance(tool_id, str):
            QMessageBox.warning(self, "入力不備", "利用するツールを選択してください。")
            return
        version = self._version_edit.text().strip()
        self._result = {
            "name": name,
            "tool_id": tool_id,
            "version_label": version or "",
        }
        self.accept()
