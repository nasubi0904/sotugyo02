"""スタート画面の実装。"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

from qtpy import QtCore, QtWidgets

Qt = QtCore.Qt
QComboBox = QtWidgets.QComboBox
QDialog = QtWidgets.QDialog
QDialogButtonBox = QtWidgets.QDialogButtonBox
QFileDialog = QtWidgets.QFileDialog
QFormLayout = QtWidgets.QFormLayout
QFrame = QtWidgets.QFrame
QHBoxLayout = QtWidgets.QHBoxLayout
QLabel = QtWidgets.QLabel
QLineEdit = QtWidgets.QLineEdit
QMainWindow = QtWidgets.QMainWindow
QMessageBox = QtWidgets.QMessageBox
QInputDialog = QtWidgets.QInputDialog
QPushButton = QtWidgets.QPushButton
QSizePolicy = QtWidgets.QSizePolicy
QSpacerItem = QtWidgets.QSpacerItem
QVBoxLayout = QtWidgets.QVBoxLayout
QWidget = QtWidgets.QWidget

from sotugyo.domain.projects import ProjectRecord, ProjectStructureReport
from ...dialogs.user_settings_dialog import UserSettingsDialog
from ...style import START_WINDOW_STYLE, apply_base_style
from ..controllers.start import StartWindowController
from .node_editor import NodeEditorWindow


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
        self._controller = StartWindowController.create_default()
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
        root = QWidget(self)
        root.setObjectName("startRoot")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(32, 32, 32, 32)
        root_layout.setSpacing(0)

        card = QFrame(root)
        card.setObjectName("startCard")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(24)

        title = QLabel("Sotugyo パイプラインへようこそ", card)
        title.setObjectName("startTitle")
        title.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.addWidget(title)

        description = QLabel(
            "プロジェクトとユーザーを選択してノードエディタを開始します。", card
        )
        description.setObjectName("startDescription")
        description.setWordWrap(True)
        layout.addWidget(description)

        layout.addItem(QSpacerItem(0, 8, QSizePolicy.Minimum, QSizePolicy.Minimum))

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)
        form.setFormAlignment(Qt.AlignTop)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(14)

        self._project_combo = QComboBox(card)
        self._project_combo.currentIndexChanged.connect(self._on_project_changed)
        project_label = QLabel("プロジェクト", card)
        project_label.setObjectName("formLabel")
        form.addRow(project_label, self._project_combo)

        project_button_row = QHBoxLayout()
        create_button = QPushButton("新規プロジェクト...", card)
        create_button.clicked.connect(self._create_project)
        import_button = QPushButton("既存プロジェクトを追加...", card)
        import_button.clicked.connect(self._add_existing_project)
        refresh_button = QPushButton("再読み込み", card)
        refresh_button.clicked.connect(self.refresh_start_state)
        project_button_row.addWidget(create_button)
        project_button_row.addWidget(import_button)
        project_button_row.addWidget(refresh_button)
        project_button_label = QLabel("", card)
        project_button_label.setObjectName("formLabel")
        form.addRow(project_button_label, project_button_row)

        self._user_combo = QComboBox(card)
        self._user_combo.currentIndexChanged.connect(self._on_user_changed)
        user_label = QLabel("ユーザー", card)
        user_label.setObjectName("formLabel")
        form.addRow(user_label, self._user_combo)

        user_button_row = QHBoxLayout()
        user_settings_button = QPushButton("ユーザー設定...", card)
        user_settings_button.clicked.connect(self._open_user_settings)
        user_button_row.addWidget(user_settings_button)
        user_button_row.addStretch(1)
        user_button_label = QLabel("", card)
        user_button_label.setObjectName("formLabel")
        form.addRow(user_button_label, user_button_row)

        layout.addLayout(form)

        self._project_info_label = QLabel("プロジェクト情報がここに表示されます。", card)
        self._project_info_label.setObjectName("projectInfoLabel")
        self._project_info_label.setWordWrap(True)
        layout.addWidget(self._project_info_label)

        self._structure_warning_label = QLabel("", card)
        self._structure_warning_label.setObjectName("structureStatusLabel")
        self._structure_warning_label.setWordWrap(True)
        self._structure_warning_label.hide()
        layout.addWidget(self._structure_warning_label)

        layout.addItem(QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding))

        open_button = QPushButton("ノードエディタを開く", card)
        open_button.setObjectName("primaryActionButton")
        open_button.clicked.connect(self._open_node_editor)
        layout.addWidget(open_button, alignment=Qt.AlignRight)

        root_layout.addStretch(1)
        root_layout.addWidget(card, 0, Qt.AlignCenter)
        root_layout.addStretch(1)

        self.setCentralWidget(root)
        self._apply_styles()

    def _update_structure_warning(self, status: Optional[str], text: str = "") -> None:
        if self._structure_warning_label is None:
            return
        label = self._structure_warning_label
        if status and text:
            label.setText(text)
            label.setProperty("status", status)
            label.show()
        else:
            label.clear()
            label.setProperty("status", "")
            label.hide()
        style = label.style()
        if style is not None:
            style.unpolish(label)
            style.polish(label)
        label.update()

    def _apply_styles(self) -> None:
        apply_base_style(self, START_WINDOW_STYLE)

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

        records = self._controller.project_records()
        for index, record in enumerate(records):
            display_name = record.name or record.root.name
            self._project_combo.addItem(display_name, record.root)
            self._project_records[index] = record
        last_root = self._controller.last_project_root()
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
        previous_user = self._user_combo.currentData()
        accounts = self._controller.list_accounts()
        self._user_combo.blockSignals(True)
        self._user_combo.clear()
        for account in accounts:
            display = f"{account.display_name} ({account.user_id})"
            self._user_combo.addItem(display, account.user_id)
        self._user_combo.blockSignals(False)
        if previous_user and self._set_user_selection(previous_user):
            return
        self._apply_default_user_selection()

    def _apply_default_user_selection(self) -> None:
        if self._user_combo is None:
            return
        preferred_user: Optional[str] = None
        if self._current_settings_path:
            settings = self._controller.load_project_settings(self._current_settings_path)
            if settings.auto_fill_user_id and settings.last_user_id:
                preferred_user = settings.last_user_id
        if preferred_user is None:
            preferred_user = self._controller.last_user_id()
        if preferred_user:
            self._set_user_selection(preferred_user)

    def _set_user_selection(self, user_id: str) -> bool:
        if self._user_combo is None:
            return False
        for index in range(self._user_combo.count()):
            if self._user_combo.itemData(index) == user_id:
                previous_block = self._user_combo.blockSignals(True)
                self._user_combo.setCurrentIndex(index)
                self._user_combo.blockSignals(previous_block)
                return True
        return False

    def _open_user_settings(self) -> None:
        dialog = UserSettingsDialog(self._controller.user_manager, self)
        if dialog.exec() == QDialog.Accepted:
            self._reload_users()

    def _on_project_changed(self, index: int) -> None:
        if self._project_combo is None or self._project_info_label is None:
            return
        record = self._project_records.get(index)
        if record is None:
            self._current_settings_path = None
            self._project_info_label.setText("プロジェクトが選択されていません。")
            self._update_structure_warning(None)
            return
        self._current_settings_path = Path(record.root)
        context = self._controller.load_project_context(record.root)
        settings = context.settings
        info_lines = [
            f"プロジェクト名: {settings.project_name}",
            f"ルート: {record.root}",
            f"概要: {settings.description or '（なし）'}",
        ]
        self._project_info_label.setText("\n".join(info_lines))
        report = self._controller.validate_structure(record.root)
        if report.is_valid:
            self._update_structure_warning("ok", "構成チェック: 問題なし")
        else:
            self._update_structure_warning("error", "構成チェック: " + report.summary())
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
            self._controller.ensure_structure(project_dir)
        except OSError as exc:
            QMessageBox.critical(self, "エラー", f"構成の作成に失敗しました: {exc}")
            return
        settings = self._controller.load_project_settings(project_dir)
        settings.project_name = project_name
        self._controller.save_project_settings(settings, set_last=True)
        self.refresh_start_state()
        if self._project_combo is not None:
            for index in range(self._project_combo.count()):
                if Path(self._project_combo.itemData(index)) == project_dir:
                    self._project_combo.setCurrentIndex(index)
                    break

    def _add_existing_project(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "既存プロジェクトのルートを選択")
        if not directory:
            return
        root = Path(directory)
        if not root.exists() or not root.is_dir():
            QMessageBox.critical(self, "エラー", "選択したディレクトリが存在しないか、フォルダーではありません。")
            return
        report = self._controller.validate_structure(root)
        if not self._confirm_project_registration(report):
            return
        settings = self._controller.load_project_settings(root)
        self._controller.register_project(settings.to_record(), set_last=True)
        self.refresh_start_state()

    def _confirm_project_registration(self, report: ProjectStructureReport) -> bool:
        if report.is_valid:
            return True
        message = "既定の構成に不足があります。登録を続行しますか？\n\n" + report.summary()
        response = QMessageBox.warning(
            self,
            "警告",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return response == QMessageBox.StandardButton.Yes

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
        account = self._controller.get_account(user_id)
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

        context = self._controller.load_project_context(record.root)
        settings = context.settings
        report: ProjectStructureReport = self._controller.validate_structure(record.root)
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
        if settings.auto_fill_password and settings.last_user_id == user_id:
            default_password = settings.last_user_password

        prompt = PasswordPromptDialog(user_id=user_id, default_password=default_password, parent=self)
        if prompt.exec() != QDialog.Accepted:
            return
        password = prompt.password()
        if not account.verify_password(password):
            QMessageBox.critical(self, "エラー", "パスワードが一致しません。")
            return

        if settings.auto_fill_user_id:
            settings.last_user_id = user_id
        else:
            settings.last_user_id = None
        if settings.auto_fill_password:
            settings.last_user_password = password
        else:
            settings.last_user_password = None
        self._controller.save_project_settings(settings)
        self._controller.set_last_user_id(user_id)
        self._controller.set_last_project(record.root)

        if self._node_window is None:
            self._node_window = NodeEditorWindow(
                self,
                project_service=self._controller.project_service,
                user_manager=self._controller.user_manager,
            )
            self._node_window.return_to_start_requested.connect(self._on_return_to_start)
        if not self._node_window.prepare_context(context, account, password):
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

