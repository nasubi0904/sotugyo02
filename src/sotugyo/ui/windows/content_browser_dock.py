"""コンテンツブラウザ用ドックの定義。"""

from __future__ import annotations

from typing import Iterable, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDockWidget, QVBoxLayout, QWidget

from ..components.content_browser import NodeCatalogEntry, NodeContentBrowser


class NodeContentBrowserDock(QDockWidget):
    """ノードカタログ表示を提供するドックウィジェット。"""

    node_type_requested = Signal(str)
    search_submitted = Signal(str)
    back_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("コンテンツブラウザ", parent)
        self.setObjectName("ContentBrowserDock")
        self.setAllowedAreas(Qt.TopDockWidgetArea | Qt.BottomDockWidgetArea)
        self.setFeatures(
            QDockWidget.DockWidgetMovable
            | QDockWidget.DockWidgetFloatable
            | QDockWidget.DockWidgetClosable
        )

        browser = NodeContentBrowser(self)
        browser.setMinimumHeight(160)
        browser.node_type_requested.connect(self.node_type_requested)
        browser.search_submitted.connect(self.search_submitted)
        browser.back_requested.connect(self.back_requested)

        container = QWidget(self)
        container.setObjectName("dockContentContainer")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        layout.addWidget(browser)
        self.setWidget(container)

        self._browser = browser

    def set_catalog_entries(self, entries: Iterable[NodeCatalogEntry]) -> None:
        """ブラウザにカタログを設定する。"""

        self._browser.set_catalog_entries(entries)

    def focus_search(self) -> None:
        """検索入力へフォーカスを移す。"""

        self._browser.focus_search()

    def first_visible_available_type(self) -> Optional[str]:
        """現在表示されているエントリのうち最初のノード種別を取得する。"""

        return self._browser.first_visible_available_type()

    def current_search_text(self) -> str:
        """検索入力の現在値を返す。"""

        return self._browser.current_search_text()

