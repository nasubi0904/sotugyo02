"""ノードエディタで利用するカスタムノード定義。"""

from __future__ import annotations

from typing import ClassVar, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QTextOption
from PySide6.QtWidgets import QTextEdit
from NodeGraphQt import BaseNode
from NodeGraphQt.constants import NodePropWidgetEnum
from NodeGraphQt.widgets.node_widgets import NodeBaseWidget


class MemoTextWidget(NodeBaseWidget):
    """ノード内に常駐するメモ用テキストエディタ。"""

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
        editor.setStyleSheet(
            "QTextEdit {"
            " background-color: rgba(255, 255, 255, 220);"
            " border: 1px solid rgba(0, 0, 0, 40);"
            " border-radius: 4px;"
            " color: #222;"
            " padding: 8px;"
            "}"
        )
        editor.setMinimumWidth(240)
        editor.setMinimumHeight(160)
        editor.setPlainText(text or "")
        editor.textChanged.connect(self._emit_changed)
        self._editor = editor
        self.set_custom_widget(editor)
        container = self.widget()
        if container is not None and container.layout() is not None:
            container.layout().setContentsMargins(0, 0, 0, 0)

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

    @classmethod
    def node_type_identifier(cls) -> str:
        return f"{cls.__identifier__}.{cls.__name__}"

    def set_property(self, name, value, push_undo: bool = True):  # type: ignore[override]
        normalized = value
        if name == "memo_text":
            normalized = "" if value is None else str(value)
        elif name == "memo_font_size":
            normalized = self._normalize_font_size(value)
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
