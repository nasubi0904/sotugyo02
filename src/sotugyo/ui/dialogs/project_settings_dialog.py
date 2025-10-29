"""プロジェクト設定ダイアログ。"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from ....domain.projects import ProjectSettings, ProjectStructureReport, validate_structure
from ..style import apply_base_style


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
            auto_fill_user_id=settings.auto_fill_user_id,
            auto_fill_password=settings.auto_fill_password,
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
        self._auto_fill_id_checkbox = QCheckBox("前回ユーザーのIDを自動入力する", self)
        self._auto_fill_id_checkbox.setChecked(settings.auto_fill_user_id)
        self._auto_fill_password_checkbox = QCheckBox("前回ユーザーのパスワードを自動入力する", self)
        self._auto_fill_password_checkbox.setChecked(settings.auto_fill_password)
        self._structure_label = QLabel("", self)
        self._structure_label.setObjectName("structureStatusLabel")
        self._structure_label.setWordWrap(True)
        self._structure_label.setProperty("status", "warning")

        self._build_ui()
        self._update_structure_status()
        apply_base_style(self)
        status = self._structure_label.property("status")
        if isinstance(status, str) and status:
            self._set_structure_status(status)

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

        header = QLabel("プロジェクト設定", card)
        header.setObjectName("panelTitle")
        card_layout.addWidget(header)

        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignLeft)
        form_layout.setFormAlignment(Qt.AlignTop)
        form_layout.setHorizontalSpacing(18)
        form_layout.setVerticalSpacing(14)
        form_layout.addRow("プロジェクト名", self._name_edit)
        form_layout.addRow("プロジェクト概要", self._description_edit)

        root_layout = QHBoxLayout()
        root_layout.setSpacing(12)
        root_layout.addWidget(self._root_edit, 1)
        root_layout.addWidget(self._root_button)
        form_layout.addRow("プロジェクトルート", root_layout)

        form_layout.addRow(self._auto_fill_id_checkbox)
        form_layout.addRow(self._auto_fill_password_checkbox)

        card_layout.addLayout(form_layout)
        card_layout.addWidget(self._structure_label)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, card)
        card_layout.addWidget(button_box, 0, Qt.AlignRight)

        outer_layout.addWidget(card)

        self._root_button.clicked.connect(self._choose_root)
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)

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
            self._set_structure_status("error")
            self._structure_report = None
            return
        report = validate_structure(root)
        self._structure_report = report
        if report.is_valid:
            self._structure_label.setText("既定の構成を満たしています。")
            self._set_structure_status("ok")
        else:
            self._structure_label.setText(report.summary())
            self._set_structure_status("error")

    def _apply_changes(self) -> None:
        root = Path(self._root_edit.text().strip())
        self._edited_settings = ProjectSettings(
            project_name=self._name_edit.text().strip(),
            description=self._description_edit.toPlainText().strip(),
            project_root=root,
            auto_fill_user_id=self._auto_fill_id_checkbox.isChecked(),
            auto_fill_password=self._auto_fill_password_checkbox.isChecked(),
            last_user_id=self._original_settings.last_user_id,
            last_user_password=self._original_settings.last_user_password,
        )

    # 公開 API --------------------------------------------------------
    def settings(self) -> ProjectSettings:
        return self._edited_settings

    def _set_structure_status(self, status: str) -> None:
        self._structure_label.setProperty("status", status)
        style = self._structure_label.style()
        if style is not None:
            style.unpolish(self._structure_label)
            style.polish(self._structure_label)
        self._structure_label.update()
