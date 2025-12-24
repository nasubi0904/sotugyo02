"""ツール環境定義を編集するダイアログ。"""

from __future__ import annotations

from typing import Dict, List, Optional

from qtpy import QtCore, QtWidgets

Qt = QtCore.Qt
QAbstractItemView = QtWidgets.QAbstractItemView
QDialog = QtWidgets.QDialog
QDialogButtonBox = QtWidgets.QDialogButtonBox
QFormLayout = QtWidgets.QFormLayout
QHBoxLayout = QtWidgets.QHBoxLayout
QLabel = QtWidgets.QLabel
QLineEdit = QtWidgets.QLineEdit
QMessageBox = QtWidgets.QMessageBox
QPlainTextEdit = QtWidgets.QPlainTextEdit
QPushButton = QtWidgets.QPushButton
QTreeWidget = QtWidgets.QTreeWidget
QTreeWidgetItem = QtWidgets.QTreeWidgetItem
QVBoxLayout = QtWidgets.QVBoxLayout
QWidget = QtWidgets.QWidget

from ...domain.tooling import ToolEnvironmentDefinition, ToolEnvironmentService


class ToolEnvironmentManagerDialog(QDialog):
    """ツール環境ノードの定義一覧を管理する。"""

    def __init__(self, service: ToolEnvironmentService, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._service = service
        self._environment_list: Optional[QTreeWidget] = None
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
            "Rez パッケージとバリアントを組み合わせた環境を定義します。定義した環境はコンテンツブラウザからノードとして利用できます。",
            self,
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        env_list = QTreeWidget(self)
        env_list.setColumnCount(2)
        env_list.setHeaderLabels(
            ["Rez パッケージ", "Rez バリアント"]
        )
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
            environments = self._service.list_environments()
        except OSError as exc:
            QMessageBox.critical(self, "エラー", f"環境情報の取得に失敗しました: {exc}")
            environments = []
        if self._environment_list is None:
            return
        self._environment_list.clear()
        for environment in environments:
            packages_text = ", ".join(environment.rez_packages)
            if not packages_text:
                packages_text = "-"
            variants_text = ", ".join(environment.rez_variants) if environment.rez_variants else "-"
            item = QTreeWidgetItem(
                [
                    packages_text,
                    variants_text,
                ]
            )
            item.setData(0, Qt.UserRole, environment.package_key_label())
            self._environment_list.addTopLevelItem(item)
        self._environment_list.resizeColumnToContents(0)
        self._environment_list.resizeColumnToContents(1)

    def _add_environment(self) -> None:
        dialog = ToolEnvironmentEditDialog(
            service=self._service,
            parent=self,
        )
        if dialog.exec() != QDialog.Accepted:
            return
        payload = dialog.result_payload()
        if not payload:
            return
        try:
            environment = self._service.save_environment(**payload)
        except ValueError as exc:
            QMessageBox.warning(self, "保存に失敗", str(exc))
            return
        except OSError as exc:
            QMessageBox.critical(self, "保存に失敗", str(exc))
            return
        self._refresh_on_accept = True
        self._refresh_listing()

    def _current_environment_key(self) -> Optional[str]:
        if self._environment_list is None:
            return None
        current = self._environment_list.currentItem()
        if current is None:
            return None
        identifier = current.data(0, Qt.UserRole)
        return identifier if isinstance(identifier, str) else None

    def _edit_environment(self) -> None:
        package_key_label = self._current_environment_key()
        if not package_key_label:
            QMessageBox.information(self, "編集", "編集する環境を選択してください。")
            return
        try:
            environments = self._service.list_environments()
        except OSError as exc:
            QMessageBox.critical(self, "取得失敗", str(exc))
            return
        target = next(
            (
                env
                for env in environments
                if env.package_key_label() == package_key_label
            ),
            None,
        )
        if target is None:
            QMessageBox.warning(self, "編集", "指定された環境が見つかりませんでした。")
            return
        dialog = ToolEnvironmentEditDialog(
            service=self._service,
            definition=target,
            parent=self,
        )
        if dialog.exec() != QDialog.Accepted:
            return
        payload = dialog.result_payload()
        if not payload:
            return
        try:
            environment = self._service.save_environment(**payload)
        except ValueError as exc:
            QMessageBox.warning(self, "保存に失敗", str(exc))
            return
        except OSError as exc:
            QMessageBox.critical(self, "保存に失敗", str(exc))
            return
        self._refresh_on_accept = True
        self._refresh_listing()

    def _remove_environment(self) -> None:
        package_key_label = self._current_environment_key()
        if not package_key_label:
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
            removed = self._service.remove_environment(package_key_label)
        except OSError as exc:
            QMessageBox.critical(self, "削除に失敗", str(exc))
            return
        if not removed:
            QMessageBox.warning(self, "削除", "指定された環境が見つかりませんでした。")
            return
        self._refresh_on_accept = True
        self._refresh_listing()

    @staticmethod
    def _describe_validation(status: Optional[dict]) -> str:
        if not isinstance(status, dict):
            return ""
        if bool(status.get("success", False)):
            return "Rez 検証済み"
        message = str(
            status.get("stderr")
            or status.get("stdout")
            or status.get("message")
            or "Rez 環境の解決に失敗しました。"
        )
        return f"Rez 検証失敗: {message}"


class ToolEnvironmentEditDialog(QDialog):
    """単一のツール環境を編集するフォーム。"""

    def __init__(
        self,
        *,
        service: ToolEnvironmentService,
        definition: Optional[ToolEnvironmentDefinition] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._definition = definition
        self._package_edit: Optional[QPlainTextEdit] = None
        self._variant_edit: Optional[QLineEdit] = None
        self._result: Optional[dict] = None

        self.setWindowTitle("環境の設定")
        self.resize(520, 420)

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

        self._package_edit = QPlainTextEdit(self)
        self._package_edit.setPlaceholderText("1 行につき 1 つの Rez パッケージを入力します。")
        form.addRow("Rez パッケージ", self._package_edit)

        self._variant_edit = QLineEdit(self)
        self._variant_edit.setPlaceholderText("カンマ区切りで Rez バリアントを指定")
        form.addRow("Rez バリアント", self._variant_edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal,
            self,
        )
        buttons.accepted.connect(self._handle_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _apply_definition(self, definition: ToolEnvironmentDefinition) -> None:
        if self._package_edit is not None:
            self._package_edit.setPlainText("\n".join(definition.rez_packages))
        if self._variant_edit is not None:
            self._variant_edit.setText(", ".join(definition.rez_variants))

    def _handle_accept(self) -> None:
        if (
            or self._package_edit is None
            or self._variant_edit is None
        ):
            return
        packages = self._collect_packages()
        if not packages:
            QMessageBox.warning(self, "入力不備", "Rez パッケージを入力してください。")
            return
        variants = self._collect_variants()
        result: Dict[str, object] = {
            "rez_packages": packages,
            "rez_variants": variants,
        }
        self._result = result
        self.accept()

    def _collect_packages(self) -> List[str]:
        if self._package_edit is None:
            return []
        lines = [line.strip() for line in self._package_edit.toPlainText().splitlines()]
        return [line for line in lines if line]

    def _collect_variants(self) -> List[str]:
        if self._variant_edit is None:
            return []
        text = self._variant_edit.text()
        items = [part.strip() for part in text.split(",")]
        return [item for item in items if item]
