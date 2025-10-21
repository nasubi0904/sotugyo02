"""スタート画面の実装。"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QInputDialog,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from ..settings.project_registry import ProjectRecord, ProjectRegistry
from ..settings.project_settings import load_project_settings, save_project_settings
from ..settings.project_structure import ensure_project_structure, validate_project_structure
from ..settings.user_settings import UserSettingsManager
from .node_editor_window import NodeEditorWindow


class PasswordPromptDialog(QDialog):
    """ユーザーパスワードを入力させるためのダイアログ。"""

    def __init__(self, *, user_id: str, default_password: Optional[str] = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"{user_id} のパスワード")
        self._password_edit = QLineEdit(self)
        self._password_edit.setEchoMode(QLineEdit.Password)
        if default_password:
            self._password_edit.setText(default_password)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("パスワードを入力してください。", self))
        layout.addWidget(self._password_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def password(self) -> str:
        return self._password_edit.text()


class StartWindow(QMainWindow):
    """ノード編集テストへ遷移するスタート画面。"""

    WINDOW_TITLE = "スタート画面"

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(self.WINDOW_TITLE)
        self.resize(640, 420)
        self._node_window: Optional[NodeEditorWindow] = None
        self._registry = ProjectRegistry()
        self._user_manager = UserSettingsManager()
        self._project_records: Dict[int, ProjectRecord] = {}
        self._current_settings_path: Optional[Path] = None
        self._active_project_root: Optional[Path] = None
        self._active_user_id: Optional[str] = None

        self._project_combo: Optional[QComboBox] = None
        self._user_combo: Optional[QComboBox] = None
        self._project_info_label: Optional[QLabel] = None
        self._structure_warning_label: Optional[QLabel] = None

        self._init_ui()
        self.refresh_start_state()

    # UI -----------------------------------------------------------------
    def _init_ui(self) -> None:
        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        title = QLabel("Sotugyo パイプラインへようこそ", self)
        title.setObjectName("startTitle")
        title.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        layout.addWidget(title)

        description = QLabel(
            "プロジェクトとユーザーを選択してノードエディタを開始します。", self
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        layout.addItem(QSpacerItem(0, 8, QSizePolicy.Minimum, QSizePolicy.Minimum))

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)

        self._project_combo = QComboBox(self)
        self._project_combo.currentIndexChanged.connect(self._on_project_changed)
        form.addRow("プロジェクト", self._project_combo)

        project_button_row = QHBoxLayout()
        create_button = QPushButton("新規プロジェクト...", self)
        create_button.clicked.connect(self._create_project)
        refresh_button = QPushButton("再読み込み", self)
        refresh_button.clicked.connect(self.refresh_start_state)
        project_button_row.addWidget(create_button)
        project_button_row.addWidget(refresh_button)
        form.addRow(" ", project_button_row)

        self._user_combo = QComboBox(self)
        self._user_combo.currentIndexChanged.connect(self._on_user_changed)
        form.addRow("ユーザー", self._user_combo)

        layout.addLayout(form)

        self._project_info_label = QLabel("プロジェクト情報がここに表示されます。", self)
        self._project_info_label.setWordWrap(True)
        layout.addWidget(self._project_info_label)

        self._structure_warning_label = QLabel("", self)
        self._structure_warning_label.setWordWrap(True)
        layout.addWidget(self._structure_warning_label)

        layout.addItem(QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding))

        open_button = QPushButton("ノードエディタを開く", self)
        open_button.clicked.connect(self._open_node_editor)
        layout.addWidget(open_button, alignment=Qt.AlignRight)

        self.setCentralWidget(container)

    # 状態更新 -----------------------------------------------------------
    def refresh_start_state(self) -> None:
        self._reload_projects()
        self._reload_users()

    def _reload_projects(self) -> None:
        if self._project_combo is None:
            return
        self._project_combo.blockSignals(True)
        self._project_combo.clear()
        self._project_records.clear()

        records = self._registry.records()
        for index, record in enumerate(records):
            display_name = record.name or record.root.name
            self._project_combo.addItem(display_name, record.root)
            self._project_records[index] = record
        last_root = self._registry.last_project()
        if last_root is not None:
            for index, record in self._project_records.items():
                if Path(record.root) == Path(last_root):
                    self._project_combo.setCurrentIndex(index)
                    break
        self._project_combo.blockSignals(False)
        self._on_project_changed(self._project_combo.currentIndex())

    def _reload_users(self) -> None:
        if self._user_combo is None:
            return
        accounts = self._user_manager.list_accounts()
        self._user_combo.blockSignals(True)
        self._user_combo.clear()
        for account in accounts:
            display = f"{account.display_name} ({account.user_id})"
            self._user_combo.addItem(display, account.user_id)
        self._user_combo.blockSignals(False)
        self._apply_default_user_selection()

    def _apply_default_user_selection(self) -> None:
        if self._user_combo is None:
            return
        preferred_user: Optional[str] = None
        if self._current_settings_path:
            settings = load_project_settings(self._current_settings_path)
            if settings.auto_fill_credentials and settings.last_user_id:
                preferred_user = settings.last_user_id
        if preferred_user is None:
            preferred_user = self._user_manager.last_user_id()
        if preferred_user:
            for index in range(self._user_combo.count()):
                if self._user_combo.itemData(index) == preferred_user:
                    self._user_combo.setCurrentIndex(index)
                    break

    def _on_project_changed(self, index: int) -> None:
        if self._project_combo is None or self._project_info_label is None:
            return
        record = self._project_records.get(index)
        if record is None:
            self._current_settings_path = None
            self._project_info_label.setText("プロジェクトが選択されていません。")
            if self._structure_warning_label:
                self._structure_warning_label.clear()
            return
        self._current_settings_path = Path(record.root)
        settings = load_project_settings(record.root)
        info_lines = [
            f"プロジェクト名: {settings.project_name}",
            f"ルート: {record.root}",
            f"概要: {settings.description or '（なし）'}",
        ]
        self._project_info_label.setText("\n".join(info_lines))
        report = validate_project_structure(record.root)
        if self._structure_warning_label:
            if report.is_valid:
                self._structure_warning_label.setText("構成チェック: 問題なし")
                self._structure_warning_label.setStyleSheet("color: #198754;")
            else:
                self._structure_warning_label.setText("構成チェック: " + report.summary())
                self._structure_warning_label.setStyleSheet("color: #d9534f;")
        self._apply_default_user_selection()

    def _on_user_changed(self, index: int) -> None:
        # 選択変更時には特に処理しないが、今後の拡張用にフックを用意する
        return

    # プロジェクト管理 ---------------------------------------------------
    def _create_project(self) -> None:
        base_dir = QFileDialog.getExistingDirectory(self, "プロジェクトの保存先を選択")
        if not base_dir:
            return
        base_path = Path(base_dir)
        project_name, ok = QInputDialog.getText(self, "プロジェクト名", "プロジェクト名を入力")
        if not ok or not project_name.strip():
            return
        project_name = project_name.strip()
        project_dir = base_path / project_name
        if project_dir.exists() and any(project_dir.iterdir()):
            confirm = QMessageBox.question(
                self,
                "確認",
                "選択したディレクトリは既に存在し内容があります。使用しますか？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return
        try:
            ensure_project_structure(project_dir)
        except OSError as exc:
            QMessageBox.critical(self, "エラー", f"構成の作成に失敗しました: {exc}")
            return
        settings = load_project_settings(project_dir)
        settings.project_name = project_name
        save_project_settings(settings)
        record = ProjectRecord(name=project_name, root=project_dir)
        self._registry.register_project(record)
        self.refresh_start_state()
        if self._project_combo is not None:
            for index in range(self._project_combo.count()):
                if Path(self._project_combo.itemData(index)) == project_dir:
                    self._project_combo.setCurrentIndex(index)
                    break

    # ノードエディタ起動 -------------------------------------------------
    def _open_node_editor(self) -> None:
        if self._project_combo is None or self._user_combo is None:
            return
        project_index = self._project_combo.currentIndex()
        record = self._project_records.get(project_index)
        if record is None:
            QMessageBox.warning(self, "警告", "プロジェクトを選択してください。")
            return
        user_id = self._user_combo.currentData()
        if not user_id:
            QMessageBox.warning(self, "警告", "ユーザーを選択してください。")
            return
        account = self._user_manager.get_account(user_id)
        if account is None:
            QMessageBox.warning(self, "警告", "指定されたユーザーが設定に存在しません。ユーザー設定を確認してください。")
            return

        if self._active_user_id and self._active_user_id != user_id:
            confirm = QMessageBox.warning(
                self,
                "確認",
                "現在のユーザーから切り替えます。続行しますか？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return

        settings = load_project_settings(record.root)
        report = validate_project_structure(record.root)
        if not report.is_valid:
            proceed = QMessageBox.warning(
                self,
                "警告",
                "既定の構成に不足があります。続行すると不足要素は作成されません。進めますか？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if proceed != QMessageBox.StandardButton.Yes:
                return

        default_password: Optional[str] = None
        if settings.auto_fill_credentials and settings.last_user_id == user_id:
            default_password = settings.last_user_password

        prompt = PasswordPromptDialog(user_id=user_id, default_password=default_password, parent=self)
        if prompt.exec() != QDialog.Accepted:
            return
        password = prompt.password()
        if not account.verify_password(password):
            QMessageBox.critical(self, "エラー", "パスワードが一致しません。")
            return

        if settings.auto_fill_credentials:
            settings.last_user_id = user_id
            settings.last_user_password = password
            save_project_settings(settings)
        self._user_manager.set_last_user_id(user_id)
        self._registry.set_last_project(record.root)

        if self._node_window is None:
            self._node_window = NodeEditorWindow(self)
            self._node_window.return_to_start_requested.connect(self._on_return_to_start)
        if not self._node_window.prepare_context(record.root, settings, account, password):
            return
        self._active_project_root = record.root
        self._active_user_id = user_id
        self._node_window.show()
        self._node_window.raise_()
        self._node_window.activateWindow()
        self.hide()

    def _on_return_to_start(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()
        self.refresh_start_state()

