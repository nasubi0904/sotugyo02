"""ツール環境ノード。"""

from __future__ import annotations

import json
import logging
from typing import Any, ClassVar, Dict, Mapping

from sotugyo.qt_compat import ensure_qt_module_alias

ensure_qt_module_alias()
from NodeGraphQt import BaseNode
from NodeGraphQt.constants import NodePropWidgetEnum


LOGGER = logging.getLogger(__name__)


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
            "environment_payload",
            "{}",
            widget_type=NodePropWidgetEnum.QTEXT_EDIT.value,
            widget_tooltip="環境再現に必要な情報 (JSON)",
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
        environment_payload: Mapping[str, Any] | None = None,
    ) -> None:
        self.set_name(environment_name)
        self.set_property("environment_id", environment_id, push_undo=False)
        self.set_property("tool_id", tool_id, push_undo=False)
        self.set_property("tool_name", tool_name, push_undo=False)
        self.set_property("version_label", version_label, push_undo=False)
        payload = environment_payload or {
            "environment_id": environment_id,
            "tool_id": tool_id,
            "tool_name": tool_name,
            "version_label": version_label,
        }
        self.set_property("environment_payload", self._serialize_payload(payload), push_undo=False)
        self._update_summary()

    def set_property(self, name, value, push_undo: bool = True):  # type: ignore[override]
        super().set_property(name, value, push_undo=push_undo)
        if name in {"tool_name", "version_label", "environment_payload"}:
            self._update_summary()

    def get_environment_payload(self) -> Dict[str, Any]:
        """環境情報を辞書として返す。"""

        try:
            raw_value = self.get_property("environment_payload")
        except Exception:  # pragma: no cover - NodeGraph 依存の例外
            LOGGER.debug("environment_payload の取得に失敗しました", exc_info=True)
            return {}
        if not isinstance(raw_value, str):
            return {}
        try:
            data = json.loads(raw_value)
        except json.JSONDecodeError:
            LOGGER.warning("environment_payload の JSON デコードに失敗しました: %s", raw_value)
            return {}
        if not isinstance(data, dict):
            return {}
        return data

    def _serialize_payload(self, payload: Mapping[str, Any]) -> str:
        try:
            return json.dumps(payload, ensure_ascii=False, sort_keys=True)
        except (TypeError, ValueError):
            LOGGER.warning("環境ペイロードのシリアライズに失敗しました: %s", payload, exc_info=True)
            return "{}"

    def _update_summary(self) -> None:
        try:
            tool_name = str(self.get_property("tool_name"))
        except Exception:  # pragma: no cover - NodeGraph 依存の例外
            LOGGER.debug("tool_name の取得に失敗しました", exc_info=True)
            tool_name = ""
        try:
            version_label = str(self.get_property("version_label"))
        except Exception:  # pragma: no cover - NodeGraph 依存の例外
            LOGGER.debug("version_label の取得に失敗しました", exc_info=True)
            version_label = ""
        payload = self.get_environment_payload()
        summary_hint = payload.get("summary")
        summary_lines = []
        if tool_name:
            summary_lines.append(tool_name)
        if version_label:
            summary_lines.append(f"Version: {version_label}")
        if summary_hint:
            summary_lines.append(str(summary_hint))
        tooltip = "\n".join(summary_lines) if summary_lines else "ツール環境"
        view = getattr(self, "view", None)
        if view is not None and hasattr(view, "setToolTip"):
            view.setToolTip(tooltip)


__all__ = ["ToolEnvironmentNode"]
