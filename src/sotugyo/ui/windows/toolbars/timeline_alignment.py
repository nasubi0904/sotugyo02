"""タイムライン整列ツールバー。"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QSizePolicy, QStyle, QToolBar, QToolButton, QWidget


class TimelineAlignmentToolBar(QToolBar):
    """ノード整列操作に特化したツールバー。"""

    align_inputs_requested = Signal()
    align_outputs_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("ノード整列", parent)
        self.setObjectName("AlignmentToolBar")
        self.setOrientation(Qt.Vertical)
        self.setIconSize(QSize(24, 24))
        self.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.setAllowedAreas(Qt.LeftToolBarArea | Qt.RightToolBarArea)
        self.setMovable(True)
        self.setFloatable(True)
        self.setMinimumWidth(72)

        layout = self.layout()
        if layout is not None:
            layout.setSpacing(12)
            layout.setContentsMargins(12, 16, 12, 16)

        self._align_inputs_action = self.addAction(
            self.style().standardIcon(QStyle.SP_ArrowBack),
            "入力側整列",
        )
        self._align_inputs_action.setToolTip("入力側ノードを整列")
        self._align_inputs_action.setEnabled(False)
        self._align_inputs_action.triggered.connect(self.align_inputs_requested)
        inputs_button = self.widgetForAction(self._align_inputs_action)
        if isinstance(inputs_button, QToolButton):
            inputs_button.setAutoRaise(False)

        self._align_outputs_action = self.addAction(
            self.style().standardIcon(QStyle.SP_ArrowForward),
            "出力側整列",
        )
        self._align_outputs_action.setToolTip("出力側ノードを整列")
        self._align_outputs_action.setEnabled(False)
        self._align_outputs_action.triggered.connect(self.align_outputs_requested)
        outputs_button = self.widgetForAction(self._align_outputs_action)
        if isinstance(outputs_button, QToolButton):
            outputs_button.setAutoRaise(False)

        spacer = QWidget(self)
        spacer.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.addWidget(spacer)

    def set_alignment_enabled(self, *, inputs: bool, outputs: bool) -> None:
        """整列ボタンの有効状態をまとめて更新する。"""

        self._align_inputs_action.setEnabled(inputs)
        self._align_outputs_action.setEnabled(outputs)

