"""UI コンポーネント。"""

from __future__ import annotations

from importlib import import_module

_CONTENT_EXPORTS = {"NodeContentBrowser", "NodeCatalogEntry"}
_NODE_EXPORTS = {
    "BaseDemoNode",
    "MemoNode",
    "ReviewNode",
    "TaskNode",
    "ToolEnvironmentNode",
}

__all__ = sorted(_CONTENT_EXPORTS | _NODE_EXPORTS)


def __getattr__(name: str):
    if name in _CONTENT_EXPORTS:
        module = import_module(f"{__name__}.content_browser")
        value = getattr(module, name)
        globals()[name] = value
        return value
    if name in _NODE_EXPORTS:
        module = import_module(f"{__name__}.nodes")
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
