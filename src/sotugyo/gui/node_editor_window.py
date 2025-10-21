"""ノード編集画面のウィンドウ実装。"""

from __future__ import annotations

from typing import Iterable, List, Optional

from PySide6.QtCore import Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
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

        self._side_tabs: Optional[QTabWidget] = None
        self._detail_name_label: Optional[QLabel] = None
        self._detail_type_label: Optional[QLabel] = None
        self._detail_position_label: Optional[QLabel] = None
        self._rename_input: Optional[QLineEdit] = None
        self._rename_button: Optional[QPushButton] = None
        self._search_input: Optional[QLineEdit] = None

        self._init_ui()
        self._setup_graph_signals()
        self._update_selected_node_info()

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

        content_layout.addWidget(self._side_tabs)
        content_layout.addWidget(self._graph_widget, 1)

        root_layout.addLayout(content_layout, 1)
        root_layout.addWidget(self._build_bottom_panel())

        self.setCentralWidget(container)

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
        node.set_pos([pos_x, pos_y])
        self._node_spawn_offset += 1
        self._known_nodes.append(node)

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

    def _return_to_start(self) -> None:
        self.hide()
        self.return_to_start_requested.emit()

    def closeEvent(self, event: QCloseEvent) -> None:
        super().closeEvent(event)
        self.return_to_start_requested.emit()
