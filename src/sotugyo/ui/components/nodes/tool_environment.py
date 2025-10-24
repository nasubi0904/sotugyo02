"""ツール環境ノード。"""

from __future__ import annotations

from typing import ClassVar

from NodeGraphQt import BaseNode
from NodeGraphQt.constants import NodePropWidgetEnum


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


__all__ = ["ToolEnvironmentNode"]
