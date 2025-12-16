"""ノードインスペクタ用の部品。"""

from __future__ import annotations

from typing import Mapping, Optional, Tuple

from qtpy import QtCore, QtWidgets

Qt = QtCore.Qt
Signal = QtCore.Signal
QAbstractItemView = QtWidgets.QAbstractItemView
QDockWidget = QtWidgets.QDockWidget
QFrame = QtWidgets.QFrame
QFormLayout = QtWidgets.QFormLayout
QHBoxLayout = QtWidgets.QHBoxLayout
QHeaderView = QtWidgets.QHeaderView
QLabel = QtWidgets.QLabel
QLineEdit = QtWidgets.QLineEdit
QPushButton = QtWidgets.QPushButton
QSpinBox = QtWidgets.QSpinBox
QTabWidget = QtWidgets.QTabWidget
QTableWidget = QtWidgets.QTableWidget
QTableWidgetItem = QtWidgets.QTableWidgetItem
QTextEdit = QtWidgets.QTextEdit
QVBoxLayout = QtWidgets.QVBoxLayout
QWidget = QtWidgets.QWidget


class NodeInspectorPanel(QWidget):
    """ノードの詳細と編集操作をまとめたパネル。"""

    rename_requested = Signal(str)
    memo_text_changed = Signal(str)
    memo_font_changed = Signal(int)
    launch_tool_requested = Signal()

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        memo_font_range: Tuple[int, int] = (8, 72),
        memo_font_default: int = 12,
    ) -> None:
        super().__init__(parent)
        self._memo_font_range = memo_font_range
        self._memo_font_default = memo_font_default
        self._memo_controls_active = False

        self._detail_name_label = QLabel("-", self)
        self._detail_type_label = QLabel("-", self)
        self._detail_uuid_label = QLabel("-", self)
        self._detail_position_label = QLabel("-", self)

        self._rename_input = QLineEdit(self)
        self._rename_button = QPushButton("名前を更新", self)
        self._rename_button.clicked.connect(self._emit_rename_request)
        self._rename_input.returnPressed.connect(self._emit_rename_request)

        self._memo_text_edit = QTextEdit(self)
        self._memo_text_edit.setAcceptRichText(False)
        self._memo_text_edit.setPlaceholderText("メモノードの内容を入力")
        self._memo_text_edit.setMinimumHeight(140)
        self._memo_text_edit.textChanged.connect(self._on_memo_text_changed)

        self._memo_font_spin = QSpinBox(self)
        self._memo_font_spin.setRange(*self._memo_font_range)
        self._memo_font_spin.setValue(self._memo_font_default)
        self._memo_font_spin.valueChanged.connect(self._on_memo_font_changed)

        self._launch_tool_button = QPushButton("Rez 環境で起動", self)
        self._launch_tool_button.setEnabled(False)
        self._launch_tool_button.clicked.connect(self.launch_tool_requested)

        self._property_table = QTableWidget(self)
        self._property_table.setColumnCount(2)
        self._property_table.setHorizontalHeaderLabels(["キー", "値"])
        header = self._property_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        self._property_table.verticalHeader().setVisible(False)
        self._property_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._property_table.setSelectionMode(QAbstractItemView.NoSelection)
        self._property_table.setFocusPolicy(Qt.NoFocus)
        self._property_table.setAlternatingRowColors(True)

        self._tabs = QTabWidget(self)
        self._tabs.setMinimumWidth(260)
        self._tabs.addTab(self._build_detail_tab(), "ノード詳細")
        self._tabs.addTab(self._build_operation_tab(), "ノード操作")
        self._tabs.addTab(self._build_property_tab(), "プロパティ")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._tabs)

        self.disable_rename()
        self.clear_memo()

    def _build_detail_tab(self) -> QWidget:
        widget = QFrame(self)
        widget.setObjectName("inspectorSection")
        layout = QFormLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        layout.addRow("名前", self._detail_name_label)
        layout.addRow("タイプ", self._detail_type_label)
        layout.addRow("UUID", self._detail_uuid_label)
        layout.addRow("位置", self._detail_position_label)
        layout.addRow("ツール起動", self._launch_tool_button)
        return widget

    def _build_operation_tab(self) -> QWidget:
        widget = QFrame(self)
        widget.setObjectName("inspectorSection")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        rename_label = QLabel("名前の変更", widget)
        rename_label.setObjectName("panelTitle")
        layout.addWidget(rename_label)

        self._rename_input.setPlaceholderText("ノード名を入力")
        layout.addWidget(self._rename_input)
        layout.addWidget(self._rename_button)

        memo_label = QLabel("メモ編集", widget)
        memo_label.setObjectName("panelTitle")
        layout.addWidget(memo_label)

        layout.addWidget(self._memo_text_edit)

        memo_font_layout = QHBoxLayout()
        memo_font_label = QLabel("文字サイズ", widget)
        memo_font_layout.addWidget(memo_font_label)
        memo_font_layout.addWidget(self._memo_font_spin)
        layout.addLayout(memo_font_layout)

        layout.addStretch(1)
        return widget

    def update_node_details(
        self,
        *,
        name: str,
        node_type: object,
        node_uuid: str,
        position_text: str,
    ) -> None:
        """選択ノードの詳細情報を表示する。"""

        self._detail_name_label.setText(name or "-")
        self._detail_type_label.setText(str(node_type) if node_type else "-")
        self._detail_uuid_label.setText(node_uuid or "-")
        self._detail_position_label.setText(position_text or "-")

    def clear_node_details(self) -> None:
        """詳細情報をリセットする。"""

        self._detail_name_label.setText("-")
        self._detail_type_label.setText("-")
        self._detail_uuid_label.setText("-")
        self._detail_position_label.setText("-")
        self.set_tool_launch_enabled(False)
        self.clear_properties()

    def enable_rename(self, value: str) -> None:
        """リネーム操作を有効化する。"""

        self._rename_input.blockSignals(True)
        self._rename_input.setText(value)
        self._rename_input.setEnabled(True)
        self._rename_input.blockSignals(False)
        self._rename_button.setEnabled(True)

    def disable_rename(self) -> None:
        """リネーム操作を無効化する。"""

        self._rename_input.blockSignals(True)
        self._rename_input.clear()
        self._rename_input.blockSignals(False)
        self._rename_input.setEnabled(False)
        self._rename_button.setEnabled(False)

    def show_memo(self, text: str, font_size: int) -> None:
        """メモ編集欄へ内容を反映する。"""

        normalized_size = self._normalize_font_size(font_size)
        self._memo_controls_active = True
        self._memo_text_edit.setPlainText(text)
        self._memo_font_spin.setValue(normalized_size)
        self._memo_controls_active = False
        self._set_memo_enabled(True)

    def clear_memo(self) -> None:
        """メモ編集欄をリセットする。"""

        self._memo_controls_active = True
        self._memo_text_edit.clear()
        self._memo_font_spin.setValue(self._memo_font_default)
        self._memo_controls_active = False
        self._set_memo_enabled(False)

    def _set_memo_enabled(self, enabled: bool) -> None:
        self._memo_text_edit.setEnabled(enabled)
        self._memo_font_spin.setEnabled(enabled)

    def _emit_rename_request(self) -> None:
        if not self._rename_button.isEnabled():
            return
        text = self._rename_input.text().strip()
        self.rename_requested.emit(text)

    def _on_memo_text_changed(self) -> None:
        if self._memo_controls_active:
            return
        self.memo_text_changed.emit(self._memo_text_edit.toPlainText())

    def _on_memo_font_changed(self, value: int) -> None:
        if self._memo_controls_active:
            return
        self.memo_font_changed.emit(self._normalize_font_size(value))

    def _normalize_font_size(self, value: int) -> int:
        minimum, maximum = self._memo_font_range
        try:
            coerced = int(value)
        except (TypeError, ValueError):
            return self._memo_font_default
        return max(minimum, min(maximum, coerced))

    def set_tool_launch_enabled(self, enabled: bool) -> None:
        self._launch_tool_button.setEnabled(enabled)

    def show_properties(self, properties: Mapping[str, object]) -> None:
        if self._property_table is None:
            return
        entries = sorted(properties.items()) if properties else []
        if not entries:
            self.clear_properties()
            return
        self._property_table.setRowCount(len(entries))
        for row, (key, value) in enumerate(entries):
            self._property_table.setItem(row, 0, QTableWidgetItem(str(key)))
            self._property_table.setItem(row, 1, QTableWidgetItem(str(value)))

    def clear_properties(self) -> None:
        if self._property_table is None:
            return
        self._property_table.setRowCount(1)
        self._property_table.setItem(0, 0, QTableWidgetItem("-"))
        self._property_table.setItem(0, 1, QTableWidgetItem("-"))

    def _build_property_tab(self) -> QWidget:
        widget = QFrame(self)
        widget.setObjectName("inspectorSection")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        layout.addWidget(self._property_table)
        return widget


class NodeInspectorDock(QDockWidget):
    """ノードインスペクタ用ドックウィジェット。"""

    rename_requested = Signal(str)
    memo_text_changed = Signal(str)
    memo_font_changed = Signal(int)
    launch_tool_requested = Signal()

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        memo_font_range: Tuple[int, int] = (8, 72),
        memo_font_default: int = 12,
    ) -> None:
        super().__init__("インスペクタ", parent)
        self.setObjectName("InspectorDock")
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.setFeatures(
            QDockWidget.DockWidgetMovable
            | QDockWidget.DockWidgetFloatable
            | QDockWidget.DockWidgetClosable
        )

        panel = NodeInspectorPanel(
            self,
            memo_font_range=memo_font_range,
            memo_font_default=memo_font_default,
        )
        panel.rename_requested.connect(self.rename_requested)
        panel.memo_text_changed.connect(self.memo_text_changed)
        panel.memo_font_changed.connect(self.memo_font_changed)
        panel.launch_tool_requested.connect(self.launch_tool_requested)

        container = QWidget(self)
        container.setObjectName("dockContentContainer")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        layout.addWidget(panel)
        self.setWidget(container)

        self._panel = panel

    def panel(self) -> NodeInspectorPanel:
        """内部パネルを取得する。"""

        return self._panel

    def update_node_details(
        self,
        *,
        name: str,
        node_type: object,
        node_uuid: str,
        position_text: str,
    ) -> None:
        self._panel.update_node_details(
            name=name,
            node_type=node_type,
            node_uuid=node_uuid,
            position_text=position_text,
        )

    def clear_node_details(self) -> None:
        self._panel.clear_node_details()

    def enable_rename(self, value: str) -> None:
        self._panel.enable_rename(value)

    def disable_rename(self) -> None:
        self._panel.disable_rename()

    def show_memo(self, text: str, font_size: int) -> None:
        self._panel.show_memo(text, font_size)

    def clear_memo(self) -> None:
        self._panel.clear_memo()

    def set_tool_launch_enabled(self, enabled: bool) -> None:
        self._panel.set_tool_launch_enabled(enabled)

    def show_properties(self, properties: Mapping[str, object]) -> None:
        self._panel.show_properties(properties)

    def clear_properties(self) -> None:
        self._panel.clear_properties()
