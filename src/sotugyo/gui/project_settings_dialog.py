"""プロジェクト設定ダイアログ。"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from ..settings.project_settings import ProjectSettings
from ..settings.project_structure import ProjectStructureReport, validate_project_structure


class ProjectSettingsDialog(QDialog):
    """プロジェクト名やルートを編集するダイアログ。"""

    def __init__(self, settings: ProjectSettings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("プロジェクト設定")
        self._original_settings = settings
        self._edited_settings = ProjectSettings(
            project_name=settings.project_name,
            description=settings.description,
            project_root=settings.project_root,
            auto_fill_credentials=settings.auto_fill_credentials,
            last_user_id=settings.last_user_id,
            last_user_password=settings.last_user_password,
        )
        self._structure_report: Optional[ProjectStructureReport] = None

        self._name_edit = QLineEdit(settings.project_name, self)
        self._description_edit = QTextEdit(self)
        self._description_edit.setPlainText(settings.description)
        self._root_edit = QLineEdit(str(settings.project_root), self)
        self._root_edit.setReadOnly(True)
        self._root_button = QPushButton("参照...")
        self._auto_fill_checkbox = QCheckBox("前回ユーザーの資格情報を自動入力する", self)
        self._auto_fill_checkbox.setChecked(settings.auto_fill_credentials)
        self._last_user_edit = QLineEdit(settings.last_user_id or "", self)
        self._last_password_edit = QLineEdit(settings.last_user_password or "", self)
        self._last_password_edit.setEchoMode(QLineEdit.Password)
        self._structure_label = QLabel("", self)
        self._structure_label.setWordWrap(True)

        self._build_ui()
        self._update_structure_status()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        form_layout.addRow("プロジェクト名", self._name_edit)
        form_layout.addRow("プロジェクト概要", self._description_edit)

        root_layout = QHBoxLayout()
        root_layout.addWidget(self._root_edit, 1)
        root_layout.addWidget(self._root_button)
        form_layout.addRow("プロジェクトルート", root_layout)

        form_layout.addRow(self._auto_fill_checkbox)
        form_layout.addRow("自動入力するユーザーID", self._last_user_edit)
        form_layout.addRow("自動入力するパスワード", self._last_password_edit)

        layout.addLayout(form_layout)
        layout.addWidget(self._structure_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        layout.addWidget(buttons)

        self._root_button.clicked.connect(self._choose_root)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

    # UI イベント ------------------------------------------------------
    def _choose_root(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "プロジェクトルートを選択")
        if not selected:
            return
        self._root_edit.setText(selected)
        self._update_structure_status()

    def _on_accept(self) -> None:
        if not self._validate_inputs():
            return
        if self._structure_report and not self._structure_report.is_valid:
            result = QMessageBox.warning(
                self,
                "警告",
                "既定のプロジェクト構成と一致しない項目があります。保存しますか？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if result != QMessageBox.StandardButton.Yes:
                return
        self._apply_changes()
        self.accept()

    # 検証 ------------------------------------------------------------
    def _validate_inputs(self) -> bool:
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "入力エラー", "プロジェクト名を入力してください。")
            return False
        root_text = self._root_edit.text().strip()
        if not root_text:
            QMessageBox.warning(self, "入力エラー", "プロジェクトルートを指定してください。")
            return False
        return True

    def _update_structure_status(self) -> None:
        root = Path(self._root_edit.text().strip())
        if not root:
            self._structure_label.setText("プロジェクトルートを指定してください。")
            self._structure_label.setStyleSheet("color: #d9534f;")
            self._structure_report = None
            return
        report = validate_project_structure(root)
        self._structure_report = report
        if report.is_valid:
            self._structure_label.setText("既定の構成を満たしています。")
            self._structure_label.setStyleSheet("color: #198754;")
        else:
            self._structure_label.setText(report.summary())
            self._structure_label.setStyleSheet("color: #d9534f;")

    def _apply_changes(self) -> None:
        root = Path(self._root_edit.text().strip())
        self._edited_settings = ProjectSettings(
            project_name=self._name_edit.text().strip(),
            description=self._description_edit.toPlainText().strip(),
            project_root=root,
            auto_fill_credentials=self._auto_fill_checkbox.isChecked(),
            last_user_id=self._last_user_edit.text().strip() or None,
            last_user_password=self._last_password_edit.text() or None,
        )

    # 公開 API --------------------------------------------------------
    def settings(self) -> ProjectSettings:
        return self._edited_settings
