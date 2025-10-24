"""ツール登録を管理するダイアログ。"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...domain.tooling.models import TemplateInstallationCandidate
from ...domain.tooling.service import ToolEnvironmentService


class ToolRegistryDialog(QDialog):
    """登録済みツールの一覧と追加・削除を行う。"""

    def __init__(self, service: ToolEnvironmentService, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._service = service
        self._tool_list: Optional[QTreeWidget] = None
        self._status_label: Optional[QLabel] = None
        self._refresh_on_accept = False

        self.setWindowTitle("ツール環境設定")
        self.resize(560, 420)

        self._build_ui()
        self._refresh_tool_list()

    def refresh_requested(self) -> bool:
        return self._refresh_on_accept

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        description = QLabel(
            "マシンに登録する DCC ツールを管理します。追加したツールは環境定義で利用できます。",
            self,
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        tool_list = QTreeWidget(self)
        tool_list.setColumnCount(4)
        tool_list.setHeaderLabels(["表示名", "テンプレート", "バージョン", "実行ファイル"])
        tool_list.setRootIsDecorated(False)
        tool_list.setAlternatingRowColors(True)
        tool_list.setSelectionMode(QAbstractItemView.SingleSelection)
        tool_list.setSelectionBehavior(QAbstractItemView.SelectRows)
        tool_list.setUniformRowHeights(True)
        tool_list.setAllColumnsShowFocus(True)
        layout.addWidget(tool_list, 1)
        self._tool_list = tool_list

        button_row = QHBoxLayout()
        add_button = QPushButton("ツールを追加")
        add_button.clicked.connect(self._open_add_menu)
        auto_button = QPushButton("テンプレート自動登録")
        auto_button.clicked.connect(self._auto_register_all_templates)
        remove_button = QPushButton("選択ツールを削除")
        remove_button.clicked.connect(self._remove_selected_tool)
        button_row.addWidget(add_button)
        button_row.addWidget(auto_button)
        button_row.addWidget(remove_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        status_label = QLabel("登録されているツール数: 0", self)
        status_label.setObjectName("statusLabel")
        layout.addWidget(status_label)
        self._status_label = status_label

        buttons = QDialogButtonBox(QDialogButtonBox.Close, Qt.Horizontal, self)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _refresh_tool_list(self) -> None:
        if self._tool_list is None:
            return
        try:
            tools = self._service.list_tools()
        except OSError as exc:
            QMessageBox.critical(self, "エラー", f"ツールの読み込みに失敗しました: {exc}")
            tools = []
        self._tool_list.clear()
        for tool in tools:
            item = QTreeWidgetItem(
                [
                    tool.display_name,
                    tool.template_id or "-",
                    tool.version or "-",
                    str(tool.executable_path),
                ]
            )
            item.setData(0, Qt.UserRole, tool.tool_id)
            self._tool_list.addTopLevelItem(item)
        self._tool_list.resizeColumnToContents(0)
        self._tool_list.resizeColumnToContents(1)
        self._tool_list.resizeColumnToContents(2)
        if self._status_label is not None:
            self._status_label.setText(f"登録されているツール数: {len(tools)}")

    def _open_add_menu(self) -> None:
        button = self.sender()
        if not isinstance(button, QPushButton):
            return
        menu = QMenu(self)
        template_action = menu.addAction("テンプレートから追加")
        template_action.triggered.connect(self._open_template_registration)
        direct_action = menu.addAction("実行ファイルを指定")
        direct_action.triggered.connect(self._open_direct_registration)
        menu.exec(button.mapToGlobal(button.rect().bottomLeft()))

    def _open_template_registration(self) -> None:
        dialog = ToolRegistrationDialog(self._service, self, mode="template")
        if dialog.exec() != QDialog.Accepted:
            return
        self._register_tool(dialog.result_payload())

    def _open_direct_registration(self) -> None:
        dialog = ToolRegistrationDialog(self._service, self, mode="direct")
        if dialog.exec() != QDialog.Accepted:
            return
        self._register_tool(dialog.result_payload())

    def _register_tool(self, payload: Optional[dict]) -> None:
        if not payload:
            return
        try:
            self._service.register_tool(**payload)
        except ValueError as exc:
            QMessageBox.warning(self, "登録に失敗", str(exc))
            return
        except OSError as exc:
            QMessageBox.critical(self, "登録に失敗", str(exc))
            return
        self._refresh_on_accept = True
        self._refresh_tool_list()

    def _remove_selected_tool(self) -> None:
        if self._tool_list is None:
            return
        current = self._tool_list.currentItem()
        if current is None:
            QMessageBox.information(self, "削除", "削除するツールを選択してください。")
            return
        tool_id = current.data(0, Qt.UserRole)
        if not isinstance(tool_id, str):
            return
        reply = QMessageBox.question(
            self,
            "確認",
            "選択したツールを削除しますか？関連する環境定義も削除されます。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            removed = self._service.remove_tool(tool_id)
        except OSError as exc:
            QMessageBox.critical(self, "削除に失敗", str(exc))
            return
        if not removed:
            QMessageBox.warning(self, "削除", "指定されたツールが見つかりませんでした。")
            return
        self._refresh_on_accept = True
        self._refresh_tool_list()

    def _auto_register_all_templates(self) -> None:
        templates = self._service.list_templates()
        if not templates:
            QMessageBox.information(self, "自動登録", "利用可能なテンプレートが定義されていません。")
            return

        registered = 0
        skipped = 0
        errors: List[str] = []

        for template in templates:
            template_id = template.get("template_id")
            if not template_id:
                continue
            candidates = self._service.discover_template_installations(template_id)
            for candidate in candidates:
                try:
                    self._service.register_tool(
                        display_name=candidate.display_name,
                        executable_path=candidate.executable_path,
                        template_id=candidate.template_id,
                        version=candidate.version,
                    )
                except ValueError:
                    skipped += 1
                except OSError as exc:
                    errors.append(f"{candidate.display_name}: {exc}")
                else:
                    registered += 1

        if registered == 0 and skipped == 0 and not errors:
            QMessageBox.information(
                self,
                "自動登録",
                "テンプレートから登録可能なインストールは見つかりませんでした。",
            )
            return

        messages: List[str] = []
        if registered:
            messages.append(f"{registered} 件のツールを登録しました。")
        if skipped:
            messages.append(f"{skipped} 件は既に登録済みのためスキップしました。")
        if errors:
            messages.append("一部のインストールでエラーが発生しました:")
            messages.extend(errors)
            QMessageBox.warning(self, "自動登録", "\n".join(messages))
        else:
            QMessageBox.information(self, "自動登録", "\n".join(messages))

        if registered or skipped:
            self._refresh_on_accept = True
            self._refresh_tool_list()


class ToolRegistrationDialog(QDialog):
    """テンプレートまたは直接指定でツールを登録する。"""

    def __init__(
        self,
        service: ToolEnvironmentService,
        parent: Optional[QWidget] = None,
        *,
        mode: str = "template",
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._mode = mode
        self._stack: Optional[QTabWidget] = None
        self._template_selector: Optional[QListWidget] = None
        self._candidate_list: Optional[QListWidget] = None
        self._template_candidates: List[TemplateInstallationCandidate] = []
        self._direct_name: Optional[QLineEdit] = None
        self._direct_path: Optional[QLineEdit] = None
        self._direct_version: Optional[QLineEdit] = None
        self._template_version: Optional[QLineEdit] = None
        self._template_name: Optional[QLineEdit] = None
        self._result: Optional[dict] = None

        self.setWindowTitle("ツールの追加")
        self.resize(480, 360)

        self._build_ui()
        if self._stack is not None:
            if mode == "template":
                self._stack.setCurrentIndex(0)
                self._populate_templates()
            else:
                self._stack.setCurrentIndex(1)

    def result_payload(self) -> Optional[dict]:
        return self._result

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self._stack = QTabWidget(self)
        self._stack.setTabBarAutoHide(True)
        layout.addWidget(self._stack, 1)

        template_page = QWidget(self._stack)
        template_layout = QVBoxLayout(template_page)
        template_layout.setContentsMargins(0, 0, 0, 0)
        template_layout.setSpacing(8)

        instructions = QLabel(
            "テンプレートを選択し、検出されたインストールから登録します。",
            template_page,
        )
        instructions.setWordWrap(True)
        template_layout.addWidget(instructions)

        self._template_selector = QListWidget(template_page)
        self._template_selector.itemSelectionChanged.connect(self._on_template_changed)
        template_layout.addWidget(self._template_selector, 1)

        candidate_group = QGroupBox("検出されたインストール", template_page)
        candidate_layout = QVBoxLayout(candidate_group)
        candidate_layout.setContentsMargins(8, 8, 8, 8)
        candidate_layout.setSpacing(6)

        self._candidate_list = QListWidget(candidate_group)
        self._candidate_list.itemSelectionChanged.connect(self._on_candidate_selected)
        candidate_layout.addWidget(self._candidate_list, 1)

        form_group = QGroupBox("登録情報", template_page)
        form_layout = QGridLayout(form_group)
        form_layout.setContentsMargins(8, 8, 8, 8)
        form_layout.setHorizontalSpacing(6)
        form_layout.setVerticalSpacing(6)

        form_layout.addWidget(QLabel("表示名", form_group), 0, 0)
        self._template_name = QLineEdit(form_group)
        form_layout.addWidget(self._template_name, 0, 1)

        form_layout.addWidget(QLabel("バージョン", form_group), 1, 0)
        self._template_version = QLineEdit(form_group)
        form_layout.addWidget(self._template_version, 1, 1)

        template_layout.addWidget(candidate_group)
        template_layout.addWidget(form_group)

        self._stack.addTab(template_page, "テンプレート")

        direct_page = QWidget(self._stack)
        direct_layout = QGridLayout(direct_page)
        direct_layout.setContentsMargins(0, 0, 0, 0)
        direct_layout.setHorizontalSpacing(8)
        direct_layout.setVerticalSpacing(8)

        direct_layout.addWidget(QLabel("表示名", direct_page), 0, 0)
        self._direct_name = QLineEdit(direct_page)
        direct_layout.addWidget(self._direct_name, 0, 1, 1, 2)

        direct_layout.addWidget(QLabel("実行ファイル", direct_page), 1, 0)
        self._direct_path = QLineEdit(direct_page)
        browse_button = QPushButton("参照", direct_page)
        browse_button.clicked.connect(self._browse_executable)
        direct_layout.addWidget(self._direct_path, 1, 1)
        direct_layout.addWidget(browse_button, 1, 2)

        direct_layout.addWidget(QLabel("バージョン", direct_page), 2, 0)
        self._direct_version = QLineEdit(direct_page)
        direct_layout.addWidget(self._direct_version, 2, 1, 1, 2)

        self._stack.addTab(direct_page, "直接指定")

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal,
            self,
        )
        buttons.accepted.connect(self._handle_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        for template in self._service.list_templates():
            item = QListWidgetItem(template.get("label", "テンプレート"))
            item.setData(Qt.UserRole, template.get("template_id"))
            if self._template_selector is not None:
                self._template_selector.addItem(item)

    def _populate_templates(self) -> None:
        if self._template_selector is not None and self._template_selector.count() > 0:
            self._template_selector.setCurrentRow(0)

    def _on_template_changed(self) -> None:
        selected = self._template_selector.currentItem()
        if selected is None:
            return
        template_id = selected.data(Qt.UserRole)
        if not isinstance(template_id, str):
            return
        self._candidate_list.clear()
        self._template_candidates = self._service.discover_template_installations(template_id)
        if not self._template_candidates:
            empty = QListWidgetItem("該当するインストールが見つかりませんでした。")
            empty.setFlags(Qt.NoItemFlags)
            self._candidate_list.addItem(empty)
            self._template_name.setText(selected.text())
            self._template_version.setText("")
            return
        for candidate in self._template_candidates:
            item = QListWidgetItem(f"{candidate.display_name}\n{candidate.executable_path}")
            item.setData(Qt.UserRole, candidate)
            self._candidate_list.addItem(item)
        self._candidate_list.setCurrentRow(0)

    def _on_candidate_selected(self) -> None:
        selected = self._candidate_list.currentItem()
        if selected is None:
            return
        candidate = selected.data(Qt.UserRole)
        if isinstance(candidate, TemplateInstallationCandidate):
            self._template_name.setText(candidate.display_name)
            self._template_version.setText(candidate.version or "")

    def _browse_executable(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "実行ファイルを選択",
            str(Path.home()),
            "実行ファイル (*.exe);;すべてのファイル (*)",
        )
        if filename and self._direct_path is not None:
            self._direct_path.setText(filename)
            if self._direct_name is not None and not self._direct_name.text().strip():
                self._direct_name.setText(Path(filename).stem)

    def _handle_accept(self) -> None:
        if self._stack.currentIndex() == 0:
            payload = self._build_template_payload()
        else:
            payload = self._build_direct_payload()
        if not payload:
            return
        self._result = payload
        self.accept()

    def _build_template_payload(self) -> Optional[dict]:
        candidate_item = self._candidate_list.currentItem() if self._candidate_list else None
        candidate = (
            candidate_item.data(Qt.UserRole)
            if candidate_item is not None
            else None
        )
        if not isinstance(candidate, TemplateInstallationCandidate):
            QMessageBox.warning(self, "入力不備", "登録するインストールを選択してください。")
            return None
        name = self._template_name.text().strip() if self._template_name else ""
        version = self._template_version.text().strip() if self._template_version else ""
        return {
            "display_name": name or candidate.display_name,
            "executable_path": candidate.executable_path,
            "template_id": candidate.template_id,
            "version": version or candidate.version,
        }

    def _build_direct_payload(self) -> Optional[dict]:
        if self._direct_path is None:
            return None
        path_text = self._direct_path.text().strip()
        if not path_text:
            QMessageBox.warning(self, "入力不備", "実行ファイルを指定してください。")
            return None
        name = self._direct_name.text().strip() if self._direct_name else ""
        version = self._direct_version.text().strip() if self._direct_version else ""
        return {
            "display_name": name or Path(path_text).stem,
            "executable_path": path_text,
            "template_id": None,
            "version": version or None,
        }
