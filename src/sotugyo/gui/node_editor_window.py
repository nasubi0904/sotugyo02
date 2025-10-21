"""ノード編集画面のウィンドウ実装。"""

from __future__ import annotations

from typing import Iterable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QSizePolicy,
    QToolBar,
    QWidget,
)
from NodeGraphQt import NodeGraph, Port

from .nodes import ReviewNode, TaskNode


class NodeEditorWindow(QMainWindow):
    """NodeGraphQt を用いたノード編集画面。"""

    WINDOW_TITLE = "ノード編集テスト"

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

        self._init_ui()

    # ------------------------------------------------------------------
    # UI 初期化
    # ------------------------------------------------------------------
    def _init_ui(self) -> None:
        container = QWidget(self)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._graph_widget)
        self.setCentralWidget(container)

        toolbar = QToolBar("ノード操作", self)
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.addToolBar(Qt.TopToolBarArea, toolbar)

        create_task_action = toolbar.addAction("タスク追加")
        create_task_action.triggered.connect(self._create_task_node)

        create_review_action = toolbar.addAction("レビュー追加")
        create_review_action.triggered.connect(self._create_review_node)

        delete_action = toolbar.addAction("選択ノード削除")
        delete_action.triggered.connect(self._delete_selected_nodes)

        connect_action = toolbar.addAction("選択ノード接続")
        connect_action.triggered.connect(self._connect_selected_nodes)

        disconnect_action = toolbar.addAction("選択ノード切断")
        disconnect_action.triggered.connect(self._disconnect_selected_nodes)

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

    def _delete_selected_nodes(self) -> None:
        nodes = self._graph.selected_nodes()
        if not nodes:
            self._show_info_dialog("削除するノードを選択してください。")
            return
        self._graph.delete_nodes(nodes)

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
