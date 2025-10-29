"""ユーザーインターフェース層のパッケージ。"""

from __future__ import annotations

_STYLE_EXPORTS = {
    "START_WINDOW_STYLE",
    "apply_base_style",
    "available_style_profiles",
    "get_active_style_profile",
    "get_style_profile",
    "set_style_profile",
}

_PACKAGE_EXPORTS = {"components", "dialogs", "windows"}

__all__ = sorted(_STYLE_EXPORTS | _PACKAGE_EXPORTS)


def __getattr__(name: str):
    if name in _PACKAGE_EXPORTS:
        import importlib

        module = importlib.import_module(f"{__name__}.{name}")
        globals()[name] = module
        return module
    if name in _STYLE_EXPORTS:
        from . import style

        value = getattr(style, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
