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
            "environment_key",
            "",
            widget_type=NodePropWidgetEnum.QLINE_EDIT.value,
            widget_tooltip="環境定義のキー (Rez パッケージ集合)",
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
        environment_key: str,
        environment_name: str,
        environment_payload: Mapping[str, Any] | None = None,
    ) -> None:
        self.set_name(environment_name)
        self.set_property("environment_key", environment_key, push_undo=False)
        payload = {
            "environment_key": environment_key,
            "environment_name": environment_name,
        }
        if environment_payload:
            payload.update(environment_payload)
        self.set_property(
            "environment_payload", self._serialize_payload(payload), push_undo=False
        )
        self._update_summary()

    def set_property(self, name, value, push_undo: bool = True):  # type: ignore[override]
        super().set_property(name, value, push_undo=push_undo)
        if name in {"environment_payload"}:
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
        payload = self.get_environment_payload()
        summary_hint = payload.get("summary")
        packages = payload.get("rez_packages")
        validation = None
        metadata = payload.get("metadata")
        if isinstance(metadata, dict):
            validation = metadata.get("rez_validation")
        validation_status = payload.get("rez_validation")
        summary_lines = []
        if summary_hint:
            summary_lines.append(str(summary_hint))
        if isinstance(packages, (list, tuple)) and packages:
            preview = ", ".join(str(pkg) for pkg in packages[:3])
            if len(packages) > 3:
                preview += " …"
            summary_lines.append(f"Rez: {preview}")
        validation_map = None
        if isinstance(validation, dict):
            validation_map = validation
        elif isinstance(validation_status, dict):
            validation_map = validation_status
        if isinstance(validation_map, dict) and not validation_map.get("success", False):
            message = (
                validation_map.get("stderr")
                or validation_map.get("stdout")
                or validation_map.get("message")
                or "Rez 環境の解決に失敗しました。"
            )
            summary_lines.append(f"⚠️ {message}")
        tooltip = "\n".join(summary_lines) if summary_lines else "ツール環境"
        view = getattr(self, "view", None)
        if view is not None and hasattr(view, "setToolTip"):
            view.setToolTip(tooltip)


__all__ = ["ToolEnvironmentNode"]
