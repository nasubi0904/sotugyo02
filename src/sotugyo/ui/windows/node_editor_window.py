"""ノード編集画面のウィンドウ実装。"""

from __future__ import annotations

import json
import logging
import shutil
import uuid
from pathlib import Path
from collections.abc import Iterable as IterableABC, Mapping
from datetime import date, datetime, timedelta
from typing import Dict, Iterable, List, Optional, Set, Tuple

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QKeySequence,
    QResizeEvent,
    QShortcut,
    QShowEvent,
)
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QSizePolicy,
    QWidget,
)
from NodeGraphQt import Port


LOGGER = logging.getLogger(__name__)

from ..components.content_browser import NodeCatalogEntry
from ..components.nodes import (
    MemoNode,
    ReviewNode,
    TaskNode,
    ToolEnvironmentNode,
)
from ..components.timeline import (
    TimelineGridOverlay,
    TimelineNodeGraph,
    TimelineSnapController,
)
from ...domain.projects.service import ProjectContext, ProjectService
from ...domain.projects.settings import ProjectSettings
from ...domain.projects.timeline import (
    DEFAULT_TIMELINE_UNIT,
    TimelineAxis,
    TimelineSnapSettings,
)
from ...domain.users.settings import UserAccount, UserSettingsManager
from ...domain.tooling.coordinator import (
    NodeCatalogRecord,
    NodeEditorCoordinator,
    ToolEnvironmentSnapshot,
)
from ...domain.tooling.models import RegisteredTool, ToolEnvironmentDefinition
from ..dialogs import (
    ProjectSettingsDialog,
    ToolEnvironmentManagerDialog,
    ToolRegistryDialog,
    UserSettingsDialog,
)
from ..style import apply_base_style
from .alignment_toolbar import TimelineAlignmentToolBar
from .content_browser_dock import NodeContentBrowserDock
from .inspector_panel import NodeInspectorDock


class NodeEditorWindow(QMainWindow):
    """NodeGraphQt を用いたノード編集画面。"""

    WINDOW_TITLE = "ノード編集テスト"
    return_to_start_requested = Signal()

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        project_service: Optional[ProjectService] = None,
        user_manager: Optional[UserSettingsManager] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.WINDOW_TITLE)
        self._base_window_title = self.windowTitle()
        self.resize(960, 600)
        self.setWindowState(self.windowState() | Qt.WindowFullScreen)

        self._graph = TimelineNodeGraph()
        self._graph.register_node(TaskNode)
        self._graph.register_node(ReviewNode)
        self._graph.register_node(MemoNode)
        self._graph.register_node(ToolEnvironmentNode)

        self._graph_widget = self._graph.widget
        self._graph_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._timeline_base_unit = DEFAULT_TIMELINE_UNIT
        self._timeline_column_units = 1
        self._timeline_origin_y = 0.0
        self._timeline_start_date = date.today()
        self._timeline_reference_date: Optional[date] = self._timeline_start_date
        self._timeline_overlay: Optional[TimelineGridOverlay] = None
        self._timeline_snap_controller: Optional[TimelineSnapController] = None

        self._node_spawn_offset = 0
        self._task_count = 0
        self._review_count = 0
        self._memo_count = 0
        self._current_node = None
        self._known_nodes: List = []
        self._node_metadata: Dict[object, Dict[str, str]] = {}
        self._is_modified = False
        self._current_project_root: Optional[Path] = None
        self._current_project_settings: Optional[ProjectSettings] = None
        self._current_user: Optional[UserAccount] = None
        self._current_user_password: Optional[str] = None
        self._coordinator = NodeEditorCoordinator(
            project_service=project_service,
            user_manager=user_manager,
        )
        self._project_service = self._coordinator.project_service
        self._user_manager = self._coordinator.user_manager
        self._tool_snapshot: Optional[ToolEnvironmentSnapshot] = None
        self._registered_tools: Dict[str, RegisteredTool] = {}
        self._tool_environments: Dict[str, ToolEnvironmentDefinition] = {}

        self._shortcuts: List[QShortcut] = []
        self._node_type_creators = {
            "sotugyo.demo.TaskNode": self._create_task_node,
            "sotugyo.demo.ReviewNode": self._create_review_node,
            MemoNode.node_type_identifier(): self._create_memo_node,
        }
        self._inspector_dock: Optional[NodeInspectorDock] = None
        self._content_dock: Optional[NodeContentBrowserDock] = None
        self._alignment_toolbar: Optional[TimelineAlignmentToolBar] = None

        snap_settings = TimelineSnapSettings(
            base_unit=self._timeline_base_unit,
            column_units=self._timeline_column_units,
            origin_x=self._timeline_origin_y,
            axis=TimelineAxis.VERTICAL,
        )
        self._timeline_snap_controller = TimelineSnapController(
            self._graph,
            settings=snap_settings,
            should_snap=self._should_snap_node,
            modified_callback=self._set_modified,
        )
        self._timeline_snap_controller.set_axis_orientation(TimelineAxis.VERTICAL)
        self._graph.set_timeline_move_handler(
            self._timeline_snap_controller.handle_nodes_moved
        )
        self._timeline_overlay = TimelineGridOverlay(
            self._graph_widget, axis=TimelineAxis.VERTICAL
        )
        self._update_timeline_overlay_settings()

        self._init_ui()
        self._create_menus()
        self._setup_graph_signals()
        self._setup_context_menu()
        self._setup_shortcuts()
        self._refresh_tool_configuration()
        self._initialize_content_browser()
        self._update_selected_node_info()
        self._refresh_node_catalog()
        self._set_modified(False)
        apply_base_style(self)

        property_signal = getattr(self._graph, "property_changed", None)
        if property_signal is not None and hasattr(property_signal, "connect"):
            property_signal.connect(self._on_graph_property_changed_timeline)

    def showEvent(self, event: QShowEvent) -> None:
        """ウィンドウ表示時に全画面状態を維持する。"""

        super().showEvent(event)
        if not self.isFullScreen():
            self.setWindowState(self.windowState() | Qt.WindowFullScreen)

    # ------------------------------------------------------------------
    # UI 初期化
    # ------------------------------------------------------------------
    def _init_ui(self) -> None:
        central = QWidget(self)
        central.setObjectName("graphCentralContainer")
        central_layout = QHBoxLayout(central)
        central_layout.setContentsMargins(16, 16, 16, 16)
        central_layout.setSpacing(16)
        central_layout.addWidget(self._graph_widget, 1)
        self.setCentralWidget(central)

        alignment_toolbar = TimelineAlignmentToolBar(
            self, initial_units=self._timeline_column_units
        )
        alignment_toolbar.align_inputs_requested.connect(self._align_input_nodes)
        alignment_toolbar.align_outputs_requested.connect(self._align_output_nodes)
        alignment_toolbar.timeline_width_changed.connect(
            self._on_timeline_width_units_changed
        )
        self.addToolBar(Qt.LeftToolBarArea, alignment_toolbar)
        self._alignment_toolbar = alignment_toolbar

        inspector_dock = NodeInspectorDock(
            self,
            memo_font_range=(MemoNode.MIN_FONT_SIZE, MemoNode.MAX_FONT_SIZE),
            memo_font_default=MemoNode.DEFAULT_FONT_SIZE,
        )
        inspector_dock.rename_requested.connect(self._handle_rename_requested)
        inspector_dock.memo_text_changed.connect(self._handle_memo_text_changed)
        inspector_dock.memo_font_changed.connect(self._handle_memo_font_size_changed)
        self.addDockWidget(Qt.RightDockWidgetArea, inspector_dock)
        self._inspector_dock = inspector_dock

        content_dock = NodeContentBrowserDock(self)
        content_dock.node_type_requested.connect(self._spawn_node_by_type)
        content_dock.search_submitted.connect(self._handle_content_browser_search)
        content_dock.back_requested.connect(self._return_to_start)
        self.addDockWidget(Qt.BottomDockWidgetArea, content_dock)
        self._content_dock = content_dock

        self.resizeDocks([content_dock], [220], Qt.Vertical)
        self.resizeDocks([inspector_dock], [320], Qt.Horizontal)

    def _create_menus(self) -> None:
        menubar = self.menuBar()

        file_menu = menubar.addMenu("File")

        save_action = QAction("上書き保存", self)
        save_action.triggered.connect(self._file_save)
        save_action.setShortcut(QKeySequence.Save)
        file_menu.addAction(save_action)

        export_selected_action = QAction("選択ノードを保存...", self)
        export_selected_action.triggered.connect(self._file_export_selected_nodes)
        file_menu.addAction(export_selected_action)

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

        tools_menu = menubar.addMenu("Tools")
        tool_registry_action = QAction("環境設定...", self)
        tool_registry_action.triggered.connect(self._open_tool_settings)
        tools_menu.addAction(tool_registry_action)
        environment_action = QAction("ツール環境の編集...", self)
        environment_action.triggered.connect(self._open_tool_environment_manager)
        tools_menu.addAction(environment_action)

        view_menu = menubar.addMenu("View")
        if self._inspector_dock is not None:
            view_menu.addAction(self._inspector_dock.toggleViewAction())
        if self._content_dock is not None:
            view_menu.addAction(self._content_dock.toggleViewAction())
        if self._alignment_toolbar is not None:
            view_menu.addAction(self._alignment_toolbar.toggleViewAction())

    def _open_project_settings(self) -> None:
        if self._current_project_root is None:
            self._show_info_dialog("プロジェクトが選択されていません。")
            return
        if self._current_project_settings is None:
            self._current_project_settings = self._project_service.load_settings(
                self._current_project_root
            )
        dialog = ProjectSettingsDialog(self._current_project_settings, self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        updated = dialog.settings()
        root_changed = updated.project_root != self._current_project_root
        name_changed = (
            self._current_project_settings.project_name != updated.project_name
            if self._current_project_settings
            else True
        )
        self._current_project_settings = updated
        try:
            self._project_service.save_settings(updated)
        except OSError as exc:
            self._show_error_dialog(f"設定の保存に失敗しました: {exc}")
            return
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

    def _open_tool_settings(self) -> None:
        dialog = ToolRegistryDialog(self._coordinator.tool_service, self)
        dialog.exec()
        if dialog.refresh_requested():
            self._refresh_tool_configuration()

    def _open_tool_environment_manager(self) -> None:
        dialog = ToolEnvironmentManagerDialog(self._coordinator.tool_service, self)
        dialog.exec()
        if dialog.refresh_requested():
            self._refresh_tool_configuration()

    def _setup_graph_signals(self) -> None:
        selection_signal = getattr(self._graph, "selection_changed", None)
        if selection_signal is not None and hasattr(selection_signal, "connect"):
            selection_signal.connect(self._on_selection_changed)
        else:
            selection_signal = getattr(self._graph, "node_selection_changed", None)
            if selection_signal is not None and hasattr(selection_signal, "connect"):
                selection_signal.connect(self._on_selection_changed)

        connection_signals = [
            getattr(self._graph, "port_connected", None),
            getattr(self._graph, "port_disconnected", None),
            getattr(self._graph, "pipes_deleted", None),
        ]
        for signal in connection_signals:
            if signal is not None and hasattr(signal, "connect"):
                signal.connect(self._on_port_connection_changed)

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
        if self._content_dock is None:
            return
        self._refresh_content_browser_entries()

    def _refresh_tool_configuration(self) -> None:
        snapshot = self._coordinator.load_tool_snapshot()
        self._tool_snapshot = snapshot
        self._registered_tools = dict(snapshot.tools)
        self._tool_environments = dict(snapshot.environments)
        self._refresh_content_browser_entries()

    def _refresh_content_browser_entries(self) -> None:
        if self._content_dock is None:
            return
        records = self._build_available_node_records()
        if self._tool_snapshot is not None:
            records = self._coordinator.extend_catalog(records, self._tool_snapshot)
        entries = [
            NodeCatalogEntry(
                node_type=record.node_type,
                title=record.title,
                subtitle=record.subtitle,
                genre=record.genre,
                keywords=record.keywords,
                icon_path=record.icon_path,
            )
            for record in records
        ]
        self._content_dock.set_catalog_entries(entries)

    # ------------------------------------------------------------------
    # プロジェクトコンテキスト管理
    # ------------------------------------------------------------------
    def prepare_context(
        self,
        context: ProjectContext,
        user: UserAccount,
        password: str,
    ) -> bool:
        project_root = Path(context.root)
        settings = context.settings
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
        self._current_project_settings = settings
        self._current_user = user
        self._current_user_password = password

        self._project_service.register_project(context.record, set_last=True)
        self._project_service.ensure_structure(project_root)

        self._refresh_window_title()
        self._load_project_graph()

        report = self._project_service.validate_structure(project_root)
        if not report.is_valid:
            QMessageBox.warning(
                self,
                "警告",
                "既定のプロジェクト構成に不足があります。\n" + report.summary(),
            )

        self._notify_start_window_refresh()
        return True

    def _build_available_node_records(self) -> List[NodeCatalogRecord]:
        records: List[NodeCatalogRecord] = [
            NodeCatalogRecord(
                node_type="sotugyo.demo.TaskNode",
                title=TaskNode.NODE_NAME,
                subtitle="工程を構成するタスクノード",
                genre="ワークフロー",
                keywords=("task", "workflow", "工程"),
            ),
            NodeCatalogRecord(
                node_type="sotugyo.demo.ReviewNode",
                title=ReviewNode.NODE_NAME,
                subtitle="成果物を検証するレビューノード",
                genre="ワークフロー",
                keywords=("review", "チェック", "検証"),
            ),
            NodeCatalogRecord(
                node_type=MemoNode.node_type_identifier(),
                title=MemoNode.NODE_NAME,
                subtitle="ノードエディタ上で自由に記述できるメモ",
                genre="メモ",
                keywords=("note", "メモ", "記録"),
            ),
        ]
        return records

    def _open_graph_context_menu(self, position: QPoint) -> None:
        menu = QMenu(self)

        add_task_action = menu.addAction("タスクノードを追加")
        add_task_action.triggered.connect(self._create_task_node)

        add_review_action = menu.addAction("レビューノードを追加")
        add_review_action.triggered.connect(self._create_review_node)

        add_memo_action = menu.addAction("メモノードを追加")
        add_memo_action.triggered.connect(self._create_memo_node)

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
        if self._content_dock is not None:
            self._content_dock.focus_search()

    def _handle_content_browser_search(self, keyword: str) -> None:
        if self._content_dock is None:
            return
        keyword = keyword.strip()
        if not keyword:
            self._show_info_dialog("検索キーワードを入力してください。")
            return

        if self._search_nodes(keyword, show_dialog=False) is not None:
            return

        available_type = self._content_dock.first_visible_available_type()
        if available_type is not None:
            self._spawn_node_by_type(available_type)
            return

        self._show_info_dialog(f"「{keyword}」に一致するノードが見つかりません。")

    def _spawn_node_by_type(self, node_type: str) -> None:
        if node_type.startswith("tool-environment:"):
            environment_id = node_type.split(":", 1)[1]
            self._create_tool_environment_node(environment_id)
            return
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
    def _ensure_node_metadata(
        self,
        node,
        *,
        uuid_value: Optional[str] = None,
        assigned_at: Optional[str] = None,
    ) -> Tuple[str, str, bool]:
        metadata = self._node_metadata.get(node)
        existing_uuid = metadata.get("uuid") if metadata else None
        existing_assigned_at = metadata.get("uuid_assigned_at") if metadata else None

        provided_uuid = uuid_value.strip() if isinstance(uuid_value, str) else None
        uuid_was_missing = False
        if provided_uuid:
            normalized_uuid = provided_uuid
        elif existing_uuid:
            normalized_uuid = existing_uuid
        else:
            normalized_uuid = str(uuid.uuid4())
            uuid_was_missing = True

        provided_assigned_at = assigned_at.strip() if isinstance(assigned_at, str) else None
        assigned_at_was_missing = False
        if provided_assigned_at:
            normalized_assigned_at = provided_assigned_at
        elif existing_assigned_at:
            normalized_assigned_at = existing_assigned_at
        else:
            normalized_assigned_at = datetime.now().strftime("%Y-%m-%d")
            assigned_at_was_missing = True

        previous_uuid = metadata.get("uuid") if metadata else None
        previous_assigned_at = metadata.get("uuid_assigned_at") if metadata else None
        if (
            metadata is None
            or previous_uuid != normalized_uuid
            or previous_assigned_at != normalized_assigned_at
        ):
            self._node_metadata[node] = {
                "uuid": normalized_uuid,
                "uuid_assigned_at": normalized_assigned_at,
            }

        metadata_changed = uuid_was_missing or assigned_at_was_missing
        if not metadata_changed and metadata is not None:
            metadata_changed = (
                previous_uuid != normalized_uuid
                or previous_assigned_at != normalized_assigned_at
            )

        if normalized_assigned_at:
            self._consider_timeline_date(normalized_assigned_at)

        return normalized_uuid, normalized_assigned_at, metadata_changed

    def _remove_node_metadata(self, nodes: Iterable) -> None:
        for node in nodes:
            self._node_metadata.pop(node, None)

    def _on_graph_property_changed_timeline(self, node, prop_name: str, value: object) -> None:
        if self._timeline_snap_controller is None:
            return
        if self._timeline_snap_controller.handle_property_changed(node, prop_name, value):
            self._update_timeline_overlay_settings()

    def _on_timeline_width_units_changed(self, value: int) -> None:
        if self._timeline_snap_controller is None:
            return
        if not self._timeline_snap_controller.set_column_units(value):
            return
        self._timeline_column_units = max(1, int(value))
        if self._alignment_toolbar is not None:
            self._alignment_toolbar.set_timeline_units(self._timeline_column_units)
        self._update_timeline_overlay_settings()
        self._timeline_snap_controller.snap_nodes(self._collect_all_nodes())

    def _update_timeline_overlay_settings(self) -> None:
        if self._timeline_overlay is None or self._timeline_snap_controller is None:
            return
        self._timeline_snap_controller.set_origin_y(self._timeline_origin_y)
        snap_settings = self._timeline_snap_controller.settings
        self._timeline_overlay.set_axis_orientation(TimelineAxis.VERTICAL)
        self._timeline_overlay.set_column_width(self._timeline_snap_controller.column_width)
        self._timeline_overlay.set_column_units(snap_settings.normalized_column_units)
        self._timeline_overlay.set_origin_x(snap_settings.origin_x)
        self._timeline_overlay.set_start_date(self._timeline_start_date)

    def _consider_timeline_date(self, assigned_at: Optional[str]) -> None:
        candidate = self._parse_assigned_date(assigned_at)
        if candidate is None:
            return
        if self._timeline_reference_date is None or candidate < self._timeline_reference_date:
            self._timeline_reference_date = candidate
            self._timeline_start_date = candidate
            self._update_timeline_overlay_settings()

    def _rebuild_timeline_reference(self) -> None:
        earliest: Optional[date] = None
        for metadata in self._node_metadata.values():
            assigned = metadata.get("uuid_assigned_at")
            candidate = self._parse_assigned_date(assigned)
            if candidate is None:
                continue
            if earliest is None or candidate < earliest:
                earliest = candidate
        if earliest is None:
            earliest = date.today()
        self._timeline_reference_date = earliest
        self._timeline_start_date = earliest
        self._update_timeline_overlay_settings()

    @staticmethod
    def _parse_assigned_date(value: Optional[str]) -> Optional[date]:
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return None

    def _apply_timeline_constraints_to_nodes(self, nodes: Iterable) -> None:
        if self._timeline_snap_controller is None:
            return
        if self._timeline_snap_controller.snap_nodes(nodes):
            self._update_timeline_overlay_settings()

    def _create_task_node(self) -> None:
        self._task_count += 1
        self._create_node("sotugyo.demo.TaskNode", f"タスク {self._task_count}")

    def _create_review_node(self) -> None:
        self._review_count += 1
        self._create_node("sotugyo.demo.ReviewNode", f"レビュー {self._review_count}")

    def _create_memo_node(self) -> None:
        self._memo_count += 1
        self._create_node(MemoNode.node_type_identifier(), f"メモ {self._memo_count}")

    def _create_asset_node(self, asset_name: str) -> None:
        title = asset_name.strip() or "アセット"
        self._create_node("sotugyo.demo.TaskNode", f"Asset: {title}")

    def _create_tool_environment_node(self, environment_id: str) -> None:
        definition = self._tool_environments.get(environment_id)
        if definition is None:
            self._show_warning_dialog("選択された環境定義が見つかりませんでした。")
            return
        tool = self._registered_tools.get(definition.tool_id)
        if tool is None:
            self._show_warning_dialog("環境が参照するツールが登録されていません。")
            return
        node = self._create_node(
            ToolEnvironmentNode.node_type_identifier(), definition.name
        )
        if isinstance(node, ToolEnvironmentNode):
            node.configure_environment(
                environment_id=definition.environment_id,
                environment_name=definition.name,
                tool_id=tool.tool_id,
                tool_name=tool.display_name,
                version_label=definition.version_label,
                executable_path=str(tool.executable_path),
            )

    def _create_node(self, node_type: str, display_name: str):
        node = self._graph.create_node(node_type, name=display_name)
        pos_x = (self._node_spawn_offset % 4) * 220
        pos_y = (self._node_spawn_offset // 4) * 180
        node.set_pos(pos_x, pos_y)
        self._node_spawn_offset += 1
        self._known_nodes.append(node)
        self._ensure_node_metadata(node)
        self._apply_timeline_constraints_to_nodes([node])
        self._set_modified(True)

        clear_selection = getattr(self._graph, "clear_selection", None)
        if callable(clear_selection):
            clear_selection()
        if hasattr(node, "set_selected"):
            node.set_selected(True)
        self._on_selection_changed()
        self._refresh_node_catalog()
        return node

    def _delete_selected_nodes(self) -> None:
        nodes = self._graph.selected_nodes()
        if not nodes:
            self._show_info_dialog("削除するノードを選択してください。")
            return
        self._graph.delete_nodes(nodes)
        self._known_nodes = [node for node in self._known_nodes if node not in nodes]
        self._remove_node_metadata(nodes)
        self._rebuild_timeline_reference()
        self._on_selection_changed()
        self._set_modified(True)
        self._refresh_node_catalog()

    # ------------------------------------------------------------------
    # 接続処理
    # ------------------------------------------------------------------
    def _connect_ports_compat(self, source_port: Port, target_port: Port) -> None:
        """NodeGraphQt のバージョン差異を吸収してポートを接続する。"""

        connect_ports = getattr(self._graph, "connect_ports", None)
        try:
            if callable(connect_ports):
                connect_ports(source_port, target_port)
            else:
                fallback = getattr(source_port, "connect_to", None)
                if not callable(fallback):  # pragma: no cover - 保険的分岐
                    raise AttributeError("connect_ports API が利用できません")
                fallback(target_port)
        except Exception as exc:  # pragma: no cover - Qt 依存の例外
            LOGGER.warning(
                "ポート接続に失敗しました（source=%s, target=%s）: %s",
                self._describe_port(source_port),
                self._describe_port(target_port),
                exc,
                exc_info=True,
            )
            raise

    def _disconnect_ports_compat(self, source_port: Port, target_port: Port) -> None:
        """NodeGraphQt のバージョン差異を吸収してポートを切断する。"""

        disconnect_ports = getattr(self._graph, "disconnect_ports", None)
        try:
            if callable(disconnect_ports):
                disconnect_ports(source_port, target_port)
            else:
                fallback = getattr(source_port, "disconnect_from", None)
                if not callable(fallback):  # pragma: no cover - 保険的分岐
                    raise AttributeError("disconnect_ports API が利用できません")
                fallback(target_port)
        except Exception as exc:  # pragma: no cover - Qt 依存の例外
            LOGGER.warning(
                "ポート切断に失敗しました（source=%s, target=%s）: %s",
                self._describe_port(source_port),
                self._describe_port(target_port),
                exc,
                exc_info=True,
            )
            raise

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
        self._connect_ports_compat(source_port, target_port)
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
                self._disconnect_ports_compat(source_port, connected_port)
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

    def _describe_port(self, port: Port) -> str:
        node_label = "不明ノード"
        node_getter = getattr(port, "node", None)
        node_obj = None
        if callable(node_getter):
            try:
                node_obj = node_getter()
            except Exception:  # pragma: no cover - Qt 依存の例外
                node_obj = None
        if node_obj is not None:
            node_label = self._safe_node_name(node_obj)
        port_label = None
        name_getter = getattr(port, "name", None)
        if callable(name_getter):
            try:
                port_label = str(name_getter())
            except Exception:  # pragma: no cover - Qt 依存の例外
                port_label = None
        if port_label:
            return f"{node_label}:{port_label}"
        return f"{node_label}:{repr(port)}"

    def _show_info_dialog(self, message: str) -> None:
        QMessageBox.information(self, "操作案内", message)

    def _show_warning_dialog(self, message: str) -> None:
        QMessageBox.warning(self, "警告", message)

    def _show_error_dialog(self, message: str) -> None:
        QMessageBox.critical(self, "エラー", message)

    def _search_nodes(
        self, keyword: Optional[str] = None, *, show_dialog: bool = True
    ):
        if keyword is None:
            keyword = (
                self._content_dock.current_search_text()
                if self._content_dock is not None
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

    def _on_port_connection_changed(self, *_ports, **_kwargs) -> None:
        self._set_modified(True)
        self._update_selected_node_info()

    def _update_selected_node_info(self) -> None:
        nodes = self._graph.selected_nodes()
        node = nodes[0] if nodes else None
        self._current_node = node

        inspector = self._inspector_dock
        if node is None:
            if inspector is not None:
                inspector.clear_node_details()
                inspector.disable_rename()
                inspector.clear_memo()
            self._update_alignment_controls(None)
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

        node_uuid, _, metadata_changed = self._ensure_node_metadata(node)
        if metadata_changed:
            self._set_modified(True)

        if inspector is not None:
            inspector.update_node_details(
                name=name,
                node_type=node_type,
                node_uuid=node_uuid,
                position_text=pos_text,
            )
            inspector.enable_rename(name)
        self._update_memo_controls(node)
        self._update_alignment_controls(node)

    def _handle_rename_requested(self, new_name: str) -> None:
        if self._current_node is None:
            self._show_info_dialog("名前を変更するノードを選択してください。")
            if self._inspector_dock is not None:
                self._inspector_dock.disable_rename()
            return

        normalized_name = new_name.strip()
        if not normalized_name:
            self._show_info_dialog("新しい名前を入力してください。")
            return

        if hasattr(self._current_node, "set_name"):
            self._current_node.set_name(normalized_name)
        self._update_selected_node_info()
        self._set_modified(True)
        self._refresh_node_catalog()

    def _handle_memo_text_changed(self, text: str) -> None:
        if self._current_node is None or not self._is_memo_node(self._current_node):
            return
        try:
            current = self._current_node.get_property("memo_text")
        except Exception:  # pragma: no cover - NodeGraph 依存の例外
            current = None
        if current == text:
            return
        try:
            self._current_node.set_property("memo_text", text)
        except Exception:  # pragma: no cover - NodeGraph 依存の例外
            LOGGER.debug("メモテキストの更新に失敗しました", exc_info=True)
            return
        self._set_modified(True)

    def _handle_memo_font_size_changed(self, value: int) -> None:
        if self._current_node is None or not self._is_memo_node(self._current_node):
            return
        try:
            current = self._current_node.get_property("memo_font_size")
        except Exception:  # pragma: no cover - NodeGraph 依存の例外
            current = None
        if current == value:
            return
        try:
            self._current_node.set_property("memo_font_size", value)
        except Exception:  # pragma: no cover - NodeGraph 依存の例外
            LOGGER.debug("メモフォントサイズの更新に失敗しました", exc_info=True)
            return
        self._set_modified(True)

    def _update_alignment_controls(self, node) -> None:
        input_nodes = self._collect_connected_nodes(node, direction="inputs")
        output_nodes = self._collect_connected_nodes(node, direction="outputs")
        if self._alignment_toolbar is not None:
            self._alignment_toolbar.set_alignment_enabled(
                inputs=bool(input_nodes), outputs=bool(output_nodes)
            )

    def _align_input_nodes(self) -> None:
        if self._current_node is None:
            self._show_info_dialog("整列するノードを選択してください。")
            return
        self._align_connected_nodes(self._current_node, direction="inputs")

    def _align_output_nodes(self) -> None:
        if self._current_node is None:
            self._show_info_dialog("整列するノードを選択してください。")
            return
        self._align_connected_nodes(self._current_node, direction="outputs")

    def _collect_connected_nodes(self, node, *, direction: str) -> List:
        if node is None:
            return []
        ports_func_name = "input_ports" if direction == "inputs" else "output_ports"
        ports_getter = getattr(node, ports_func_name, None)
        if not callable(ports_getter):
            return []
        connected_nodes: List = []
        try:
            ports = list(ports_getter())
        except Exception:  # pragma: no cover - NodeGraph 依存の例外
            return []
        for port in ports:
            connected_ports = getattr(port, "connected_ports", None)
            if not callable(connected_ports):
                continue
            try:
                links = list(connected_ports())
            except Exception:  # pragma: no cover - NodeGraph 依存の例外
                continue
            for link in links:
                node_getter = getattr(link, "node", None)
                if not callable(node_getter):
                    continue
                try:
                    other = node_getter()
                except Exception:  # pragma: no cover - NodeGraph 依存の例外
                    continue
                if other is None or other is node:
                    continue
                if other not in connected_nodes:
                    connected_nodes.append(other)
        return connected_nodes

    def _align_connected_nodes(self, node, *, direction: str) -> None:
        connected_nodes = self._collect_connected_nodes(node, direction=direction)
        if not connected_nodes:
            self._show_info_dialog("接続されているノードが見つかりません。")
            return

        try:
            base_x, base_y = node.pos()
        except Exception:  # pragma: no cover - NodeGraph 依存の例外
            self._show_warning_dialog("ノード位置を取得できませんでした。")
            return

        spacing = self._estimate_node_spacing(connected_nodes)
        horizontal_offset = self._estimate_horizontal_offset(node, connected_nodes)

        sorted_nodes = sorted(connected_nodes, key=lambda n: self._safe_node_pos(n)[1])
        count = len(sorted_nodes)
        start_y = base_y - spacing * (count - 1) / 2

        updated = False
        for index, target in enumerate(sorted_nodes):
            target_x = (
                base_x - horizontal_offset
                if direction == "inputs"
                else base_x + horizontal_offset
            )
            target_y = start_y + spacing * index
            if self._move_node_if_needed(target, target_x, target_y):
                updated = True

        if updated:
            self._apply_timeline_constraints_to_nodes(sorted_nodes)
            self._set_modified(True)

    def _estimate_node_spacing(self, nodes: List) -> float:
        default_spacing = 160.0
        heights: List[float] = []
        for node in nodes:
            height = self._read_numeric_property(node, "height")
            if height is not None:
                heights.append(float(height))
        if not heights:
            return default_spacing
        average_height = sum(heights) / len(heights)
        return max(default_spacing, average_height + 40.0)

    def _estimate_horizontal_offset(self, base_node, connected_nodes: List) -> float:
        base_width = self._read_numeric_property(base_node, "width") or 240
        connected_widths = [
            self._read_numeric_property(node, "width") or 240 for node in connected_nodes
        ]
        max_connected = max(connected_widths) if connected_widths else 240
        return base_width / 2 + max_connected / 2 + 120

    def _read_numeric_property(self, node, name: str) -> Optional[float]:
        getter = getattr(node, "get_property", None)
        if not callable(getter):
            return None
        try:
            value = getter(name)
        except Exception:  # pragma: no cover - NodeGraph 依存の例外
            return None
        try:
            return float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None

    def _safe_node_pos(self, node) -> Tuple[float, float]:
        try:
            pos = node.pos()
            if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                return float(pos[0]), float(pos[1])
        except Exception:  # pragma: no cover - NodeGraph 依存の例外
            pass
        return 0.0, 0.0

    def _move_node_if_needed(self, node, pos_x: float, pos_y: float) -> bool:
        current_x, current_y = self._safe_node_pos(node)
        if abs(current_x - pos_x) < 1e-3 and abs(current_y - pos_y) < 1e-3:
            return False
        try:
            node.set_pos(pos_x, pos_y)
        except Exception:  # pragma: no cover - NodeGraph 依存の例外
            LOGGER.debug("ノード位置の更新に失敗しました", exc_info=True)
            return False
        return True

    def _update_memo_controls(self, node) -> None:
        inspector = self._inspector_dock
        if inspector is None:
            return
        if not self._is_memo_node(node):
            inspector.clear_memo()
            return

        try:
            memo_text = node.get_property("memo_text")
        except Exception:  # pragma: no cover - NodeGraph 依存の例外
            memo_text = ""
        try:
            font_size = node.get_property("memo_font_size")
        except Exception:  # pragma: no cover - NodeGraph 依存の例外
            font_size = MemoNode.DEFAULT_FONT_SIZE
        try:
            normalized_size = int(font_size)
        except (TypeError, ValueError):
            normalized_size = MemoNode.DEFAULT_FONT_SIZE
        inspector.show_memo(str(memo_text or ""), normalized_size)

    def _is_memo_node(self, node) -> bool:
        if node is None:
            return False
        return self._node_type_identifier(node) == MemoNode.node_type_identifier()

    def _should_snap_node(self, node) -> bool:
        return node is not None and not self._is_memo_node(node)

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
            self._project_service.ensure_structure(self._current_project_root)
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
            self._remove_node_metadata(existing_nodes)
        self._known_nodes.clear()
        self._node_metadata.clear()
        self._node_spawn_offset = 0
        self._task_count = 0
        self._review_count = 0
        self._memo_count = 0
        self._rebuild_timeline_reference()
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
            metadata_changed = self._load_project_from_path(graph_path)
            self._set_modified(bool(metadata_changed))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            self._show_error_dialog(f"プロジェクトの読み込みに失敗しました: {exc}")
            self._reset_graph()
            self._set_modified(False)

    def _load_project_from_path(self, path: Path) -> bool:
        with path.open("r", encoding="utf-8") as handle:
            state = json.load(handle)
        return self._apply_project_state(state)

    def _export_project_state(self) -> Dict:
        nodes = self._collect_all_nodes()
        return self._build_state_from_nodes(nodes)

    def _build_state_from_nodes(self, nodes: Iterable) -> Dict:
        node_list = list(nodes)
        node_entries = []
        node_id_map: Dict = {}
        node_uuid_map: Dict[object, str] = {}
        for index, node in enumerate(node_list):
            node_id_map[node] = index
            node_uuid, assigned_at, _ = self._ensure_node_metadata(node)
            node_uuid_map[node] = node_uuid
            entry = {
                "id": index,
                "name": self._safe_node_name(node),
                "type": self._node_type_identifier(node),
                "position": self._safe_node_position(node),
                "uuid": node_uuid,
            }
            if assigned_at:
                entry["uuid_assigned_at"] = assigned_at
            custom_props = self._node_custom_properties(node)
            if custom_props:
                entry["custom_properties"] = custom_props
            node_entries.append(entry)

        connections = []
        seen_connections: Set[
            Tuple[str, Optional[int], str, str, Optional[int], str]
        ] = set()
        for node in node_list:
            for port in self._collect_ports(node, output=True):
                for connected in self._connected_ports(port):
                    if not isinstance(connected, Port):
                        continue
                    target_node = connected.node() if hasattr(connected, "node") else None
                    if target_node is None or target_node not in node_id_map:
                        continue
                    source_uuid = node_uuid_map.get(node)
                    target_uuid = node_uuid_map.get(target_node)
                    if source_uuid is None or target_uuid is None:
                        continue
                    source_id = node_id_map[node]
                    target_id = node_id_map[target_node]
                    source_name = self._safe_port_name(port)
                    target_name = self._safe_port_name(connected)
                    source_index = self._port_index_in_node(node, port, output=True)
                    target_index = self._port_index_in_node(target_node, connected, output=False)
                    key = (
                        source_uuid,
                        source_index,
                        source_name,
                        target_uuid,
                        target_index,
                        target_name,
                    )
                    if key in seen_connections:
                        continue
                    seen_connections.add(key)
                    entry = {
                        "source": source_id,
                        "source_uuid": source_uuid,
                        "source_port": source_name,
                        "target": target_id,
                        "target_uuid": target_uuid,
                        "target_port": target_name,
                    }
                    if source_index is not None:
                        entry["source_port_index"] = source_index
                    if target_index is not None:
                        entry["target_port_index"] = target_index
                    connections.append(entry)

        return {"nodes": node_entries, "connections": connections}

    def _file_export_selected_nodes(self) -> None:
        selected_nodes = getattr(self._graph, "selected_nodes", None)
        if not callable(selected_nodes):
            self._show_error_dialog("選択中のノードを取得できませんでした。")
            return
        nodes = list(selected_nodes() or [])
        if not nodes:
            self._show_info_dialog("保存するノードを選択してください。")
            return

        start_dir = (
            str(self._current_project_root)
            if self._current_project_root is not None
            else str(Path.home())
        )
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "選択ノードを保存",
            start_dir,
            "JSON Files (*.json);;All Files (*)",
        )
        if not filename:
            return

        path = Path(filename)
        try:
            state = self._build_state_from_nodes(nodes)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8") as handle:
                json.dump(state, handle, ensure_ascii=True, indent=2)
        except (OSError, TypeError) as exc:
            self._show_error_dialog(f"保存に失敗しました: {exc}")
            return

        self._show_info_dialog("選択したノードを保存しました。")

    def _apply_project_state(self, state: Dict) -> bool:
        nodes_info = state.get("nodes") if isinstance(state, dict) else None
        connections_info = state.get("connections") if isinstance(state, dict) else None
        if not isinstance(nodes_info, list) or not isinstance(connections_info, list):
            raise ValueError("プロジェクトファイルの形式が不正です。")

        existing_nodes = self._collect_all_nodes()
        if existing_nodes:
            self._graph.delete_nodes(existing_nodes)
            self._remove_node_metadata(existing_nodes)

        self._known_nodes.clear()
        self._node_metadata.clear()
        self._node_spawn_offset = 0
        self._task_count = 0
        self._review_count = 0

        identifier_map: Dict[int, object] = {}
        uuid_map: Dict[str, object] = {}
        metadata_changed = False
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
            node_uuid = entry.get("uuid")
            assigned_at = entry.get("uuid_assigned_at")
            normalized_uuid, _, changed = self._ensure_node_metadata(
                node,
                uuid_value=node_uuid if isinstance(node_uuid, str) else None,
                assigned_at=assigned_at if isinstance(assigned_at, str) else None,
            )
            uuid_map[normalized_uuid] = node
            if changed:
                metadata_changed = True
            custom_props = entry.get("custom_properties")
            if isinstance(custom_props, dict):
                for key, value in custom_props.items():
                    try:
                        node.set_property(key, value, push_undo=False)
                    except Exception:  # pragma: no cover - NodeGraph 依存の例外
                        LOGGER.debug("プロパティ %s の適用に失敗しました", key, exc_info=True)

        failed_operations: List[str] = []

        for index, connection in enumerate(connections_info):
            if not isinstance(connection, dict):
                failed_operations.append(
                    f"接続エントリ #{index + 1} の形式が不正なため処理できませんでした。"
                )
                continue
            source_node = None
            target_node = None
            source_uuid = connection.get("source_uuid")
            target_uuid = connection.get("target_uuid")
            if isinstance(source_uuid, str):
                source_node = uuid_map.get(source_uuid)
            if isinstance(target_uuid, str):
                target_node = uuid_map.get(target_uuid)
            if source_node is None:
                source_id = connection.get("source")
                if isinstance(source_id, int):
                    source_node = identifier_map.get(source_id)
            if target_node is None:
                target_id = connection.get("target")
                if isinstance(target_id, int):
                    target_node = identifier_map.get(target_id)
            raw_source_id = connection.get("source")
            raw_target_id = connection.get("target")
            if isinstance(source_uuid, str) and source_uuid:
                source_label = source_uuid
            elif isinstance(raw_source_id, int):
                source_label = str(raw_source_id)
            else:
                source_label = "不明"
            if isinstance(target_uuid, str) and target_uuid:
                target_label = target_uuid
            elif isinstance(raw_target_id, int):
                target_label = str(raw_target_id)
            else:
                target_label = "不明"
            if source_node is None or target_node is None:
                failed_operations.append(
                    "接続（source="
                    + source_label
                    + ", target="
                    + target_label
                    + "）のノードが見つからないため再現できませんでした。"
                )
                continue
            source_name, source_index = self._parse_connection_port_reference(
                connection.get("source_port"),
                connection.get("source_port_index"),
            )
            target_name, target_index = self._parse_connection_port_reference(
                connection.get("target_port"),
                connection.get("target_port_index"),
            )
            source_port = self._find_port(
                source_node,
                port_name=source_name,
                port_index=source_index,
                output=True,
            )
            target_port = self._find_port(
                target_node,
                port_name=target_name,
                port_index=target_index,
                output=False,
            )
            if source_port is None:
                source_port = self._first_output_port(source_node)
            if target_port is None:
                target_port = self._first_input_port(target_node)
            if source_port is None or target_port is None:
                missing_parts: List[str] = []
                if source_port is None:
                    missing_parts.append("出力ポート")
                if target_port is None:
                    missing_parts.append("入力ポート")
                reason = "と".join(missing_parts)
                failed_operations.append(
                    f"接続（source={source_label}, target={target_label}）の{reason}を特定できませんでした。"
                )
                continue
            try:
                self._connect_ports_compat(source_port, target_port)
            except Exception as exc:
                failed_operations.append(
                    f"接続（source={source_label}, target={target_label}）の再現に失敗しました: {exc}"
                )
                continue

        self._node_spawn_offset = len(self._known_nodes)
        self._task_count = sum(
            1 for node in self._known_nodes if self._node_type_identifier(node) == "sotugyo.demo.TaskNode"
        )
        self._review_count = sum(
            1 for node in self._known_nodes if self._node_type_identifier(node) == "sotugyo.demo.ReviewNode"
        )
        self._memo_count = sum(
            1 for node in self._known_nodes if self._node_type_identifier(node) == MemoNode.node_type_identifier()
        )
        self._rebuild_timeline_reference()
        self._apply_timeline_constraints_to_nodes(self._known_nodes)

        clear_selection = getattr(self._graph, "clear_selection", None)
        if callable(clear_selection):
            clear_selection()
        self._on_selection_changed()
        self._refresh_node_catalog()

        if failed_operations:
            summary = "\n".join(f"・{message}" for message in failed_operations)
            self._show_warning_dialog(
                "プロジェクトの再構成中に一部のコネクションを再現できませんでした。\n" + summary
            )

        return metadata_changed

    def _safe_node_name(self, node) -> str:
        if hasattr(node, "name"):
            try:
                return str(node.name())
            except Exception:
                pass
        return str(node)

    def _node_custom_properties(self, node) -> Dict[str, object]:
        model = getattr(node, "model", None)
        if model is None:
            return {}
        props = getattr(model, "custom_properties", None)
        if callable(props):
            try:
                props = props()
            except Exception:  # pragma: no cover - NodeGraph 依存の例外
                props = None
        if not isinstance(props, dict):
            return {}
        serializable: Dict[str, object] = {}
        for key, value in props.items():
            if isinstance(key, str):
                if isinstance(value, (str, int, float, bool)) or value is None:
                    serializable[key] = value
                else:
                    serializable[key] = str(value)
        return serializable

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

    @staticmethod
    def _connected_ports(port) -> List:
        connected_getter = getattr(port, "connected_ports", None)
        if not callable(connected_getter):
            return []
        try:
            return list(connected_getter() or [])
        except Exception:
            return []

    def _collect_ports(self, node, *, output: bool) -> List[Port]:
        accessor = "output_ports" if output else "input_ports"
        ports_getter = getattr(node, accessor, None)
        if not callable(ports_getter):
            return []
        try:
            raw_ports = ports_getter()
        except Exception:
            return []
        if not raw_ports:
            return []
        if isinstance(raw_ports, Mapping):
            candidates = raw_ports.values()
        elif isinstance(raw_ports, IterableABC) and not isinstance(raw_ports, (str, bytes)):
            candidates = raw_ports
        else:
            return []
        ports: List[Port] = []
        for entry in candidates:
            if isinstance(entry, Port):
                ports.append(entry)
        return ports

    def _port_index_in_node(self, node, port, *, output: bool) -> Optional[int]:
        for index, candidate in enumerate(self._collect_ports(node, output=output)):
            if candidate is port:
                return index
        return None

    @staticmethod
    def _parse_connection_port_reference(
        port_entry, index_entry
    ) -> Tuple[Optional[str], Optional[int]]:
        name: Optional[str] = None
        index: Optional[int] = None
        
        def _normalize_index(value) -> Optional[int]:
            if isinstance(value, bool):
                return None
            try:
                return int(value)
            except (TypeError, ValueError):
                return None

        if isinstance(port_entry, dict):
            raw_name = port_entry.get("name")
            if isinstance(raw_name, str):
                name = raw_name
            raw_index = port_entry.get("index")
            normalized = _normalize_index(raw_index)
            if normalized is not None:
                index = normalized
        elif isinstance(port_entry, str):
            name = port_entry
        normalized_index = _normalize_index(index_entry)
        if normalized_index is not None:
            index = normalized_index
        return name, index

    def _find_port(
        self,
        node,
        *,
        port_name: Optional[str],
        port_index: Optional[int],
        output: bool,
    ) -> Optional[Port]:
        ports = self._collect_ports(node, output=output)
        if not ports:
            return None
        if isinstance(port_index, int) and 0 <= port_index < len(ports):
            candidate = ports[port_index]
            candidate_name = self._safe_port_name(candidate)
            if port_name is not None and candidate_name != port_name:
                node_identifier = getattr(node, "name", None)
                if callable(node_identifier):
                    node_identifier = node_identifier()
                if node_identifier is None:
                    node_identifier = repr(node)
                LOGGER.debug(
                    "ポート名の不一致: index=%s, expected=%s, actual=%s, node=%s",
                    port_index,
                    port_name,
                    candidate_name,
                    node_identifier,
                )
            return candidate
        for index, port in enumerate(ports):
            if port_name is not None and self._safe_port_name(port) != port_name:
                continue
            if port_index is not None and port_index != index:
                continue
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
