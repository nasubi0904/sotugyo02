"""ウィンドウ UI のエントリポイント。"""

from __future__ import annotations

from .controllers.start import StartWindowController
from .docks.content_browser import NodeContentBrowserDock
from .docks.inspector import NodeInspectorDock
from .toolbars.timeline_alignment import TimelineAlignmentToolBar
from .views.node_editor import NodeEditorWindow
from .views.start import StartWindow

__all__ = [
    "NodeContentBrowserDock",
    "NodeEditorWindow",
    "NodeInspectorDock",
    "StartWindow",
    "StartWindowController",
    "TimelineAlignmentToolBar",
]
