"""ノード編集画面のウィンドウ実装。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from PySide6.QtCore import Signal
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from NodeGraphQt import NodeGraph, Port

from .nodes import ReviewNode, TaskNode


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
        self._current_project_path: Optional[Path] = None

        self._side_tabs: Optional[QTabWidget] = None
        self._detail_name_label: Optional[QLabel] = None
        self._detail_type_label: Optional[QLabel] = None
        self._detail_position_label: Optional[QLabel] = None
        self._rename_input: Optional[QLineEdit] = None
        self._rename_button: Optional[QPushButton] = None
        self._search_input: Optional[QLineEdit] = None

        self._init_ui()
        self._create_menus()
        self._setup_graph_signals()
        self._update_selected_node_info()
        self._set_modified(False)

    # ------------------------------------------------------------------
    # UI 初期化
    # ------------------------------------------------------------------
    def _init_ui(self) -> None:
        container = QWidget(self)
        root_layout = QVBoxLayout(container)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self._side_tabs = QTabWidget(container)
        self._side_tabs.setMinimumWidth(260)
        self._side_tabs.addTab(self._build_detail_tab(), "ノード詳細")
        self._side_tabs.addTab(self._build_operation_tab(), "ノード操作")

        content_layout.addWidget(self._graph_widget, 1)
        content_layout.addWidget(self._side_tabs)

        root_layout.addLayout(content_layout, 1)
        root_layout.addWidget(self._build_bottom_panel())

        self.setCentralWidget(container)

    def _create_menus(self) -> None:
        menubar = self.menuBar()

        file_menu = menubar.addMenu("File")

        save_action = QAction("上書き保存", self)
        save_action.triggered.connect(self._file_save)
        file_menu.addAction(save_action)

        save_as_action = QAction("別名保存...", self)
        save_as_action.triggered.connect(self._file_save_as)
        file_menu.addAction(save_as_action)

        import_action = QAction("インポート...", self)
        import_action.triggered.connect(self._file_import)
        file_menu.addAction(import_action)

        option_menu = menubar.addMenu("Option")
        project_settings_action = QAction("プロジェクト設定...", self)
        project_settings_action.triggered.connect(self._open_project_settings)
        option_menu.addAction(project_settings_action)

        setting_menu = menubar.addMenu("Setting")
        machine_settings_action = QAction("マシン設定...", self)
        machine_settings_action.triggered.connect(self._open_machine_settings)
        setting_menu.addAction(machine_settings_action)

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

    def _build_bottom_panel(self) -> QWidget:
        panel = QWidget(self)
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        self._search_input = QLineEdit(panel)
        self._search_input.setPlaceholderText("ノード名で検索")
        layout.addWidget(self._search_input)

        search_button = QPushButton("検索", panel)
        search_button.clicked.connect(self._search_nodes)
        layout.addWidget(search_button)

        layout.addSpacing(12)

        add_task_button = QPushButton("タスク追加", panel)
        add_task_button.clicked.connect(self._create_task_node)
        layout.addWidget(add_task_button)

        add_review_button = QPushButton("レビュー追加", panel)
        add_review_button.clicked.connect(self._create_review_node)
        layout.addWidget(add_review_button)

        delete_button = QPushButton("選択ノード削除", panel)
        delete_button.clicked.connect(self._delete_selected_nodes)
        layout.addWidget(delete_button)

        connect_button = QPushButton("選択ノード接続", panel)
        connect_button.clicked.connect(self._connect_selected_nodes)
        layout.addWidget(connect_button)

        disconnect_button = QPushButton("選択ノード切断", panel)
        disconnect_button.clicked.connect(self._disconnect_selected_nodes)
        layout.addWidget(disconnect_button)

        layout.addStretch(1)

        back_button = QPushButton("スタート画面に戻る", panel)
        back_button.clicked.connect(self._return_to_start)
        layout.addWidget(back_button)

        return panel

    def _open_project_settings(self) -> None:
        self._show_info_dialog(
            "プロジェクトごとの設定項目は現在準備中です。"
        )

    def _open_machine_settings(self) -> None:
        self._show_info_dialog(
            "マシン依存の設定項目は現在準備中です。"
        )

    def _setup_graph_signals(self) -> None:
        selection_signal = getattr(self._graph, "selection_changed", None)
        if selection_signal is not None and hasattr(selection_signal, "connect"):
            selection_signal.connect(self._on_selection_changed)
        else:
            selection_signal = getattr(self._graph, "node_selection_changed", None)
            if selection_signal is not None and hasattr(selection_signal, "connect"):
                selection_signal.connect(self._on_selection_changed)

    # ------------------------------------------------------------------
    # ノード生成・削除
    # ------------------------------------------------------------------
    def _create_task_node(self) -> None:
        self._task_count += 1
        self._create_node("sotugyo.demo.TaskNode", f"タスク {self._task_count}")

    def _create_review_node(self) -> None:
        self._review_count += 1
        self._create_node("sotugyo.demo.ReviewNode", f"レビュー {self._review_count}")

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

    def _delete_selected_nodes(self) -> None:
        nodes = self._graph.selected_nodes()
        if not nodes:
            self._show_info_dialog("削除するノードを選択してください。")
            return
        self._graph.delete_nodes(nodes)
        self._known_nodes = [node for node in self._known_nodes if node not in nodes]
        self._on_selection_changed()
        self._set_modified(True)

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

    def _search_nodes(self) -> None:
        if self._search_input is None:
            return
        keyword = self._search_input.text().strip()
        if not keyword:
            self._show_info_dialog("検索キーワードを入力してください。")
            return

        keyword_lower = keyword.lower()
        matched = [
            node
            for node in self._collect_all_nodes()
            if hasattr(node, "name") and keyword_lower in node.name().lower()
        ]
        if not matched:
            self._show_info_dialog(f"「{keyword}」に一致するノードが見つかりません。")
            return

        clear_selection = getattr(self._graph, "clear_selection", None)
        if callable(clear_selection):
            clear_selection()

        target = matched[0]
        if hasattr(target, "set_selected"):
            target.set_selected(True)
        if hasattr(self._graph_widget, "centerOn") and hasattr(target, "view"):
            try:
                self._graph_widget.centerOn(target.view)
            except Exception:
                pass
        self._on_selection_changed()

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

    def _return_to_start(self) -> None:
        if not self._confirm_discard_changes("未保存の変更があります。スタート画面に戻りますか？"):
            return
        self.hide()
        self.return_to_start_requested.emit()

    # ------------------------------------------------------------------
    # プロジェクトの保存・読み込み
    # ------------------------------------------------------------------
    def _file_save(self) -> None:
        if self._current_project_path is None:
            self._file_save_as()
            return
        try:
            self._write_project_to_path(self._current_project_path)
            self._set_modified(False)
            self._show_info_dialog("プロジェクトを保存しました。")
        except OSError as exc:
            self._show_error_dialog(f"保存に失敗しました: {exc}")

    def _file_save_as(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "保存先を選択",
            "",
            "Project Files (*.json);;All Files (*)",
        )
        if not filename:
            return
        target_path = Path(filename)
        try:
            self._write_project_to_path(target_path)
        except OSError as exc:
            self._show_error_dialog(f"保存に失敗しました: {exc}")
            return
        self._current_project_path = target_path
        self._set_modified(False)
        self._show_info_dialog("プロジェクトを保存しました。")

    def _file_import(self) -> None:
        if not self._confirm_discard_changes(
            "現在の編集内容が失われる可能性があります。インポートを続行しますか？"
        ):
            return
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "プロジェクトをインポート",
            "",
            "Project Files (*.json);;All Files (*)",
        )
        if not filename:
            return
        source_path = Path(filename)
        try:
            self._load_project_from_path(source_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            self._show_error_dialog(f"インポートに失敗しました: {exc}")
            return
        self._current_project_path = source_path
        self._set_modified(False)
        self._show_info_dialog("プロジェクトをインポートしました。")

    def _write_project_to_path(self, path: Path) -> None:
        state = self._export_project_state()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(state, handle, ensure_ascii=True, indent=2)

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
                    connections.append(
                        {
                            "source": node_id_map[node],
                            "source_port": self._safe_port_name(port),
                            "target": node_id_map[target_node],
                            "target_port": self._safe_port_name(connected),
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
        title = self._base_window_title
        if modified:
            title = f"*{title}"
        self.setWindowTitle(title)

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
