"""ユーザー設定ダイアログ。"""

from __future__ import annotations

from typing import Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QInputDialog,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ..settings.user_settings import UserAccount, UserSettingsManager
from .style import apply_base_style


class UserSettingsDialog(QDialog):
    """ユーザーアカウントの登録・編集を行うダイアログ。"""

    def __init__(self, manager: UserSettingsManager, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("ユーザー設定")
        self.resize(480, 360)
        self._manager = manager
        self._accounts: Dict[str, UserAccount] = {
            account.user_id: account for account in manager.list_accounts()
        }
        self._current_user_id: Optional[str] = None

        self._list_widget = QListWidget(self)
        self._display_name_edit = QLineEdit(self)
        self._password_edit = QLineEdit(self)
        self._password_edit.setEchoMode(QLineEdit.Password)

        self._build_ui()
        self._populate_list()
        apply_base_style(self)

    def _build_ui(self) -> None:
        self.setObjectName("appDialog")

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(32, 32, 32, 32)
        outer_layout.setSpacing(0)

        card = QFrame(self)
        card.setObjectName("dialogCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 28, 28, 28)
        card_layout.setSpacing(18)

        header = QLabel("ユーザー設定", card)
        header.setObjectName("panelTitle")
        card_layout.addWidget(header)

        list_layout = QHBoxLayout()
        list_layout.setSpacing(16)
        self._list_widget.setObjectName("userList")
        self._list_widget.setAlternatingRowColors(False)
        self._list_widget.setSelectionMode(QListWidget.SingleSelection)
        self._list_widget.setWordWrap(True)
        self._list_widget.setTextElideMode(Qt.TextElideMode.ElideNone)
        list_layout.addWidget(self._list_widget, 1)

        button_column = QVBoxLayout()
        button_column.setSpacing(10)
        add_button = QPushButton("追加")
        remove_button = QPushButton("削除")
        button_column.addWidget(add_button)
        button_column.addWidget(remove_button)
        button_column.addStretch(1)
        list_layout.addLayout(button_column)

        card_layout.addLayout(list_layout)

        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignLeft)
        form_layout.setFormAlignment(Qt.AlignTop)
        form_layout.setHorizontalSpacing(18)
        form_layout.setVerticalSpacing(12)
        form_layout.addRow("表示名", self._display_name_edit)
        form_layout.addRow("パスワード", self._password_edit)
        card_layout.addLayout(form_layout)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, card)
        card_layout.addWidget(button_box, 0, Qt.AlignRight)

        outer_layout.addWidget(card)

        self._list_widget.currentItemChanged.connect(self._on_selection_changed)
        add_button.clicked.connect(self._add_account)
        remove_button.clicked.connect(self._remove_account)
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)

    def _populate_list(self) -> None:
        self._list_widget.clear()
        for user_id in sorted(self._accounts.keys()):
            account = self._accounts[user_id]
            item = QListWidgetItem(account.user_id)
            item.setData(Qt.UserRole, account.user_id)
            self._list_widget.addItem(item)
        if self._accounts:
            self._list_widget.setCurrentRow(0)

    def _on_selection_changed(self, current: QListWidgetItem, previous: QListWidgetItem) -> None:
        user_id = current.data(Qt.UserRole) if current else None
        self._current_user_id = user_id
        if not user_id or user_id not in self._accounts:
            self._display_name_edit.clear()
            self._password_edit.clear()
            return
        account = self._accounts[user_id]
        self._display_name_edit.setText(account.display_name)
        self._password_edit.clear()

    def _add_account(self) -> None:
        user_id, ok = QInputDialog.getText(self, "ユーザーID", "新しいユーザーIDを入力")
        user_id = user_id.strip() if user_id else ""
        if not ok or not user_id:
            return
        if user_id in self._accounts:
            QMessageBox.warning(self, "エラー", "同じユーザーIDが既に存在します。")
            return
        self._accounts[user_id] = UserAccount(user_id=user_id, display_name=user_id, password_hash="")
        self._populate_list()
        items = self._list_widget.findItems(user_id, Qt.MatchExactly)
        if items:
            self._list_widget.setCurrentItem(items[0])

    def _remove_account(self) -> None:
        if not self._current_user_id:
            return
        confirm = QMessageBox.question(
            self,
            "確認",
            f"ユーザー「{self._current_user_id}」を削除しますか？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        target = self._current_user_id
        del self._accounts[target]
        self._manager.remove_account(target)
        self._current_user_id = None
        self._populate_list()

    def _on_accept(self) -> None:
        if not self._accounts:
            QMessageBox.warning(self, "エラー", "少なくとも 1 件のユーザーを登録してください。")
            return
        current_display = self._display_name_edit.text().strip()
        current_password = self._password_edit.text()
        if self._current_user_id:
            if not current_display:
                QMessageBox.warning(self, "エラー", "表示名を入力してください。")
                return
            account = self._accounts[self._current_user_id]
            self._accounts[self._current_user_id] = UserAccount(
                user_id=account.user_id,
                display_name=current_display,
                password_hash=account.password_hash,
            )
            self._manager.upsert_account(
                self._current_user_id,
                current_display,
                current_password or None,
            )
        for user_id, account in self._accounts.items():
            if self._current_user_id and user_id == self._current_user_id:
                continue
            self._manager.upsert_account(user_id, account.display_name, None)
        self.accept()
