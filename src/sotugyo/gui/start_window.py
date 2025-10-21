"""スタート画面の実装。"""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from .node_editor_window import NodeEditorWindow


class StartWindow(QMainWindow):
    """ノード編集テストへ遷移するスタート画面。"""

    WINDOW_TITLE = "スタート画面"

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(self.WINDOW_TITLE)
        self.resize(480, 320)
        self._node_window: Optional[NodeEditorWindow] = None

        self._init_ui()

    def _init_ui(self) -> None:
        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        title = QLabel("ノードエディタ デモへようこそ")
        title.setObjectName("startTitle")
        title.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        layout.addWidget(title)

        description = QLabel(
            "このデモではタスクとレビューの 2 種類のノードを作成し、"
            "接続・切断・削除などの基本操作を試すことができます。"
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        layout.addItem(QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding))

        button_row = QHBoxLayout()
        button_row.addStretch(1)

        open_button = QPushButton("ノード編集テストを開く")
        open_button.clicked.connect(self._open_node_editor)
        button_row.addWidget(open_button)

        layout.addLayout(button_row)

        layout.addItem(QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding))

        self.setCentralWidget(container)

    def _open_node_editor(self) -> None:
        if self._node_window is None:
            self._node_window = NodeEditorWindow(self)
            self._node_window.return_to_start_requested.connect(
                self._on_return_to_start_requested
            )
        self._node_window.show()
        self._node_window.raise_()
        self._node_window.activateWindow()
        self.hide()

    def _on_return_to_start_requested(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()
