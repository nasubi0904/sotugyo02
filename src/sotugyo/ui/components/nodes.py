"""ノードエディタで利用するカスタムノード定義。"""

from __future__ import annotations

from typing import ClassVar, Optional

from PySide6.QtCore import QPointF, Qt, QRectF
from PySide6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QTextOption,
    QUndoCommand,
)
from PySide6.QtWidgets import (
    QGraphicsItem,
    QSizePolicy,
    QTextEdit,
)
from NodeGraphQt import BaseNode
from NodeGraphQt.constants import NodePropWidgetEnum
from NodeGraphQt.widgets.node_widgets import NodeBaseWidget


class MemoTextWidget(NodeBaseWidget):
    """ノード内に常駐するメモ用テキストエディタ。"""

    MIN_CONTENT_WIDTH: ClassVar[int] = 200
    MIN_CONTENT_HEIGHT: ClassVar[int] = 140

    def __init__(
        self,
        parent=None,
        name: str = "memo_text",
        label: str = "",
        text: str = "",
    ) -> None:
        super().__init__(parent, name, label)
        self._block_signal = False
        editor = QTextEdit()
        editor.setAcceptRichText(False)
        editor.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        editor.setPlaceholderText("メモを入力")
        editor.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        editor.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        editor.setFrameShape(QTextEdit.NoFrame)
        editor.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        editor.setStyleSheet(
            "QTextEdit {"
            " background-color: rgba(255, 255, 255, 220);"
            " border: 1px solid rgba(0, 0, 0, 40);"
            " border-radius: 4px;"
            " color: #222;"
            " padding: 8px;"
            "}"
        )
        editor.setMinimumWidth(self.MIN_CONTENT_WIDTH)
        editor.setMinimumHeight(self.MIN_CONTENT_HEIGHT)
        editor.setPlainText(text or "")
        editor.textChanged.connect(self._emit_changed)
        self._editor = editor
        self.set_custom_widget(editor)
        container = self.widget()
        if container is not None and container.layout() is not None:
            container.layout().setContentsMargins(0, 0, 0, 0)
        self._apply_explicit_size(
            float(self.MIN_CONTENT_WIDTH),
            float(self.MIN_CONTENT_HEIGHT),
        )

    def _emit_changed(self) -> None:
        if self._block_signal:
            return
        self.on_value_changed()

    def get_value(self) -> str:
        return self._editor.toPlainText()

    def set_value(self, text: str = "") -> None:
        self._block_signal = True
        self._editor.setPlainText(text or "")
        self._block_signal = False

    def set_font_point_size(self, size: int) -> None:
        font = QFont(self._editor.font())
        if size <= 0:
            return
        if font.pointSize() == size:
            return
        font.setPointSize(size)
        self._editor.setFont(font)

    @property
    def minimum_content_width(self) -> float:
        return float(self._editor.minimumWidth())

    @property
    def minimum_content_height(self) -> float:
        return float(self._editor.minimumHeight())

    def resize_contents(self, width: float, height: float) -> None:
        target_width = max(width, self.minimum_content_width)
        target_height = max(height, self.minimum_content_height)
        self._apply_explicit_size(target_width, target_height)

    def _apply_explicit_size(self, width: float, height: float) -> None:
        container = self.widget()
        if container is not None:
            container.setMinimumSize(width, height)
            container.setMaximumSize(width, height)
            container.resize(width, height)
        self.setMinimumSize(width, height)
        self.setMaximumSize(width, height)
        self.setPreferredSize(width, height)
        self._editor.setMinimumSize(width, height)
        self._editor.setMaximumSize(width, height)
        self._editor.resize(width, height)
        self.update()


class MemoNodeResizeHandle(QGraphicsItem):
    """メモノードの右下に表示するサイズ変更ハンドル。"""

    HANDLE_SIZE: ClassVar[float] = 18.0

    def __init__(self, node: "MemoNode") -> None:
        super().__init__(node.view)
        self._node = node
        self._block_update = False
        self.setAcceptedMouseButtons(Qt.LeftButton)
        self.setCursor(Qt.SizeFDiagCursor)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.ItemSendsScenePositionChanges, True)
        self.setZValue(node.view.zValue() + 1)
        self._press_geometry: Optional[tuple[float, float]] = None
        self.update_position()

    def boundingRect(self) -> QRectF:
        size = self.HANDLE_SIZE
        return QRectF(0.0, 0.0, size, size)

    def paint(self, painter: QPainter, option, widget=None) -> None:  # type: ignore[override]
        del option, widget
        painter.save()
        rect = self.boundingRect()
        color = QColor(90, 90, 90)
        if self._node.view.selected:
            color = QColor(254, 207, 42)
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        path = QPainterPath()
        path.moveTo(rect.bottomLeft())
        path.lineTo(rect.bottomRight())
        path.lineTo(rect.topRight())
        painter.drawPath(path)
        painter.restore()

    def update_position(self) -> None:
        if self._block_update:
            return
        width = float(self._node.view.width)
        height = float(self._node.view.height)
        size = self.HANDLE_SIZE
        self._block_update = True
        self.setPos(width - size, height - size)
        self._block_update = False

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):  # type: ignore[override]
        if change == QGraphicsItem.ItemPositionChange and not self._block_update:
            new_pos: QPointF = value  # type: ignore[assignment]
            width = float(new_pos.x() + self.HANDLE_SIZE)
            height = float(new_pos.y() + self.HANDLE_SIZE)
            width = max(width, self._node.minimum_width())
            height = max(height, self._node.minimum_height())
            actual_width, actual_height = self._node.apply_size_interactively(
                width,
                height,
            )
            return QPointF(
                actual_width - self.HANDLE_SIZE,
                actual_height - self.HANDLE_SIZE,
            )
        return super().itemChange(change, value)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        self._press_geometry = (
            float(self._node.view.width),
            float(self._node.view.height),
        )
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        super().mouseReleaseEvent(event)
        if self._press_geometry is None:
            return
        previous_width, previous_height = self._press_geometry
        current_width = float(self._node.view.width)
        current_height = float(self._node.view.height)
        if (
            abs(previous_width - current_width) < 0.01
            and abs(previous_height - current_height) < 0.01
        ):
            self._press_geometry = None
            return
        self._node.commit_size_change(previous_width, previous_height)
        self._press_geometry = None


class _MemoNodeResizeCommand(QUndoCommand):
    """メモノードのサイズ変更をまとめて扱うアンドゥコマンド。"""

    def __init__(
        self,
        node: "MemoNode",
        old_size: tuple[float, float],
        new_size: tuple[float, float],
    ) -> None:
        super().__init__("メモノードのサイズ変更")
        self._node = node
        self._old_size = old_size
        self._new_size = new_size

    def redo(self) -> None:  # type: ignore[override]
        self._apply(self._new_size)

    def undo(self) -> None:  # type: ignore[override]
        self._apply(self._old_size)

    def _apply(self, size: tuple[float, float]) -> None:
        width, height = size
        final_width, final_height = self._node.apply_size_interactively(width, height)
        graph = self._node.graph
        if graph is not None:
            graph.property_changed.emit(self._node, "width", final_width)
            graph.property_changed.emit(self._node, "height", final_height)


class BaseDemoNode(BaseNode):
    """デモ用の基本ノードクラス。

    単一の入力ポートと出力ポートを提供し、
    ノード同士の接続や切断をシンプルに試せる構成にする。
    """

    __identifier__: ClassVar[str] = "sotugyo.demo"
    NODE_NAME: ClassVar[str] = "BaseDemoNode"

    def __init__(self) -> None:
        super().__init__()
        self.add_input("入力")
        self.add_output("出力")


class TaskNode(BaseDemoNode):
    """タスク処理を表すデモノード。"""

    NODE_NAME: ClassVar[str] = "タスクノード"


class ReviewNode(BaseDemoNode):
    """レビュー工程を表すデモノード。"""

    NODE_NAME: ClassVar[str] = "レビュー ノード"


class MemoNode(BaseNode):
    """ノート取り用のメモノード。"""

    __identifier__: ClassVar[str] = "sotugyo.memo"
    NODE_NAME: ClassVar[str] = "メモノード"
    DEFAULT_FONT_SIZE: ClassVar[int] = 16
    MIN_FONT_SIZE: ClassVar[int] = 8
    MAX_FONT_SIZE: ClassVar[int] = 72

    def __init__(self) -> None:
        super().__init__()
        self._text_widget: Optional[MemoTextWidget] = MemoTextWidget(self.view)
        self._resize_handle: Optional[MemoNodeResizeHandle] = None
        self._width_padding: float = 0.0
        self._height_padding: float = 0.0
        self.add_custom_widget(
            self._text_widget,
            widget_type=NodePropWidgetEnum.QTEXT_EDIT.value,
        )
        self.create_property(
            "memo_font_size",
            self.DEFAULT_FONT_SIZE,
            range=(self.MIN_FONT_SIZE, self.MAX_FONT_SIZE),
            widget_type=NodePropWidgetEnum.QSPIN_BOX.value,
            widget_tooltip="メモに適用するフォントサイズ",
        )
        self.set_property("memo_font_size", self.DEFAULT_FONT_SIZE, push_undo=False)
        self._apply_font_size(self.DEFAULT_FONT_SIZE)
        self.set_property("width", 320, push_undo=False)
        self.set_property("height", 240, push_undo=False)
        # 既存より少し暗めのベージュトーンに設定し、視認性を保ちつつ背景との差を付ける。
        self.set_color(238, 231, 200)
        if hasattr(self.view, "setZValue"):
            self.view.setZValue(-1000)
        self._update_size_padding()
        self._resize_handle = MemoNodeResizeHandle(self)
        self.view.draw_node()
        self._update_size_padding()
        if self._resize_handle is not None:
            self._resize_handle.update_position()

    @classmethod
    def node_type_identifier(cls) -> str:
        return f"{cls.__identifier__}.{cls.__name__}"

    def set_property(self, name, value, push_undo: bool = True):  # type: ignore[override]
        normalized = value
        if name == "memo_text":
            normalized = "" if value is None else str(value)
        elif name == "memo_font_size":
            normalized = self._normalize_font_size(value)
        elif name in {"width", "height"}:
            normalized = float(value)
            if name == "width":
                normalized = max(normalized, self.minimum_width())
            else:
                normalized = max(normalized, self.minimum_height())
        previous = None
        if name in {"memo_text", "memo_font_size"}:
            try:
                previous = self.get_property(name)
            except Exception:  # pragma: no cover - NodeGraph 依存の例外
                previous = None
        super().set_property(name, normalized, push_undo=push_undo)
        if name == "memo_text" and self._text_widget is not None:
            if previous != normalized:
                self._text_widget.set_value(str(normalized))
        elif name == "memo_font_size" and self._text_widget is not None:
            self._apply_font_size(normalized)
        elif name in {"width", "height"}:
            width = float(self.view.width)
            height = float(self.view.height)
            self.apply_size_interactively(width, height)

    def _apply_font_size(self, value: object) -> None:
        if self._text_widget is None:
            return
        size = self._normalize_font_size(value)
        self._text_widget.set_font_point_size(size)

    def _normalize_font_size(self, value: object) -> int:
        try:
            size = int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            size = self.DEFAULT_FONT_SIZE
        return max(self.MIN_FONT_SIZE, min(self.MAX_FONT_SIZE, size))

    def minimum_width(self) -> float:
        content_min = 0.0
        if self._text_widget is not None:
            content_min = self._text_widget.minimum_content_width
        return max(content_min + self._width_padding, 220.0)

    def minimum_height(self) -> float:
        content_min = 0.0
        if self._text_widget is not None:
            content_min = self._text_widget.minimum_content_height
        return max(content_min + self._height_padding, 180.0)

    def apply_size_interactively(self, width: float, height: float) -> tuple[float, float]:
        width = max(width, self.minimum_width())
        height = max(height, self.minimum_height())
        if self._text_widget is not None:
            content_width = max(width - self._width_padding, self._text_widget.minimum_content_width)
            content_height = max(height - self._height_padding, self._text_widget.minimum_content_height)
            self._text_widget.resize_contents(content_width, content_height)
        self.view.draw_node()
        self._update_size_padding()
        final_width = float(self.view.width)
        final_height = float(self.view.height)
        self.model.width = final_width
        self.model.height = final_height
        if self._resize_handle is not None:
            self._resize_handle.update_position()
        return final_width, final_height

    def commit_size_change(self, previous_width: float, previous_height: float) -> None:
        if self.graph is None:
            return
        current_width = float(self.view.width)
        current_height = float(self.view.height)
        previous_width = max(previous_width, self.minimum_width())
        previous_height = max(previous_height, self.minimum_height())
        if (
            abs(previous_width - current_width) < 0.01
            and abs(previous_height - current_height) < 0.01
        ):
            return
        command = _MemoNodeResizeCommand(
            self,
            (previous_width, previous_height),
            (current_width, current_height),
        )
        self.graph.undo_stack().push(command)

    def _update_size_padding(self) -> None:
        if self._text_widget is None:
            self._width_padding = 0.0
            self._height_padding = 0.0
            return
        rect = self._text_widget.boundingRect()
        self._width_padding = max(0.0, float(self.view.width) - rect.width())
        self._height_padding = max(0.0, float(self.view.height) - rect.height())


class ToolEnvironmentNode(BaseNode):
    """登録済みツール環境を表すノード。"""

    __identifier__: ClassVar[str] = "sotugyo.tooling"
    NODE_NAME: ClassVar[str] = "ツール環境"

    def __init__(self) -> None:
        super().__init__()
        self.add_input("前段")
        self.add_output("起動")
        self.create_property(
            "environment_id",
            "",
            widget_type=NodePropWidgetEnum.QLINE_EDIT.value,
            widget_tooltip="環境定義の識別子",
        )
        self.create_property(
            "tool_id",
            "",
            widget_type=NodePropWidgetEnum.QLINE_EDIT.value,
            widget_tooltip="参照しているツールの識別子",
        )
        self.create_property(
            "tool_name",
            "",
            widget_type=NodePropWidgetEnum.QLINE_EDIT.value,
            widget_tooltip="ツール名",
        )
        self.create_property(
            "version_label",
            "",
            widget_type=NodePropWidgetEnum.QLINE_EDIT.value,
            widget_tooltip="使用するバージョンの表示名",
        )
        self.create_property(
            "executable_path",
            "",
            widget_type=NodePropWidgetEnum.QLINE_EDIT.value,
            widget_tooltip="実行ファイルのパス",
        )
        self.set_property("width", 260, push_undo=False)
        self.set_property("height", 180, push_undo=False)
        self.set_color(80, 130, 190)

    @classmethod
    def node_type_identifier(cls) -> str:
        return f"{cls.__identifier__}.{cls.__name__}"

    def configure_environment(
        self,
        *,
        environment_id: str,
        environment_name: str,
        tool_id: str,
        tool_name: str,
        version_label: str,
        executable_path: str,
    ) -> None:
        self.set_name(environment_name)
        self.set_property("environment_id", environment_id, push_undo=False)
        self.set_property("tool_id", tool_id, push_undo=False)
        self.set_property("tool_name", tool_name, push_undo=False)
        self.set_property("version_label", version_label, push_undo=False)
        self.set_property("executable_path", executable_path, push_undo=False)
        self._update_summary()

    def set_property(self, name, value, push_undo: bool = True):  # type: ignore[override]
        super().set_property(name, value, push_undo=push_undo)
        if name in {"tool_name", "version_label", "executable_path"}:
            self._update_summary()

    def _update_summary(self) -> None:
        try:
            tool_name = str(self.get_property("tool_name"))
        except Exception:
            tool_name = ""
        try:
            version_label = str(self.get_property("version_label"))
        except Exception:
            version_label = ""
        try:
            executable_path = str(self.get_property("executable_path"))
        except Exception:
            executable_path = ""
        summary_lines = []
        if tool_name:
            summary_lines.append(tool_name)
        if version_label:
            summary_lines.append(f"Version: {version_label}")
        if executable_path:
            summary_lines.append(executable_path)
        tooltip = "\n".join(summary_lines) if summary_lines else "ツール環境"
        view = getattr(self, "view", None)
        if view is not None and hasattr(view, "setToolTip"):
            view.setToolTip(tooltip)
