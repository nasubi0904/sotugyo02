"""ノード編集画面のウィンドウ実装。"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFrame,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from NodeGraphQt import NodeGraph, Port

from .nodes import ReviewNode, TaskNode
from ..settings.project_registry import ProjectRecord, ProjectRegistry
from ..settings.project_settings import ProjectSettings, load_project_settings, save_project_settings
from ..settings.project_structure import ensure_project_structure, validate_project_structure
from ..settings.user_settings import UserAccount, UserSettingsManager
from .project_settings_dialog import ProjectSettingsDialog
from .user_settings_dialog import UserSettingsDialog


class NodeContentBrowser(QWidget):
    """ノード追加と検索をまとめたコンテンツブラウザ風ウィジェット。"""

    node_type_requested = Signal(str)
    search_submitted = Signal(str)
    back_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._search_line: QLineEdit = QLineEdit(self)
        self._available_list: QListWidget = QListWidget(self)
        self._available_entries: List[Dict[str, str]] = []

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        title_label = QLabel("コンテンツブラウザ", self)
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        header_layout.addWidget(title_label)
        header_layout.addStretch(1)

        back_button = QPushButton("スタート画面に戻る", self)
        back_button.clicked.connect(self.back_requested.emit)
        header_layout.addWidget(back_button)

        layout.addLayout(header_layout)

        search_layout = QHBoxLayout()
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(8)

        self._search_line.setPlaceholderText("ノードを検索")
        search_layout.addWidget(self._search_line, 1)

        layout.addLayout(search_layout)

        self._configure_list_widget(self._available_list)

        layout.addWidget(
            self._build_section("追加可能ノード", self._available_list),
            1,
        )

    def _configure_list_widget(self, widget: QListWidget) -> None:
        widget.setViewMode(QListWidget.IconMode)
        widget.setMovement(QListWidget.Static)
        widget.setResizeMode(QListWidget.Adjust)
        widget.setWrapping(True)
        widget.setIconSize(QSize(48, 48))
        widget.setSpacing(8)
        widget.setSelectionMode(QAbstractItemView.SingleSelection)
        widget.setUniformItemSizes(True)

    def _build_section(self, title: str, widget: QListWidget) -> QWidget:
        frame = QFrame(self)
        frame.setFrameShape(QFrame.StyledPanel)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(8, 8, 8, 8)
        frame_layout.setSpacing(6)

        label = QLabel(title, frame)
        label.setStyleSheet("font-weight: bold;")
        frame_layout.addWidget(label)
        frame_layout.addWidget(widget, 1)

        return frame

    def _connect_signals(self) -> None:
        self._search_line.textChanged.connect(self._apply_filter)
        self._search_line.returnPressed.connect(self._on_search_submitted)
        self._available_list.itemActivated.connect(self._on_available_item_activated)

    def set_available_nodes(self, entries: List[Dict[str, str]]) -> None:
        self._available_entries = entries
        self._available_list.clear()
        for entry in entries:
            title = entry.get("title", "")
            subtitle = entry.get("subtitle", "")
            node_type = entry.get("type", "")
            item = QListWidgetItem(f"{title}\n{subtitle}")
            item.setData(Qt.UserRole, node_type)
            item.setToolTip(node_type)
            item.setSizeHint(QSize(180, 72))
            self._available_list.addItem(item)
        self._apply_filter()

    def focus_search(self) -> None:
        self._search_line.setFocus()
        self._search_line.selectAll()

    def current_search_text(self) -> str:
        return self._search_line.text()

    def first_visible_available_type(self) -> Optional[str]:
        for index in range(self._available_list.count()):
            item = self._available_list.item(index)
            if item is not None and not item.isHidden():
                data = item.data(Qt.UserRole)
                if isinstance(data, str):
                    return data
        return None

    def _apply_filter(self) -> None:
        keyword = self._search_line.text().strip().lower()
        for index in range(self._available_list.count()):
            item = self._available_list.item(index)
            if item is None:
                continue
            text = item.text().lower()
            item.setHidden(bool(keyword) and keyword not in text)

    def _on_search_submitted(self) -> None:
        self.search_submitted.emit(self._search_line.text())

    def _on_available_item_activated(self, item: QListWidgetItem) -> None:
        if item is None:
            return
        node_type = item.data(Qt.UserRole)
        if isinstance(node_type, str):
            self.node_type_requested.emit(node_type)

class NodeEditorWindow(QMainWindow):
    """NodeGraphQt を用いたノード編集画面。"""

    WINDOW_TITLE = "ノード編集テスト"
    return_to_start_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.WINDOW_TITLE)
        self._base_window_title = self.windowTitle()
        self.resize(960, 600)

        self._graph = NodeGraph()
        self._graph.register_node(TaskNode)
        self._graph.register_node(ReviewNode)

        self._graph_widget = self._graph.widget
        self._graph_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._node_spawn_offset = 0
        self._task_count = 0
        self._review_count = 0
        self._current_node = None
        self._known_nodes: List = []
        self._is_modified = False
        self._current_project_root: Optional[Path] = None
        self._current_project_settings: Optional[ProjectSettings] = None
        self._current_user: Optional[UserAccount] = None
        self._current_user_password: Optional[str] = None
        self._registry = ProjectRegistry()
        self._user_manager = UserSettingsManager()

        self._side_tabs: Optional[QTabWidget] = None
        self._detail_name_label: Optional[QLabel] = None
        self._detail_type_label: Optional[QLabel] = None
        self._detail_position_label: Optional[QLabel] = None
        self._rename_input: Optional[QLineEdit] = None
        self._rename_button: Optional[QPushButton] = None
        self._content_browser: Optional[NodeContentBrowser] = None
        self._shortcuts: List[QShortcut] = []
        self._node_type_creators = {
            "sotugyo.demo.TaskNode": self._create_task_node,
            "sotugyo.demo.ReviewNode": self._create_review_node,
        }

        self._init_ui()
        self._create_menus()
        self._setup_graph_signals()
        self._setup_context_menu()
        self._setup_shortcuts()
        self._initialize_content_browser()
        self._update_selected_node_info()
        self._refresh_node_catalog()
        self._set_modified(False)

    # ------------------------------------------------------------------
    # UI 初期化
    # ------------------------------------------------------------------
    def _init_ui(self) -> None:
        container = QWidget(self)
        root_layout = QVBoxLayout(container)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        main_panel = QWidget(container)
        content_layout = QHBoxLayout(main_panel)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self._side_tabs = QTabWidget(main_panel)
        self._side_tabs.setMinimumWidth(260)
        self._side_tabs.addTab(self._build_detail_tab(), "ノード詳細")
        self._side_tabs.addTab(self._build_operation_tab(), "ノード操作")

        content_layout.addWidget(self._graph_widget, 1)
        content_layout.addWidget(self._side_tabs)

        splitter = QSplitter(Qt.Vertical, container)
        splitter.addWidget(main_panel)
        self._content_browser = NodeContentBrowser(splitter)
        self._content_browser.node_type_requested.connect(self._spawn_node_by_type)
        self._content_browser.search_submitted.connect(self._handle_content_browser_search)
        self._content_browser.back_requested.connect(self._return_to_start)
        self._content_browser.setMinimumHeight(160)

        splitter.addWidget(self._content_browser)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([420, 180])

        root_layout.addWidget(splitter, 1)

        self.setCentralWidget(container)

    def _create_menus(self) -> None:
        menubar = self.menuBar()

        file_menu = menubar.addMenu("File")

        save_action = QAction("上書き保存", self)
        save_action.triggered.connect(self._file_save)
        save_action.setShortcut(QKeySequence.Save)
        file_menu.addAction(save_action)

        import_action = QAction("アセットをインポート...", self)
        import_action.triggered.connect(self._file_import)
        import_action.setShortcut(QKeySequence.Open)
        file_menu.addAction(import_action)

        file_menu.addSeparator()

        return_action = QAction("スタート画面に戻る", self)
        return_action.triggered.connect(self._return_to_start)
        file_menu.addAction(return_action)

        project_menu = menubar.addMenu("ProjectSetting")
        project_settings_action = QAction("プロジェクト設定...", self)
        project_settings_action.triggered.connect(self._open_project_settings)
        project_menu.addAction(project_settings_action)

        user_menu = menubar.addMenu("UserSetting")
        user_settings_action = QAction("ユーザー設定...", self)
        user_settings_action.triggered.connect(self._open_user_settings)
        user_menu.addAction(user_settings_action)

    def _build_detail_tab(self) -> QWidget:
        widget = QWidget(self)
        layout = QFormLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self._detail_name_label = QLabel("-", widget)
        self._detail_type_label = QLabel("-", widget)
        self._detail_position_label = QLabel("-", widget)

        layout.addRow("名前", self._detail_name_label)
        layout.addRow("タイプ", self._detail_type_label)
        layout.addRow("位置", self._detail_position_label)

        return widget

    def _build_operation_tab(self) -> QWidget:
        widget = QWidget(self)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        rename_label = QLabel("名前の変更", widget)
        self._rename_input = QLineEdit(widget)
        self._rename_input.setPlaceholderText("ノード名を入力")

        self._rename_button = QPushButton("名前を更新", widget)
        self._rename_button.clicked.connect(self._apply_node_rename)

        layout.addWidget(rename_label)
        layout.addWidget(self._rename_input)
        layout.addWidget(self._rename_button)
        layout.addStretch(1)

        return widget

    def _open_project_settings(self) -> None:
        if self._current_project_root is None:
            self._show_info_dialog("プロジェクトが選択されていません。")
            return
        if self._current_project_settings is None:
            self._current_project_settings = load_project_settings(self._current_project_root)
        dialog = ProjectSettingsDialog(self._current_project_settings, self)
        if dialog.exec() != QDialog.Accepted:
            return
        updated = dialog.settings()
        try:
            save_project_settings(updated)
        except OSError as exc:
            self._show_error_dialog(f"設定の保存に失敗しました: {exc}")
            return
        root_changed = updated.project_root != self._current_project_root
        name_changed = (
            self._current_project_settings.project_name != updated.project_name
            if self._current_project_settings
            else True
        )
        self._current_project_settings = updated
        self._registry.register_project(ProjectRecord(updated.project_name, updated.project_root))
        if root_changed:
            if not self._confirm_discard_changes(
                "プロジェクトルートが変更されます。未保存の編集内容は失われます。続行しますか？"
            ):
                return
            if not self._confirm_project_change(updated.project_name):
                return
            self._current_project_root = updated.project_root
            self._load_project_graph()
        self._refresh_window_title()
        if name_changed or root_changed:
            self._notify_start_window_refresh()

    def _open_user_settings(self) -> None:
        dialog = UserSettingsDialog(self._user_manager, self)
        if dialog.exec() == QDialog.Accepted:
            if self._current_user is not None:
                refreshed = self._user_manager.get_account(self._current_user.user_id)
                if refreshed is not None:
                    self._current_user = refreshed
            self._refresh_window_title()
            self._notify_start_window_refresh()

    def _setup_graph_signals(self) -> None:
        selection_signal = getattr(self._graph, "selection_changed", None)
        if selection_signal is not None and hasattr(selection_signal, "connect"):
            selection_signal.connect(self._on_selection_changed)
        else:
            selection_signal = getattr(self._graph, "node_selection_changed", None)
            if selection_signal is not None and hasattr(selection_signal, "connect"):
                selection_signal.connect(self._on_selection_changed)

    def _setup_context_menu(self) -> None:
        if hasattr(self._graph_widget, "setContextMenuPolicy"):
            self._graph_widget.setContextMenuPolicy(Qt.CustomContextMenu)
            self._graph_widget.customContextMenuRequested.connect(
                self._open_graph_context_menu
            )

    def _setup_shortcuts(self) -> None:
        self._shortcuts.clear()

        def register(sequence: QKeySequence | str, callback) -> None:
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.setContext(Qt.WidgetWithChildrenShortcut)
            shortcut.activated.connect(callback)
            self._shortcuts.append(shortcut)

        register("Delete", self._delete_selected_nodes)
        register("Ctrl+S", self._file_save)
        register("Ctrl+O", self._file_import)
        register("Ctrl+F", self._focus_content_browser_search)
        register("Ctrl+Shift+C", self._connect_selected_nodes)
        register("Ctrl+Shift+D", self._disconnect_selected_nodes)
        register("Ctrl+T", self._create_task_node)
        register("Ctrl+R", self._create_review_node)

    def _initialize_content_browser(self) -> None:
        if self._content_browser is None:
            return
        self._content_browser.set_available_nodes(self._build_available_node_entries())

    # ------------------------------------------------------------------
    # プロジェクトコンテキスト管理
    # ------------------------------------------------------------------
    def prepare_context(
        self,
        project_root: Path,
        settings: ProjectSettings,
        user: UserAccount,
        password: str,
    ) -> bool:
        project_root = Path(project_root)
        if self._current_project_root is not None and project_root != self._current_project_root:
            if not self._confirm_discard_changes(
                "未保存の変更があります。プロジェクトを切り替えますか？"
            ):
                return False
            if not self._confirm_project_change(settings.project_name):
                return False
        if self._current_user is not None and user.user_id != self._current_user.user_id:
            result = QMessageBox.warning(
                self,
                "確認",
                f"ユーザーを「{user.display_name}」に切り替えます。続行しますか？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if result != QMessageBox.StandardButton.Yes:
                return False

        refreshed = self._user_manager.get_account(user.user_id)
        if refreshed is not None:
            user = refreshed

        self._current_project_root = project_root
        self._current_project_settings = load_project_settings(project_root)
        self._current_user = user
        self._current_user_password = password

        effective_settings = self._current_project_settings or settings
        self._registry.register_project(
            ProjectRecord(effective_settings.project_name, project_root)
        )
        self._registry.set_last_project(project_root)
        ensure_project_structure(project_root)

        self._refresh_window_title()
        self._load_project_graph()

        report = validate_project_structure(project_root)
        if not report.is_valid:
            QMessageBox.warning(
                self,
                "警告",
                "既定のプロジェクト構成に不足があります。\n" + report.summary(),
            )

        self._notify_start_window_refresh()
        return True

    def _build_available_node_entries(self) -> List[Dict[str, str]]:
        return [
            {
                "type": "sotugyo.demo.TaskNode",
                "title": TaskNode.NODE_NAME,
                "subtitle": "工程を構成するタスクノード",
            },
            {
                "type": "sotugyo.demo.ReviewNode",
                "title": ReviewNode.NODE_NAME,
                "subtitle": "成果物を検証するレビューノード",
            },
        ]

    def _open_graph_context_menu(self, position: QPoint) -> None:
        menu = QMenu(self)

        add_task_action = menu.addAction("タスクノードを追加")
        add_task_action.triggered.connect(self._create_task_node)

        add_review_action = menu.addAction("レビューノードを追加")
        add_review_action.triggered.connect(self._create_review_node)

        menu.addSeparator()

        delete_action = menu.addAction("選択ノードを削除")
        delete_action.triggered.connect(self._delete_selected_nodes)

        connect_action = menu.addAction("選択ノードを接続")
        connect_action.triggered.connect(self._connect_selected_nodes)

        disconnect_action = menu.addAction("選択ノードを切断")
        disconnect_action.triggered.connect(self._disconnect_selected_nodes)

        menu.addSeparator()

        search_action = menu.addAction("ノード検索を開く")
        search_action.triggered.connect(self._focus_content_browser_search)

        selected_nodes = self._graph.selected_nodes()
        delete_action.setEnabled(bool(selected_nodes))
        connect_action.setEnabled(len(selected_nodes) == 2)
        disconnect_action.setEnabled(len(selected_nodes) == 2)

        global_pos = self._graph_widget.mapToGlobal(position)
        menu.exec(global_pos)

    def _focus_content_browser_search(self) -> None:
        if self._content_browser is not None:
            self._content_browser.focus_search()

    def _handle_content_browser_search(self, keyword: str) -> None:
        if self._content_browser is None:
            return
        keyword = keyword.strip()
        if not keyword:
            self._show_info_dialog("検索キーワードを入力してください。")
            return

        if self._search_nodes(keyword, show_dialog=False) is not None:
            return

        available_type = self._content_browser.first_visible_available_type()
        if available_type is not None:
            self._spawn_node_by_type(available_type)
            return

        self._show_info_dialog(f"「{keyword}」に一致するノードが見つかりません。")

    def _spawn_node_by_type(self, node_type: str) -> None:
        creator = self._node_type_creators.get(node_type)
        if creator is not None:
            creator()
            return
        display_name = self._derive_display_name(node_type)
        self._create_node(node_type, display_name)

    def _derive_display_name(self, node_type: str) -> str:
        base_name = node_type.split(".")[-1] if node_type else "ノード"
        return f"{base_name} {self._node_spawn_offset + 1}"

    # ------------------------------------------------------------------
    # ノード生成・削除
    # ------------------------------------------------------------------
    def _create_task_node(self) -> None:
        self._task_count += 1
        self._create_node("sotugyo.demo.TaskNode", f"タスク {self._task_count}")

    def _create_review_node(self) -> None:
        self._review_count += 1
        self._create_node("sotugyo.demo.ReviewNode", f"レビュー {self._review_count}")

    def _create_asset_node(self, asset_name: str) -> None:
        title = asset_name.strip() or "アセット"
        self._create_node("sotugyo.demo.TaskNode", f"Asset: {title}")

    def _create_node(self, node_type: str, display_name: str) -> None:
        node = self._graph.create_node(node_type, name=display_name)
        pos_x = (self._node_spawn_offset % 4) * 220
        pos_y = (self._node_spawn_offset // 4) * 180
        node.set_pos(pos_x, pos_y)
        self._node_spawn_offset += 1
        self._known_nodes.append(node)
        self._set_modified(True)

        clear_selection = getattr(self._graph, "clear_selection", None)
        if callable(clear_selection):
            clear_selection()
        if hasattr(node, "set_selected"):
            node.set_selected(True)
        self._on_selection_changed()
        self._refresh_node_catalog()

    def _delete_selected_nodes(self) -> None:
        nodes = self._graph.selected_nodes()
        if not nodes:
            self._show_info_dialog("削除するノードを選択してください。")
            return
        self._graph.delete_nodes(nodes)
        self._known_nodes = [node for node in self._known_nodes if node not in nodes]
        self._on_selection_changed()
        self._set_modified(True)
        self._refresh_node_catalog()

    # ------------------------------------------------------------------
    # 接続処理
    # ------------------------------------------------------------------
    def _connect_selected_nodes(self) -> None:
        nodes = self._graph.selected_nodes()
        if len(nodes) != 2:
            self._show_info_dialog("接続する 2 つのノードを選択してください。")
            return

        source, target = self._sort_nodes_by_position(nodes)
        source_port = self._first_output_port(source)
        target_port = self._first_input_port(target)
        if not source_port or not target_port:
            self._show_info_dialog("接続できるポートが見つかりませんでした。")
            return
        self._graph.connect_ports(source_port, target_port)
        self._set_modified(True)

    def _disconnect_selected_nodes(self) -> None:
        nodes = self._graph.selected_nodes()
        if len(nodes) != 2:
            self._show_info_dialog("切断する 2 つのノードを選択してください。")
            return

        source, target = self._sort_nodes_by_position(nodes)
        source_port = self._first_output_port(source)
        target_port = self._first_input_port(target)
        if not source_port or not target_port:
            self._show_info_dialog("切断できるポートが見つかりませんでした。")
            return

        disconnected = False
        for connected_port in list(source_port.connected_ports()):
            if connected_port.node() is target:
                self._graph.disconnect_ports(source_port, connected_port)
                disconnected = True
                self._set_modified(True)
        if not disconnected:
            self._show_info_dialog("選択されたノード間に接続が存在しません。")

    # ------------------------------------------------------------------
    # ユーティリティ
    # ------------------------------------------------------------------
    def _select_single_node(self, node) -> None:
        clear_selection = getattr(self._graph, "clear_selection", None)
        if callable(clear_selection):
            clear_selection()
        if hasattr(node, "set_selected"):
            try:
                node.set_selected(True)
            except Exception:
                pass
        view_item = getattr(node, "view", None)
        if hasattr(self._graph_widget, "centerOn") and view_item is not None:
            try:
                self._graph_widget.centerOn(view_item)
            except Exception:
                pass
        self._on_selection_changed()

    def _refresh_node_catalog(self) -> None:
        """既存ノード一覧を廃止したため更新処理は不要。"""
        return

    @staticmethod
    def _sort_nodes_by_position(nodes: Iterable) -> tuple:
        sorted_nodes = sorted(nodes, key=lambda node: node.pos()[0])
        return sorted_nodes[0], sorted_nodes[1]

    @staticmethod
    def _first_output_port(node) -> Optional[Port]:
        outputs = node.output_ports()
        return outputs[0] if outputs else None

    @staticmethod
    def _first_input_port(node) -> Optional[Port]:
        inputs = node.input_ports()
        return inputs[0] if inputs else None

    def _show_info_dialog(self, message: str) -> None:
        QMessageBox.information(self, "操作案内", message)

    def _show_error_dialog(self, message: str) -> None:
        QMessageBox.critical(self, "エラー", message)

    def _search_nodes(
        self, keyword: Optional[str] = None, *, show_dialog: bool = True
    ):
        if keyword is None:
            keyword = (
                self._content_browser.current_search_text()
                if self._content_browser is not None
                else ""
            )
        keyword = keyword.strip()
        if not keyword:
            if show_dialog:
                self._show_info_dialog("検索キーワードを入力してください。")
            return None

        keyword_lower = keyword.lower()
        matched = [
            node
            for node in self._collect_all_nodes()
            if hasattr(node, "name") and keyword_lower in node.name().lower()
        ]
        if not matched:
            if show_dialog:
                self._show_info_dialog(f"「{keyword}」に一致するノードが見つかりません。")
            return None

        target = matched[0]
        self._select_single_node(target)
        return target

    def _collect_all_nodes(self) -> List:
        nodes: List = []
        all_nodes = getattr(self._graph, "all_nodes", None)
        if callable(all_nodes):
            result = all_nodes()
            if result is not None:
                nodes = list(result)
        if not nodes:
            nodes_attr = getattr(self._graph, "nodes", None)
            if callable(nodes_attr):
                result = nodes_attr()
                if result is not None:
                    nodes = list(result)
        if not nodes:
            nodes = list(self._known_nodes)
        return nodes

    def _on_selection_changed(self, *_args, **_kwargs) -> None:
        self._update_selected_node_info()

    def _update_selected_node_info(self) -> None:
        nodes = self._graph.selected_nodes()
        node = nodes[0] if nodes else None
        self._current_node = node

        if node is None:
            if self._detail_name_label:
                self._detail_name_label.setText("-")
            if self._detail_type_label:
                self._detail_type_label.setText("-")
            if self._detail_position_label:
                self._detail_position_label.setText("-")
            if self._rename_input is not None:
                self._rename_input.setText("")
                self._rename_input.setEnabled(False)
            if self._rename_button is not None:
                self._rename_button.setEnabled(False)
            return

        name = node.name() if hasattr(node, "name") else str(node)
        node_type = getattr(node, "type_", None)
        if callable(node_type):
            node_type = node_type()
        if not node_type:
            node_type = node.__class__.__name__
        position = node.pos() if hasattr(node, "pos") else (0, 0)
        pos_text = (
            f"({int(position[0])}, {int(position[1])})"
            if isinstance(position, (list, tuple)) and len(position) >= 2
            else "-"
        )

        if self._detail_name_label:
            self._detail_name_label.setText(name)
        if self._detail_type_label:
            self._detail_type_label.setText(str(node_type))
        if self._detail_position_label:
            self._detail_position_label.setText(pos_text)
        if self._rename_input is not None:
            self._rename_input.blockSignals(True)
            self._rename_input.setText(name)
            self._rename_input.setEnabled(True)
            self._rename_input.blockSignals(False)
        if self._rename_button is not None:
            self._rename_button.setEnabled(True)

    def _apply_node_rename(self) -> None:
        if self._current_node is None or self._rename_input is None:
            self._show_info_dialog("名前を変更するノードを選択してください。")
            return

        new_name = self._rename_input.text().strip()
        if not new_name:
            self._show_info_dialog("新しい名前を入力してください。")
            return

        if hasattr(self._current_node, "set_name"):
            self._current_node.set_name(new_name)
        self._update_selected_node_info()
        self._set_modified(True)
        self._refresh_node_catalog()

    def _return_to_start(self) -> None:
        if not self._confirm_discard_changes("未保存の変更があります。スタート画面に戻りますか？"):
            return
        self.hide()
        self.return_to_start_requested.emit()

    # ------------------------------------------------------------------
    # プロジェクトの保存・読み込み
    # ------------------------------------------------------------------
    def _file_save(self) -> None:
        graph_path = self._graph_file_path()
        if graph_path is None:
            self._show_error_dialog("プロジェクトが選択されていません。")
            return
        if self._current_project_root is not None:
            ensure_project_structure(self._current_project_root)
        try:
            self._write_project_to_path(graph_path)
            self._set_modified(False)
            self._show_info_dialog("プロジェクトを保存しました。")
        except OSError as exc:
            self._show_error_dialog(f"保存に失敗しました: {exc}")

    def _file_import(self) -> None:
        if self._current_project_root is None:
            self._show_info_dialog("先にプロジェクトを開いてください。")
            return
        start_dir = str(self._current_project_root / "assets")
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "アセットをインポート",
            start_dir,
            "All Files (*)",
        )
        if not filename:
            return
        source_path = Path(filename)
        target_dir = self._current_project_root / "assets" / "source"
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            destination = target_dir / source_path.name
            if source_path != destination:
                shutil.copy2(source_path, destination)
        except OSError as exc:
            self._show_error_dialog(f"アセットのコピーに失敗しました: {exc}")
            return
        self._create_asset_node(source_path.stem)
        self._set_modified(True)
        self._show_info_dialog(f"アセット「{source_path.name}」を登録しました。")

    def _write_project_to_path(self, path: Path) -> None:
        state = self._export_project_state()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(state, handle, ensure_ascii=True, indent=2)

    def _graph_file_path(self) -> Optional[Path]:
        if self._current_project_root is None:
            return None
        return self._current_project_root / "config" / "node_graph.json"

    def _reset_graph(self) -> None:
        existing_nodes = self._collect_all_nodes()
        if existing_nodes:
            try:
                self._graph.delete_nodes(existing_nodes)
            except Exception:
                pass
        self._known_nodes.clear()
        self._node_spawn_offset = 0
        self._task_count = 0
        self._review_count = 0
        clear_selection = getattr(self._graph, "clear_selection", None)
        if callable(clear_selection):
            try:
                clear_selection()
            except Exception:
                pass
        self._on_selection_changed()
        self._refresh_node_catalog()

    def _load_project_graph(self) -> None:
        graph_path = self._graph_file_path()
        self._reset_graph()
        if graph_path is None or not graph_path.exists():
            self._set_modified(False)
            return
        try:
            self._load_project_from_path(graph_path)
            self._set_modified(False)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            self._show_error_dialog(f"プロジェクトの読み込みに失敗しました: {exc}")
            self._reset_graph()
            self._set_modified(False)

    def _load_project_from_path(self, path: Path) -> None:
        with path.open("r", encoding="utf-8") as handle:
            state = json.load(handle)
        self._apply_project_state(state)

    def _export_project_state(self) -> Dict:
        nodes = self._collect_all_nodes()
        node_entries = []
        node_id_map: Dict = {}
        for index, node in enumerate(nodes):
            node_id_map[node] = index
            node_entries.append(
                {
                    "id": index,
                    "name": self._safe_node_name(node),
                    "type": self._node_type_identifier(node),
                    "position": self._safe_node_position(node),
                }
            )

        connections = []
        seen_connections: Set[Tuple[int, str, int, str]] = set()
        for node in nodes:
            outputs = getattr(node, "output_ports", None)
            if not callable(outputs):
                continue
            for port in outputs() or []:
                connected_ports = getattr(port, "connected_ports", None)
                if not callable(connected_ports):
                    continue
                for connected in connected_ports() or []:
                    target_node = connected.node() if hasattr(connected, "node") else None
                    if target_node is None or target_node not in node_id_map:
                        continue
                    source_name = self._safe_port_name(port)
                    target_name = self._safe_port_name(connected)
                    key = (
                        node_id_map[node],
                        source_name,
                        node_id_map[target_node],
                        target_name,
                    )
                    if key in seen_connections:
                        continue
                    seen_connections.add(key)
                    connections.append(
                        {
                            "source": node_id_map[node],
                            "source_port": source_name,
                            "target": node_id_map[target_node],
                            "target_port": target_name,
                        }
                    )

        return {"nodes": node_entries, "connections": connections}

    def _apply_project_state(self, state: Dict) -> None:
        nodes_info = state.get("nodes") if isinstance(state, dict) else None
        connections_info = state.get("connections") if isinstance(state, dict) else None
        if not isinstance(nodes_info, list) or not isinstance(connections_info, list):
            raise ValueError("プロジェクトファイルの形式が不正です。")

        existing_nodes = self._collect_all_nodes()
        if existing_nodes:
            self._graph.delete_nodes(existing_nodes)

        self._known_nodes.clear()
        self._node_spawn_offset = 0
        self._task_count = 0
        self._review_count = 0

        identifier_map: Dict[int, object] = {}
        for entry in nodes_info:
            if not isinstance(entry, dict):
                continue
            node_type = entry.get("type")
            node_name = entry.get("name")
            position = entry.get("position")
            if not isinstance(node_type, str) or not isinstance(node_name, str):
                continue
            node = self._graph.create_node(node_type, name=node_name)
            if isinstance(position, (list, tuple)) and len(position) >= 2:
                try:
                    node.set_pos(float(position[0]), float(position[1]))
                except Exception:
                    pass
            entry_id = entry.get("id")
            if isinstance(entry_id, int):
                identifier_map[entry_id] = node
            self._known_nodes.append(node)

        for connection in connections_info:
            if not isinstance(connection, dict):
                continue
            source_id = connection.get("source")
            target_id = connection.get("target")
            if not isinstance(source_id, int) or not isinstance(target_id, int):
                continue
            source_node = identifier_map.get(source_id)
            target_node = identifier_map.get(target_id)
            if source_node is None or target_node is None:
                continue
            source_port_name = connection.get("source_port")
            target_port_name = connection.get("target_port")
            source_port = self._find_port_by_name(source_node, source_port_name, output=True)
            target_port = self._find_port_by_name(target_node, target_port_name, output=False)
            if source_port is None or target_port is None:
                continue
            try:
                self._graph.connect_ports(source_port, target_port)
            except Exception:
                continue

        self._node_spawn_offset = len(self._known_nodes)
        self._task_count = sum(
            1 for node in self._known_nodes if self._node_type_identifier(node) == "sotugyo.demo.TaskNode"
        )
        self._review_count = sum(
            1 for node in self._known_nodes if self._node_type_identifier(node) == "sotugyo.demo.ReviewNode"
        )

        clear_selection = getattr(self._graph, "clear_selection", None)
        if callable(clear_selection):
            clear_selection()
        self._on_selection_changed()
        self._refresh_node_catalog()

    def _safe_node_name(self, node) -> str:
        if hasattr(node, "name"):
            try:
                return str(node.name())
            except Exception:
                pass
        return str(node)

    def _node_type_identifier(self, node) -> str:
        type_getter = getattr(node, "type_", None)
        if callable(type_getter):
            try:
                return str(type_getter())
            except Exception:
                pass
        identifier = getattr(node, "__identifier__", "")
        class_name = node.__class__.__name__
        return f"{identifier}.{class_name}" if identifier else class_name

    def _safe_node_position(self, node) -> List[float]:
        position = getattr(node, "pos", None)
        if callable(position):
            try:
                pos = position()
                if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                    return [float(pos[0]), float(pos[1])]
            except Exception:
                pass
        return [0.0, 0.0]

    @staticmethod
    def _safe_port_name(port) -> str:
        name_method = getattr(port, "name", None)
        if callable(name_method):
            try:
                return str(name_method())
            except Exception:
                pass
        return str(port)

    def _find_port_by_name(self, node, port_name: Optional[str], *, output: bool) -> Optional[Port]:
        accessor = "output_ports" if output else "input_ports"
        ports_getter = getattr(node, accessor, None)
        if not callable(ports_getter):
            return None
        for port in ports_getter() or []:
            if port_name is None:
                return port
            if self._safe_port_name(port) == port_name:
                return port
        return None

    def _set_modified(self, modified: bool) -> None:
        self._is_modified = modified
        self._refresh_window_title()

    def _refresh_window_title(self) -> None:
        title = self.WINDOW_TITLE
        if self._current_project_settings is not None:
            title += f" - {self._current_project_settings.project_name}"
        if self._current_user is not None:
            title += f" ({self._current_user.display_name})"
        self._base_window_title = title
        if self._is_modified:
            title = f"*{title}"
        self.setWindowTitle(title)

    def _confirm_project_change(self, project_name: str) -> bool:
        result = QMessageBox.question(
            self,
            "確認",
            f"プロジェクト「{project_name}」に切り替えますか？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return result == QMessageBox.StandardButton.Yes

    def _notify_start_window_refresh(self) -> None:
        parent = self.parent()
        if parent is None:
            return
        refresher = getattr(parent, "refresh_start_state", None)
        if callable(refresher):
            try:
                refresher()
            except Exception:
                pass

    def _confirm_discard_changes(self, message: Optional[str] = None) -> bool:
        if not self._is_modified:
            return True
        text = (
            message
            if message
            else "未保存の変更があります。操作を続行すると現在の編集内容が失われます。続行しますか？"
        )
        result = QMessageBox.warning(
            self,
            "確認",
            text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return result == QMessageBox.StandardButton.Yes

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._confirm_discard_changes("未保存の変更があります。ウィンドウを閉じますか？"):
            event.ignore()
            return
        super().closeEvent(event)
        self.return_to_start_requested.emit()
