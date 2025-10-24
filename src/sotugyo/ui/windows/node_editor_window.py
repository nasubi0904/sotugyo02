"""ノード編集画面のウィンドウ実装。"""

from __future__ import annotations

import json
import logging
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Iterable as IterableABC, Mapping
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Set, Tuple

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QFontMetrics,
    QKeySequence,
    QResizeEvent,
    QShortcut,
    QShowEvent,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QBoxLayout,
    QComboBox,
    QDialog,
    QDockWidget,
    QFrame,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QSpacerItem,
    QTextEdit,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from NodeGraphQt import NodeGraph, Port


LOGGER = logging.getLogger(__name__)

from ..components.nodes import (
    MemoNode,
    ReviewNode,
    TaskNode,
    ToolEnvironmentNode,
)
from ...domain.projects.service import ProjectContext, ProjectService
from ...domain.projects.settings import ProjectSettings
from ...domain.users.settings import UserAccount, UserSettingsManager
from ...domain.tooling import ToolEnvironmentService
from ...domain.tooling.models import RegisteredTool, ToolEnvironmentDefinition
from ..dialogs import (
    ProjectSettingsDialog,
    ToolEnvironmentManagerDialog,
    ToolRegistryDialog,
    UserSettingsDialog,
)
from ..style import apply_base_style


@dataclass(frozen=True)
class NodeCatalogEntry:
    """コンテンツブラウザに表示するノード情報。"""

    node_type: str
    title: str
    subtitle: str
    genre: str
    keywords: Tuple[str, ...] = ()

    def searchable_text(self) -> str:
        parts = [self.title, self.subtitle, self.node_type, *self.keywords]
        return "\n".join(part.lower() for part in parts if part)


@dataclass(frozen=True)
class BrowserLayoutProfile:
    """コンテンツブラウザのレイアウト設定。"""

    min_width: int
    view_mode: QListView.ViewMode
    flow: QListView.Flow
    wrapping: bool
    compact: bool
    grid_columns: int
    section_spacing: int
    card_padding: Tuple[int, int, int, int]


class NodeContentBrowser(QWidget):
    """ノード追加と検索をまとめたコンテンツブラウザ風ウィジェット。"""

    node_type_requested = Signal(str)
    search_submitted = Signal(str)
    back_requested = Signal()
    tool_environment_edit_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._search_line: QLineEdit = QLineEdit(self)
        self._genre_combo: Optional[QComboBox] = None
        self._available_list: QListWidget = QListWidget(self)
        self._catalog_entries: List[NodeCatalogEntry] = []
        self._icon_size_slider: QSlider = QSlider(Qt.Horizontal, self)
        self._icon_size_spin: QSpinBox = QSpinBox(self)
        self._icon_size_levels: Dict[int, int] = {
            1: 24,
            2: 32,
            3: 40,
            4: 48,
            5: 64,
            6: 80,
        }
        self._icon_size_default_level: int = 3
        self._icon_size_level: int = self._icon_size_default_level
        self._icon_size: int = self._icon_size_from_level(self._icon_size_level)
        self._compact_mode: bool = False
        self._icon_control_container: Optional[QWidget] = None
        self._menu_bar: Optional[QMenuBar] = None
        self._outer_layout: Optional[QVBoxLayout] = None
        self._card_frame: Optional[QFrame] = None
        self._card_layout: Optional[QVBoxLayout] = None
        self._control_header: Optional[QWidget] = None
        self._control_header_layout: Optional[QBoxLayout] = None
        self._control_header_spacer: Optional[QSpacerItem] = None
        self._result_summary_label: Optional[QLabel] = None
        self._layout_profiles: List[BrowserLayoutProfile] = [
            BrowserLayoutProfile(
                min_width=1080,
                view_mode=QListWidget.IconMode,
                flow=QListView.LeftToRight,
                wrapping=True,
                compact=False,
                grid_columns=5,
                section_spacing=16,
                card_padding=(24, 24, 24, 24),
            ),
            BrowserLayoutProfile(
                min_width=860,
                view_mode=QListWidget.IconMode,
                flow=QListView.LeftToRight,
                wrapping=True,
                compact=False,
                grid_columns=4,
                section_spacing=16,
                card_padding=(20, 20, 20, 20),
            ),
            BrowserLayoutProfile(
                min_width=660,
                view_mode=QListWidget.IconMode,
                flow=QListView.LeftToRight,
                wrapping=True,
                compact=False,
                grid_columns=3,
                section_spacing=14,
                card_padding=(20, 20, 20, 20),
            ),
            BrowserLayoutProfile(
                min_width=520,
                view_mode=QListWidget.IconMode,
                flow=QListView.LeftToRight,
                wrapping=True,
                compact=False,
                grid_columns=2,
                section_spacing=12,
                card_padding=(18, 18, 18, 18),
            ),
            BrowserLayoutProfile(
                min_width=0,
                view_mode=QListWidget.ListMode,
                flow=QListView.TopToBottom,
                wrapping=False,
                compact=True,
                grid_columns=1,
                section_spacing=10,
                card_padding=(16, 16, 16, 16),
            ),
        ]
        self._current_profile: BrowserLayoutProfile = self._layout_profiles[-1]
        self._total_entry_count: int = 0
        self._visible_entry_count: int = 0
        self._current_genre: Optional[str] = None

        self._setup_ui()
        self._connect_signals()
        self._update_layout_for_size(self.size())

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: D401
        """ウィジェットのリサイズイベントを処理する。"""

        super().resizeEvent(event)
        if event is not None:
            self._update_layout_for_size(event.size())

    def _setup_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(12)
        self._outer_layout = outer_layout

        card = QFrame(self)
        card.setObjectName("panelCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(12)
        self._card_frame = card
        self._card_layout = card_layout

        menu_bar = self._create_menu_bar(card)
        if menu_bar is not None:
            card_layout.addWidget(menu_bar)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        title_label = QLabel("コンテンツブラウザ", card)
        title_label.setObjectName("panelTitle")
        header_layout.addWidget(title_label)
        header_layout.addStretch(1)

        back_button = QPushButton("スタート画面に戻る", card)
        back_button.clicked.connect(self.back_requested.emit)
        header_layout.addWidget(back_button)

        card_layout.addLayout(header_layout)

        search_layout = QHBoxLayout()
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(8)

        self._search_line.setPlaceholderText("ノードを検索")
        self._search_line.setClearButtonEnabled(True)
        search_layout.addWidget(self._search_line, 1)

        genre_label = QLabel("ジャンル", card)
        genre_label.setProperty("hint", "secondary")
        search_layout.addWidget(genre_label)

        genre_combo = QComboBox(card)
        genre_combo.setObjectName("genreFilterCombo")
        genre_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        genre_combo.setMinimumContentsLength(6)
        genre_combo.addItem("すべて", None)
        self._genre_combo = genre_combo
        search_layout.addWidget(genre_combo)

        card_layout.addLayout(search_layout)

        self._configure_list_widget(self._available_list)

        icon_control = self._create_icon_size_control(card)
        summary_widget = self._create_result_summary(card)
        header_container = QWidget(card)
        header_container_layout = QHBoxLayout(header_container)
        header_container_layout.setContentsMargins(0, 0, 0, 0)
        header_container_layout.setSpacing(8)
        header_container_layout.addWidget(summary_widget)
        spacer = QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum)
        header_container_layout.addItem(spacer)
        header_container_layout.addWidget(icon_control)
        self._control_header = header_container
        self._control_header_layout = header_container_layout
        self._control_header_spacer = spacer

        card_layout.addWidget(
            self._build_section(
                "追加可能ノード",
                self._available_list,
                header_widget=header_container,
            ),
            1,
        )

        outer_layout.addWidget(card, 1)

    def _create_menu_bar(self, parent: QWidget) -> Optional[QMenuBar]:
        menu_bar = QMenuBar(parent)
        menu_bar.setNativeMenuBar(False)
        environment_menu = menu_bar.addMenu("環境")
        edit_action = environment_menu.addAction("ツール環境の編集...")
        edit_action.triggered.connect(self.tool_environment_edit_requested.emit)
        self._menu_bar = menu_bar
        return menu_bar

    def _configure_list_widget(self, widget: QListWidget) -> None:
        widget.setObjectName("contentList")
        widget.setViewMode(QListWidget.IconMode)
        widget.setMovement(QListWidget.Static)
        widget.setResizeMode(QListWidget.Adjust)
        widget.setWrapping(True)
        widget.setWordWrap(True)
        widget.setTextElideMode(Qt.TextElideMode.ElideNone)
        widget.setIconSize(
            QSize(self._current_icon_size_value(), self._current_icon_size_value())
        )
        widget.setSpacing(16)
        widget.setSelectionMode(QAbstractItemView.SingleSelection)
        widget.setUniformItemSizes(False)
        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._apply_icon_size()

    def _build_section(
        self,
        title: str,
        widget: QListWidget,
        header_widget: Optional[QWidget] = None,
    ) -> QWidget:
        frame = QFrame(self)
        frame.setObjectName("inspectorSection")
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(16, 16, 16, 16)
        frame_layout.setSpacing(self._current_profile.section_spacing)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        label = QLabel(title, frame)
        label.setObjectName("panelTitle")
        header_layout.addWidget(label)

        if header_widget is not None:
            header_layout.addStretch(1)
            header_layout.addWidget(header_widget)

        frame_layout.addLayout(header_layout)
        frame_layout.addWidget(widget, 1)

        return frame

    def _create_icon_size_control(self, parent: QWidget) -> QWidget:
        container = QWidget(parent)
        self._icon_control_container = container
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        size_label = QLabel("アイコンサイズ", container)
        size_label.setProperty("hint", "secondary")

        self._icon_size_slider.setParent(container)
        self._icon_size_slider.setRange(1, len(self._icon_size_levels))
        self._icon_size_slider.setSingleStep(1)
        self._icon_size_slider.setPageStep(1)
        self._icon_size_slider.setValue(self._icon_size_level)
        self._icon_size_slider.setTickInterval(1)
        self._icon_size_slider.setTickPosition(QSlider.TicksBelow)
        self._icon_size_slider.setTracking(True)

        self._icon_size_spin.setParent(container)
        self._icon_size_spin.setRange(1, len(self._icon_size_levels))
        self._icon_size_spin.setSingleStep(1)
        self._icon_size_spin.setValue(self._icon_size_level)
        self._icon_size_spin.setSuffix(" 段階")
        self._icon_size_spin.setFixedWidth(84)

        layout.addWidget(size_label)
        layout.addWidget(self._icon_size_slider, 1)
        layout.addWidget(self._icon_size_spin)

        return container

    def _create_result_summary(self, parent: QWidget) -> QWidget:
        container = QWidget(parent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        caption = QLabel("表示件数", container)
        caption.setProperty("hint", "secondary")

        summary = QLabel("0 件", container)
        summary.setObjectName("contentSummaryLabel")
        summary.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._result_summary_label = summary

        layout.addWidget(caption)
        layout.addWidget(summary)

        return container

    def _connect_signals(self) -> None:
        self._search_line.textChanged.connect(self._apply_filter)
        self._search_line.returnPressed.connect(self._on_search_submitted)
        self._available_list.itemActivated.connect(self._on_available_item_activated)
        self._icon_size_slider.valueChanged.connect(self._on_icon_size_changed)
        self._icon_size_spin.valueChanged[int].connect(self._on_icon_size_changed)
        if self._genre_combo is not None:
            self._genre_combo.currentIndexChanged.connect(self._on_genre_changed)

    def set_available_nodes(self, entries: List[Dict[str, str]]) -> None:
        catalog_entries: List[NodeCatalogEntry] = []
        for entry in entries:
            node_type = str(entry.get("type", "") or "")
            title = str(entry.get("title", "") or "")
            subtitle = str(entry.get("subtitle", "") or "")
            genre_value = entry.get("genre")
            genre = str(genre_value).strip() if isinstance(genre_value, str) else ""
            if not genre:
                genre = self._guess_genre(node_type)
            keywords: Tuple[str, ...] = ()
            raw_keywords = entry.get("keywords")
            if isinstance(raw_keywords, str):
                keywords = tuple(
                    part.strip()
                    for part in raw_keywords.split()
                    if part and part.strip()
                )
            elif isinstance(raw_keywords, IterableABC):
                keywords = tuple(
                    str(part).strip()
                    for part in raw_keywords
                    if part and str(part).strip()
                )
            catalog_entries.append(
                NodeCatalogEntry(
                    node_type=node_type,
                    title=title,
                    subtitle=subtitle,
                    genre=genre,
                    keywords=keywords,
                )
            )

        self._catalog_entries = catalog_entries
        self._total_entry_count = len(catalog_entries)
        self._available_list.clear()

        alignment = Qt.AlignLeft | Qt.AlignTop
        item_size = self._list_item_size_hint()
        for entry in catalog_entries:
            item = QListWidgetItem(self._format_entry_text(entry))
            item.setData(Qt.UserRole, entry.node_type)
            item.setData(Qt.UserRole + 1, entry.searchable_text())
            item.setData(Qt.UserRole + 2, entry.genre)
            item.setToolTip(entry.node_type)
            item.setTextAlignment(alignment)
            item.setSizeHint(item_size)
            self._available_list.addItem(item)

        self._populate_genre_options()
        self._apply_icon_size()
        self._update_item_texts()
        self._apply_filter()

    def _populate_genre_options(self) -> None:
        if self._genre_combo is None:
            return
        previous = self._current_genre
        genres = sorted({entry.genre for entry in self._catalog_entries if entry.genre})
        self._genre_combo.blockSignals(True)
        self._genre_combo.clear()
        self._genre_combo.addItem("すべて", None)
        target_index = 0
        for genre in genres:
            self._genre_combo.addItem(genre, genre)
            if previous and genre == previous:
                target_index = self._genre_combo.count() - 1
        if target_index >= self._genre_combo.count():
            target_index = 0
        if target_index == 0:
            previous = None
        self._genre_combo.setCurrentIndex(target_index)
        self._genre_combo.blockSignals(False)
        self._current_genre = previous
        tooltip_lines = ["ジャンルで一覧を絞り込みます。"]
        if genres:
            tooltip_lines.append("登録ジャンル: " + ", ".join(genres))
        self._genre_combo.setToolTip("\n".join(tooltip_lines))

    def _guess_genre(self, node_type: str) -> str:
        normalized = node_type.strip()
        if normalized.startswith("tool-environment:") or normalized.startswith(
            "sotugyo.tooling"
        ):
            return "ツール環境"
        if normalized.startswith("sotugyo.demo."):
            return "ワークフロー"
        if normalized.startswith("sotugyo.memo."):
            return "メモ"
        return "その他"

    def _on_genre_changed(self, index: int) -> None:
        if self._genre_combo is None:
            return
        data = self._genre_combo.itemData(index)
        self._current_genre = data if isinstance(data, str) and data else None
        self._apply_filter()

    def _genre_total_count(self, genre: Optional[str]) -> int:
        if genre is None:
            return self._total_entry_count
        return sum(1 for entry in self._catalog_entries if entry.genre == genre)

    def focus_search(self) -> None:
        self._search_line.setFocus()
        self._search_line.selectAll()

    def current_search_text(self) -> str:
        return self._search_line.text()

    def first_visible_available_type(self) -> Optional[str]:
        for index in range(self._available_list.count()):
            item = self._available_list.item(index)
            if item is not None and not item.isHidden():
                data = item.data(Qt.UserRole)
                if isinstance(data, str):
                    return data
        return None

    def _apply_filter(self) -> None:
        keyword = self._search_line.text().strip().lower()
        selected_genre = self._current_genre
        visible_count = 0
        for index in range(self._available_list.count()):
            item = self._available_list.item(index)
            if item is None:
                continue
            entry = self._catalog_entries[index] if index < len(self._catalog_entries) else None
            search_text = item.data(Qt.UserRole + 1)
            if not isinstance(search_text, str):
                search_text = entry.searchable_text() if entry else item.text().lower()
            matches_keyword = not keyword or keyword in search_text
            matches_genre = True
            if selected_genre:
                genre_value = item.data(Qt.UserRole + 2)
                if not isinstance(genre_value, str):
                    genre_value = entry.genre if entry else ""
                matches_genre = genre_value == selected_genre
            is_hidden = not (matches_keyword and matches_genre)
            item.setHidden(is_hidden)
            if not is_hidden:
                visible_count += 1
        self._visible_entry_count = visible_count
        self._update_summary_label(visible_count)

    def _on_search_submitted(self) -> None:
        self.search_submitted.emit(self._search_line.text())

    def _on_available_item_activated(self, item: QListWidgetItem) -> None:
        if item is None:
            return
        node_type = item.data(Qt.UserRole)
        if isinstance(node_type, str):
            self.node_type_requested.emit(node_type)

    def _on_icon_size_changed(self, value: int) -> None:
        clamped = max(self._icon_size_spin.minimum(), min(value, self._icon_size_spin.maximum()))
        if clamped == self._icon_size_level:
            return
        self._icon_size_level = clamped
        self._icon_size = self._icon_size_from_level(self._icon_size_level)
        if self._icon_size_slider.value() != clamped:
            self._icon_size_slider.blockSignals(True)
            self._icon_size_slider.setValue(clamped)
            self._icon_size_slider.blockSignals(False)
        if self._icon_size_spin.value() != clamped:
            self._icon_size_spin.blockSignals(True)
            self._icon_size_spin.setValue(clamped)
            self._icon_size_spin.blockSignals(False)
        self._apply_icon_size()

    def _apply_icon_size(self) -> None:
        icon_size_value = self._current_icon_size_value()
        icon_size = QSize(icon_size_value, icon_size_value)
        self._available_list.setIconSize(icon_size)
        self._refresh_item_sizes()
        tooltip = (
            f"表示サイズ: {icon_size_value}px"
            f" / {self._icon_size_level} 段階 ({len(self._icon_size_levels)}段階中)"
        )
        self._icon_size_slider.setToolTip(tooltip)
        self._icon_size_spin.setToolTip(tooltip)
        if self._result_summary_label is not None and self._visible_entry_count:
            self._update_summary_label()

    def _icon_size_from_level(self, level: int) -> int:
        return self._icon_size_levels.get(
            level,
            self._icon_size_levels.get(self._icon_size_default_level, 32),
        )

    def _current_icon_size_value(self) -> int:
        """現在のアイコン表示サイズ（ピクセル）を返す。"""

        return self._icon_size

    def _list_item_size_hint(self) -> QSize:
        font: QFontMetrics = self._available_list.fontMetrics()
        icon_size = self._current_icon_size_value()
        viewport = self._available_list.viewport()
        viewport_width = viewport.width() if viewport is not None else 0
        if viewport_width <= 0:
            viewport_width = max(self.width() - 40, icon_size + 64)

        line_spacing = font.lineSpacing()
        leading = font.leading()
        profile = self._current_profile

        if profile.compact:
            vertical_padding = max(10, leading + 6)
            text_lines = 2
            text_height = line_spacing * text_lines
            height = max(icon_size + vertical_padding, text_height + vertical_padding)
            width = max(220, viewport_width)
            return QSize(width, height)

        horizontal_gap = self._available_list.spacing()
        columns = max(1, profile.grid_columns)
        if viewport_width > 0 and profile.view_mode == QListWidget.IconMode:
            total_spacing = horizontal_gap * max(columns - 1, 0)
            usable_width = max(icon_size + 64, viewport_width - total_spacing)
            width = max(icon_size + 72, usable_width // columns)
        else:
            width = max(icon_size + 72, viewport_width)

        title_width = font.horizontalAdvance("M" * 18)
        width = max(width, title_width + icon_size // 2)

        vertical_padding = max(18, leading + 14)
        text_lines = 2
        text_height = line_spacing * text_lines
        height = max(icon_size + vertical_padding, text_height + vertical_padding)
        return QSize(width, height)

    def _update_layout_for_size(self, size: QSize) -> None:
        """ウィジェット幅に応じてレイアウトモードを切り替える。"""

        width = size.width() if size is not None else self.width()
        profile = self._select_layout_profile(width)
        if profile != self._current_profile:
            self._apply_profile(profile)

        self._apply_icon_size()
        self._refresh_item_sizes()
        self._update_item_texts()
        self._adjust_control_header(width)

    def _format_entry_text(self, entry: NodeCatalogEntry) -> str:
        """エントリー情報を表示用文字列に整形する。"""

        title = entry.title.strip()
        subtitle = entry.subtitle.strip()
        node_type = entry.node_type.strip()

        if self._compact_mode:
            parts: List[str] = []
            if title:
                parts.append(title)
            if subtitle:
                parts.append(subtitle)
            if not parts and node_type:
                parts.append(node_type)
            return " – ".join(parts) if len(parts) > 1 else (parts[0] if parts else "")

        lines = [text for text in (title, subtitle) if text]
        if not lines and node_type:
            lines.append(node_type)
        return "\n".join(lines)

    def _update_item_texts(self) -> None:
        """現在表示中の項目テキストを再整形する。"""

        for index, entry in enumerate(self._catalog_entries):
            item = self._available_list.item(index)
            if item is None:
                continue
            item.setText(self._format_entry_text(entry))
        self._refresh_item_sizes()

    def _refresh_item_sizes(self) -> None:
        """リスト項目のサイズヒントを再計算して反映する。"""

        item_size = self._list_item_size_hint()
        for index in range(self._available_list.count()):
            item = self._available_list.item(index)
            if item is not None:
                item.setSizeHint(item_size)
        self._available_list.updateGeometry()
        self._available_list.scheduleDelayedItemsLayout()
        viewport = self._available_list.viewport()
        if viewport is not None:
            viewport.update()
        if self._available_list.viewMode() == QListWidget.IconMode:
            self._available_list.setGridSize(item_size)

    def _select_layout_profile(self, width: int) -> BrowserLayoutProfile:
        for profile in self._layout_profiles:
            if width >= profile.min_width:
                return profile
        return self._layout_profiles[-1]

    def _apply_profile(self, profile: BrowserLayoutProfile) -> None:
        self._current_profile = profile
        self._compact_mode = profile.compact

        self._available_list.setViewMode(profile.view_mode)
        self._available_list.setFlow(profile.flow)
        self._available_list.setWrapping(profile.wrapping)
        self._available_list.setSpacing(12 if profile.compact else 16)
        self._available_list.setWordWrap(not profile.compact)

        if self._icon_control_container is not None:
            self._icon_control_container.setVisible(profile.view_mode == QListWidget.IconMode)
        if self._control_header is not None:
            self._control_header.setVisible(True)

        if self._card_layout is not None:
            left, top, right, bottom = profile.card_padding
            self._card_layout.setContentsMargins(left, top, right, bottom)
            self._card_layout.setSpacing(profile.section_spacing)
        if self._outer_layout is not None:
            self._outer_layout.setSpacing(profile.section_spacing)

        self._refresh_item_sizes()
        self._update_summary_label()
        self._adjust_control_header(self.width())

    def _adjust_control_header(self, width: int) -> None:
        if self._control_header_layout is None:
            return
        is_vertical = width < 720 or self._compact_mode
        target_direction = (
            QBoxLayout.TopToBottom if is_vertical else QBoxLayout.LeftToRight
        )
        if self._control_header_layout.direction() != target_direction:
            self._control_header_layout.setDirection(target_direction)
        if self._control_header_spacer is not None:
            if is_vertical:
                self._control_header_spacer.changeSize(
                    0,
                    0,
                    QSizePolicy.Minimum,
                    QSizePolicy.Minimum,
                )
            else:
                self._control_header_spacer.changeSize(
                    0,
                    0,
                    QSizePolicy.Expanding,
                    QSizePolicy.Minimum,
                )
        if self._icon_control_container is not None:
            alignment = Qt.AlignLeft if is_vertical else Qt.AlignRight
            self._control_header_layout.setAlignment(
                self._icon_control_container,
                alignment,
            )
        if self._control_header_layout.spacing() != (4 if is_vertical else 8):
            self._control_header_layout.setSpacing(4 if is_vertical else 8)
        if self._control_header is not None:
            self._control_header.updateGeometry()
        self._control_header_layout.invalidate()

    def _update_summary_label(self, visible_count: Optional[int] = None) -> None:
        if self._result_summary_label is None:
            return
        if visible_count is None:
            visible_count = sum(
                0
                if item is None or item.isHidden()
                else 1
                for item in (
                    self._available_list.item(i)
                    for i in range(self._available_list.count())
                )
            )
        self._visible_entry_count = visible_count
        if self._current_genre:
            total = self._genre_total_count(self._current_genre)
            text = f"{visible_count} 件 / {total} 件（ジャンル: {self._current_genre}）"
        else:
            text = f"{visible_count} 件 / 全 {self._total_entry_count} 件"
        self._result_summary_label.setText(text)

class NodeEditorWindow(QMainWindow):
    """NodeGraphQt を用いたノード編集画面。"""

    WINDOW_TITLE = "ノード編集テスト"
    return_to_start_requested = Signal()

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        project_service: Optional[ProjectService] = None,
        user_manager: Optional[UserSettingsManager] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.WINDOW_TITLE)
        self._base_window_title = self.windowTitle()
        self.resize(960, 600)
        self.setWindowState(self.windowState() | Qt.WindowFullScreen)

        self._graph = NodeGraph()
        self._graph.register_node(TaskNode)
        self._graph.register_node(ReviewNode)
        self._graph.register_node(MemoNode)
        self._graph.register_node(ToolEnvironmentNode)

        self._graph_widget = self._graph.widget
        self._graph_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._node_spawn_offset = 0
        self._task_count = 0
        self._review_count = 0
        self._memo_count = 0
        self._current_node = None
        self._known_nodes: List = []
        self._node_metadata: Dict[object, Dict[str, str]] = {}
        self._is_modified = False
        self._current_project_root: Optional[Path] = None
        self._current_project_settings: Optional[ProjectSettings] = None
        self._current_user: Optional[UserAccount] = None
        self._current_user_password: Optional[str] = None
        self._project_service = project_service or ProjectService()
        self._user_manager = user_manager or UserSettingsManager()
        self._tool_service = ToolEnvironmentService()
        self._registered_tools: Dict[str, RegisteredTool] = {}
        self._tool_environments: Dict[str, ToolEnvironmentDefinition] = {}

        self._side_tabs: Optional[QTabWidget] = None
        self._detail_name_label: Optional[QLabel] = None
        self._detail_type_label: Optional[QLabel] = None
        self._detail_position_label: Optional[QLabel] = None
        self._detail_uuid_label: Optional[QLabel] = None
        self._rename_input: Optional[QLineEdit] = None
        self._rename_button: Optional[QPushButton] = None
        self._memo_text_edit: Optional[QTextEdit] = None
        self._memo_font_spin: Optional[QSpinBox] = None
        self._memo_controls_active = False
        self._content_browser: Optional[NodeContentBrowser] = None
        self._shortcuts: List[QShortcut] = []
        self._node_type_creators = {
            "sotugyo.demo.TaskNode": self._create_task_node,
            "sotugyo.demo.ReviewNode": self._create_review_node,
            MemoNode.node_type_identifier(): self._create_memo_node,
        }
        self._inspector_dock: Optional[QDockWidget] = None
        self._content_dock: Optional[QDockWidget] = None

        self._init_ui()
        self._create_menus()
        self._setup_graph_signals()
        self._setup_context_menu()
        self._setup_shortcuts()
        self._refresh_tool_configuration()
        self._initialize_content_browser()
        self._update_selected_node_info()
        self._refresh_node_catalog()
        self._set_modified(False)
        apply_base_style(self)

    def showEvent(self, event: QShowEvent) -> None:
        """ウィンドウ表示時に全画面状態を維持する。"""

        super().showEvent(event)
        if not self.isFullScreen():
            self.setWindowState(self.windowState() | Qt.WindowFullScreen)

    # ------------------------------------------------------------------
    # UI 初期化
    # ------------------------------------------------------------------
    def _init_ui(self) -> None:
        central = QWidget(self)
        central.setObjectName("graphCentralContainer")
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(16, 16, 16, 16)
        central_layout.setSpacing(16)
        central_layout.addWidget(self._graph_widget)
        self.setCentralWidget(central)

        self._side_tabs = QTabWidget(self)
        self._side_tabs.setMinimumWidth(260)
        self._side_tabs.addTab(self._build_detail_tab(), "ノード詳細")
        self._side_tabs.addTab(self._build_operation_tab(), "ノード操作")

        inspector_dock = QDockWidget("インスペクタ", self)
        inspector_dock.setObjectName("InspectorDock")
        inspector_dock.setAllowedAreas(
            Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea
        )
        inspector_dock.setFeatures(
            QDockWidget.DockWidgetMovable
            | QDockWidget.DockWidgetFloatable
            | QDockWidget.DockWidgetClosable
        )
        inspector_container = QWidget(inspector_dock)
        inspector_container.setObjectName("dockContentContainer")
        inspector_layout = QVBoxLayout(inspector_container)
        inspector_layout.setContentsMargins(12, 12, 12, 12)
        inspector_layout.setSpacing(12)
        inspector_layout.addWidget(self._side_tabs)
        inspector_dock.setWidget(inspector_container)
        self.addDockWidget(Qt.RightDockWidgetArea, inspector_dock)
        self._inspector_dock = inspector_dock

        self._content_browser = NodeContentBrowser(self)
        self._content_browser.node_type_requested.connect(self._spawn_node_by_type)
        self._content_browser.search_submitted.connect(self._handle_content_browser_search)
        self._content_browser.back_requested.connect(self._return_to_start)
        self._content_browser.tool_environment_edit_requested.connect(
            self._open_tool_environment_manager
        )
        self._content_browser.setMinimumHeight(160)

        content_dock = QDockWidget("コンテンツブラウザ", self)
        content_dock.setObjectName("ContentBrowserDock")
        content_dock.setAllowedAreas(Qt.TopDockWidgetArea | Qt.BottomDockWidgetArea)
        content_dock.setFeatures(
            QDockWidget.DockWidgetMovable
            | QDockWidget.DockWidgetFloatable
            | QDockWidget.DockWidgetClosable
        )
        content_container = QWidget(content_dock)
        content_container.setObjectName("dockContentContainer")
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(12, 12, 12, 12)
        content_layout.setSpacing(12)
        content_layout.addWidget(self._content_browser)
        content_dock.setWidget(content_container)
        self.addDockWidget(Qt.BottomDockWidgetArea, content_dock)
        self._content_dock = content_dock

        self.resizeDocks([content_dock], [220], Qt.Vertical)
        self.resizeDocks([inspector_dock], [320], Qt.Horizontal)

    def _create_menus(self) -> None:
        menubar = self.menuBar()

        file_menu = menubar.addMenu("File")

        save_action = QAction("上書き保存", self)
        save_action.triggered.connect(self._file_save)
        save_action.setShortcut(QKeySequence.Save)
        file_menu.addAction(save_action)

        export_selected_action = QAction("選択ノードを保存...", self)
        export_selected_action.triggered.connect(self._file_export_selected_nodes)
        file_menu.addAction(export_selected_action)

        import_action = QAction("アセットをインポート...", self)
        import_action.triggered.connect(self._file_import)
        import_action.setShortcut(QKeySequence.Open)
        file_menu.addAction(import_action)

        file_menu.addSeparator()

        return_action = QAction("スタート画面に戻る", self)
        return_action.triggered.connect(self._return_to_start)
        file_menu.addAction(return_action)

        project_menu = menubar.addMenu("ProjectSetting")
        project_settings_action = QAction("プロジェクト設定...", self)
        project_settings_action.triggered.connect(self._open_project_settings)
        project_menu.addAction(project_settings_action)

        user_menu = menubar.addMenu("UserSetting")
        user_settings_action = QAction("ユーザー設定...", self)
        user_settings_action.triggered.connect(self._open_user_settings)
        user_menu.addAction(user_settings_action)

        tools_menu = menubar.addMenu("Tools")
        tool_registry_action = QAction("環境設定...", self)
        tool_registry_action.triggered.connect(self._open_tool_settings)
        tools_menu.addAction(tool_registry_action)
        environment_action = QAction("ツール環境の編集...", self)
        environment_action.triggered.connect(self._open_tool_environment_manager)
        tools_menu.addAction(environment_action)

        view_menu = menubar.addMenu("View")
        if self._inspector_dock is not None:
            view_menu.addAction(self._inspector_dock.toggleViewAction())
        if self._content_dock is not None:
            view_menu.addAction(self._content_dock.toggleViewAction())

    def _build_detail_tab(self) -> QWidget:
        widget = QFrame(self)
        widget.setObjectName("inspectorSection")
        layout = QFormLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        self._detail_name_label = QLabel("-", widget)
        self._detail_type_label = QLabel("-", widget)
        self._detail_uuid_label = QLabel("-", widget)
        self._detail_position_label = QLabel("-", widget)

        layout.addRow("名前", self._detail_name_label)
        layout.addRow("タイプ", self._detail_type_label)
        layout.addRow("UUID", self._detail_uuid_label)
        layout.addRow("位置", self._detail_position_label)

        return widget

    def _build_operation_tab(self) -> QWidget:
        widget = QFrame(self)
        widget.setObjectName("inspectorSection")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        rename_label = QLabel("名前の変更", widget)
        rename_label.setObjectName("panelTitle")
        self._rename_input = QLineEdit(widget)
        self._rename_input.setPlaceholderText("ノード名を入力")

        self._rename_button = QPushButton("名前を更新", widget)
        self._rename_button.clicked.connect(self._apply_node_rename)

        layout.addWidget(rename_label)
        layout.addWidget(self._rename_input)
        layout.addWidget(self._rename_button)

        memo_label = QLabel("メモ編集", widget)
        memo_label.setObjectName("panelTitle")
        layout.addWidget(memo_label)

        self._memo_text_edit = QTextEdit(widget)
        self._memo_text_edit.setAcceptRichText(False)
        self._memo_text_edit.setPlaceholderText("メモノードの内容を入力")
        self._memo_text_edit.setMinimumHeight(140)
        self._memo_text_edit.textChanged.connect(self._handle_memo_text_changed)
        layout.addWidget(self._memo_text_edit)

        memo_font_layout = QHBoxLayout()
        memo_font_label = QLabel("文字サイズ", widget)
        self._memo_font_spin = QSpinBox(widget)
        self._memo_font_spin.setRange(MemoNode.MIN_FONT_SIZE, MemoNode.MAX_FONT_SIZE)
        self._memo_font_spin.setValue(MemoNode.DEFAULT_FONT_SIZE)
        self._memo_font_spin.valueChanged.connect(self._handle_memo_font_size_changed)
        memo_font_layout.addWidget(memo_font_label)
        memo_font_layout.addWidget(self._memo_font_spin)
        layout.addLayout(memo_font_layout)

        self._set_memo_controls_enabled(False)

        layout.addStretch(1)

        return widget

    def _open_project_settings(self) -> None:
        if self._current_project_root is None:
            self._show_info_dialog("プロジェクトが選択されていません。")
            return
        if self._current_project_settings is None:
            self._current_project_settings = self._project_service.load_settings(
                self._current_project_root
            )
        dialog = ProjectSettingsDialog(self._current_project_settings, self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        updated = dialog.settings()
        root_changed = updated.project_root != self._current_project_root
        name_changed = (
            self._current_project_settings.project_name != updated.project_name
            if self._current_project_settings
            else True
        )
        self._current_project_settings = updated
        try:
            self._project_service.save_settings(updated)
        except OSError as exc:
            self._show_error_dialog(f"設定の保存に失敗しました: {exc}")
            return
        if root_changed:
            if not self._confirm_discard_changes(
                "プロジェクトルートが変更されます。未保存の編集内容は失われます。続行しますか？"
            ):
                return
            if not self._confirm_project_change(updated.project_name):
                return
            self._current_project_root = updated.project_root
            self._load_project_graph()
        self._refresh_window_title()
        if name_changed or root_changed:
            self._notify_start_window_refresh()

    def _open_user_settings(self) -> None:
        dialog = UserSettingsDialog(self._user_manager, self)
        if dialog.exec() == QDialog.Accepted:
            if self._current_user is not None:
                refreshed = self._user_manager.get_account(self._current_user.user_id)
                if refreshed is not None:
                    self._current_user = refreshed
            self._refresh_window_title()
            self._notify_start_window_refresh()

    def _open_tool_settings(self) -> None:
        dialog = ToolRegistryDialog(self._tool_service, self)
        dialog.exec()
        if dialog.refresh_requested():
            self._refresh_tool_configuration()

    def _open_tool_environment_manager(self) -> None:
        dialog = ToolEnvironmentManagerDialog(self._tool_service, self)
        dialog.exec()
        if dialog.refresh_requested():
            self._refresh_tool_configuration()

    def _setup_graph_signals(self) -> None:
        selection_signal = getattr(self._graph, "selection_changed", None)
        if selection_signal is not None and hasattr(selection_signal, "connect"):
            selection_signal.connect(self._on_selection_changed)
        else:
            selection_signal = getattr(self._graph, "node_selection_changed", None)
            if selection_signal is not None and hasattr(selection_signal, "connect"):
                selection_signal.connect(self._on_selection_changed)

        connection_signals = [
            getattr(self._graph, "port_connected", None),
            getattr(self._graph, "port_disconnected", None),
            getattr(self._graph, "pipes_deleted", None),
        ]
        for signal in connection_signals:
            if signal is not None and hasattr(signal, "connect"):
                signal.connect(self._on_port_connection_changed)

    def _setup_context_menu(self) -> None:
        if hasattr(self._graph_widget, "setContextMenuPolicy"):
            self._graph_widget.setContextMenuPolicy(Qt.CustomContextMenu)
            self._graph_widget.customContextMenuRequested.connect(
                self._open_graph_context_menu
            )

    def _setup_shortcuts(self) -> None:
        self._shortcuts.clear()

        def register(sequence: QKeySequence | str, callback) -> None:
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.setContext(Qt.WidgetWithChildrenShortcut)
            shortcut.activated.connect(callback)
            self._shortcuts.append(shortcut)

        register("Delete", self._delete_selected_nodes)
        register("Ctrl+S", self._file_save)
        register("Ctrl+O", self._file_import)
        register("Ctrl+F", self._focus_content_browser_search)
        register("Ctrl+Shift+C", self._connect_selected_nodes)
        register("Ctrl+Shift+D", self._disconnect_selected_nodes)
        register("Ctrl+T", self._create_task_node)
        register("Ctrl+R", self._create_review_node)

    def _initialize_content_browser(self) -> None:
        if self._content_browser is None:
            return
        self._refresh_content_browser_entries()

    def _refresh_tool_configuration(self) -> None:
        try:
            tools = self._tool_service.list_tools()
        except OSError as exc:
            LOGGER.error("ツール情報の取得に失敗しました: %s", exc, exc_info=True)
            tools = []
        try:
            environments = self._tool_service.list_environments()
        except OSError as exc:
            LOGGER.error("環境情報の取得に失敗しました: %s", exc, exc_info=True)
            environments = []

        self._registered_tools = {tool.tool_id: tool for tool in tools}
        filtered_envs: Dict[str, ToolEnvironmentDefinition] = {}
        for environment in environments:
            if environment.tool_id in self._registered_tools:
                filtered_envs[environment.environment_id] = environment
            else:
                LOGGER.warning(
                    "ツール %s が存在しないため環境 %s を読み込みから除外しました。",
                    environment.tool_id,
                    environment.environment_id,
                )
        self._tool_environments = filtered_envs
        self._refresh_content_browser_entries()

    def _refresh_content_browser_entries(self) -> None:
        if self._content_browser is None:
            return
        self._content_browser.set_available_nodes(
            self._build_available_node_entries()
        )

    # ------------------------------------------------------------------
    # プロジェクトコンテキスト管理
    # ------------------------------------------------------------------
    def prepare_context(
        self,
        context: ProjectContext,
        user: UserAccount,
        password: str,
    ) -> bool:
        project_root = Path(context.root)
        settings = context.settings
        if self._current_project_root is not None and project_root != self._current_project_root:
            if not self._confirm_discard_changes(
                "未保存の変更があります。プロジェクトを切り替えますか？"
            ):
                return False
            if not self._confirm_project_change(settings.project_name):
                return False
        if self._current_user is not None and user.user_id != self._current_user.user_id:
            result = QMessageBox.warning(
                self,
                "確認",
                f"ユーザーを「{user.display_name}」に切り替えます。続行しますか？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if result != QMessageBox.StandardButton.Yes:
                return False

        refreshed = self._user_manager.get_account(user.user_id)
        if refreshed is not None:
            user = refreshed

        self._current_project_root = project_root
        self._current_project_settings = settings
        self._current_user = user
        self._current_user_password = password

        self._project_service.register_project(context.record, set_last=True)
        self._project_service.ensure_structure(project_root)

        self._refresh_window_title()
        self._load_project_graph()

        report = self._project_service.validate_structure(project_root)
        if not report.is_valid:
            QMessageBox.warning(
                self,
                "警告",
                "既定のプロジェクト構成に不足があります。\n" + report.summary(),
            )

        self._notify_start_window_refresh()
        return True

    def _build_available_node_entries(self) -> List[Dict[str, str]]:
        entries: List[Dict[str, str]] = [
            {
                "type": "sotugyo.demo.TaskNode",
                "title": TaskNode.NODE_NAME,
                "subtitle": "工程を構成するタスクノード",
                "genre": "ワークフロー",
                "keywords": ["task", "workflow", "工程"],
            },
            {
                "type": "sotugyo.demo.ReviewNode",
                "title": ReviewNode.NODE_NAME,
                "subtitle": "成果物を検証するレビューノード",
                "genre": "ワークフロー",
                "keywords": ["review", "チェック", "検証"],
            },
            {
                "type": MemoNode.node_type_identifier(),
                "title": MemoNode.NODE_NAME,
                "subtitle": "ノードエディタ上で自由に記述できるメモ",
                "genre": "メモ",
                "keywords": ["note", "メモ", "記録"],
            },
        ]

        if self._tool_environments:
            for environment in sorted(
                self._tool_environments.values(), key=lambda item: item.name
            ):
                tool = self._registered_tools.get(environment.tool_id)
                if tool is not None:
                    subtitle_parts = [tool.display_name]
                    if environment.version_label:
                        subtitle_parts.append(environment.version_label)
                    subtitle = " / ".join(subtitle_parts)
                else:
                    subtitle = "参照先ツールが見つかりません"
                entries.append(
                    {
                        "type": f"tool-environment:{environment.environment_id}",
                        "title": environment.name,
                        "subtitle": subtitle,
                        "genre": "ツール環境",
                        "keywords": [
                            environment.environment_id,
                            tool.display_name if tool is not None else "",
                        ],
                    }
                )
        return entries

    def _open_graph_context_menu(self, position: QPoint) -> None:
        menu = QMenu(self)

        add_task_action = menu.addAction("タスクノードを追加")
        add_task_action.triggered.connect(self._create_task_node)

        add_review_action = menu.addAction("レビューノードを追加")
        add_review_action.triggered.connect(self._create_review_node)

        add_memo_action = menu.addAction("メモノードを追加")
        add_memo_action.triggered.connect(self._create_memo_node)

        menu.addSeparator()

        delete_action = menu.addAction("選択ノードを削除")
        delete_action.triggered.connect(self._delete_selected_nodes)

        connect_action = menu.addAction("選択ノードを接続")
        connect_action.triggered.connect(self._connect_selected_nodes)

        disconnect_action = menu.addAction("選択ノードを切断")
        disconnect_action.triggered.connect(self._disconnect_selected_nodes)

        menu.addSeparator()

        search_action = menu.addAction("ノード検索を開く")
        search_action.triggered.connect(self._focus_content_browser_search)

        selected_nodes = self._graph.selected_nodes()
        delete_action.setEnabled(bool(selected_nodes))
        connect_action.setEnabled(len(selected_nodes) == 2)
        disconnect_action.setEnabled(len(selected_nodes) == 2)

        global_pos = self._graph_widget.mapToGlobal(position)
        menu.exec(global_pos)

    def _focus_content_browser_search(self) -> None:
        if self._content_browser is not None:
            self._content_browser.focus_search()

    def _handle_content_browser_search(self, keyword: str) -> None:
        if self._content_browser is None:
            return
        keyword = keyword.strip()
        if not keyword:
            self._show_info_dialog("検索キーワードを入力してください。")
            return

        if self._search_nodes(keyword, show_dialog=False) is not None:
            return

        available_type = self._content_browser.first_visible_available_type()
        if available_type is not None:
            self._spawn_node_by_type(available_type)
            return

        self._show_info_dialog(f"「{keyword}」に一致するノードが見つかりません。")

    def _spawn_node_by_type(self, node_type: str) -> None:
        if node_type.startswith("tool-environment:"):
            environment_id = node_type.split(":", 1)[1]
            self._create_tool_environment_node(environment_id)
            return
        creator = self._node_type_creators.get(node_type)
        if creator is not None:
            creator()
            return
        display_name = self._derive_display_name(node_type)
        self._create_node(node_type, display_name)

    def _derive_display_name(self, node_type: str) -> str:
        base_name = node_type.split(".")[-1] if node_type else "ノード"
        return f"{base_name} {self._node_spawn_offset + 1}"

    # ------------------------------------------------------------------
    # ノード生成・削除
    # ------------------------------------------------------------------
    def _ensure_node_metadata(
        self,
        node,
        *,
        uuid_value: Optional[str] = None,
        assigned_at: Optional[str] = None,
    ) -> Tuple[str, str, bool]:
        metadata = self._node_metadata.get(node)
        existing_uuid = metadata.get("uuid") if metadata else None
        existing_assigned_at = metadata.get("uuid_assigned_at") if metadata else None

        provided_uuid = uuid_value.strip() if isinstance(uuid_value, str) else None
        uuid_was_missing = False
        if provided_uuid:
            normalized_uuid = provided_uuid
        elif existing_uuid:
            normalized_uuid = existing_uuid
        else:
            normalized_uuid = str(uuid.uuid4())
            uuid_was_missing = True

        provided_assigned_at = assigned_at.strip() if isinstance(assigned_at, str) else None
        assigned_at_was_missing = False
        if provided_assigned_at:
            normalized_assigned_at = provided_assigned_at
        elif existing_assigned_at:
            normalized_assigned_at = existing_assigned_at
        else:
            normalized_assigned_at = datetime.now().strftime("%Y-%m-%d")
            assigned_at_was_missing = True

        previous_uuid = metadata.get("uuid") if metadata else None
        previous_assigned_at = metadata.get("uuid_assigned_at") if metadata else None
        if (
            metadata is None
            or previous_uuid != normalized_uuid
            or previous_assigned_at != normalized_assigned_at
        ):
            self._node_metadata[node] = {
                "uuid": normalized_uuid,
                "uuid_assigned_at": normalized_assigned_at,
            }

        metadata_changed = uuid_was_missing or assigned_at_was_missing
        if not metadata_changed and metadata is not None:
            metadata_changed = (
                previous_uuid != normalized_uuid
                or previous_assigned_at != normalized_assigned_at
            )

        return normalized_uuid, normalized_assigned_at, metadata_changed

    def _remove_node_metadata(self, nodes: Iterable) -> None:
        for node in nodes:
            self._node_metadata.pop(node, None)

    def _create_task_node(self) -> None:
        self._task_count += 1
        self._create_node("sotugyo.demo.TaskNode", f"タスク {self._task_count}")

    def _create_review_node(self) -> None:
        self._review_count += 1
        self._create_node("sotugyo.demo.ReviewNode", f"レビュー {self._review_count}")

    def _create_memo_node(self) -> None:
        self._memo_count += 1
        self._create_node(MemoNode.node_type_identifier(), f"メモ {self._memo_count}")

    def _create_asset_node(self, asset_name: str) -> None:
        title = asset_name.strip() or "アセット"
        self._create_node("sotugyo.demo.TaskNode", f"Asset: {title}")

    def _create_tool_environment_node(self, environment_id: str) -> None:
        definition = self._tool_environments.get(environment_id)
        if definition is None:
            self._show_warning_dialog("選択された環境定義が見つかりませんでした。")
            return
        tool = self._registered_tools.get(definition.tool_id)
        if tool is None:
            self._show_warning_dialog("環境が参照するツールが登録されていません。")
            return
        node = self._create_node(
            ToolEnvironmentNode.node_type_identifier(), definition.name
        )
        if isinstance(node, ToolEnvironmentNode):
            node.configure_environment(
                environment_id=definition.environment_id,
                environment_name=definition.name,
                tool_id=tool.tool_id,
                tool_name=tool.display_name,
                version_label=definition.version_label,
                executable_path=str(tool.executable_path),
            )

    def _create_node(self, node_type: str, display_name: str):
        node = self._graph.create_node(node_type, name=display_name)
        pos_x = (self._node_spawn_offset % 4) * 220
        pos_y = (self._node_spawn_offset // 4) * 180
        node.set_pos(pos_x, pos_y)
        self._node_spawn_offset += 1
        self._known_nodes.append(node)
        self._ensure_node_metadata(node)
        self._set_modified(True)

        clear_selection = getattr(self._graph, "clear_selection", None)
        if callable(clear_selection):
            clear_selection()
        if hasattr(node, "set_selected"):
            node.set_selected(True)
        self._on_selection_changed()
        self._refresh_node_catalog()
        return node

    def _delete_selected_nodes(self) -> None:
        nodes = self._graph.selected_nodes()
        if not nodes:
            self._show_info_dialog("削除するノードを選択してください。")
            return
        self._graph.delete_nodes(nodes)
        self._known_nodes = [node for node in self._known_nodes if node not in nodes]
        self._remove_node_metadata(nodes)
        self._on_selection_changed()
        self._set_modified(True)
        self._refresh_node_catalog()

    # ------------------------------------------------------------------
    # 接続処理
    # ------------------------------------------------------------------
    def _connect_ports_compat(self, source_port: Port, target_port: Port) -> None:
        """NodeGraphQt のバージョン差異を吸収してポートを接続する。"""

        connect_ports = getattr(self._graph, "connect_ports", None)
        try:
            if callable(connect_ports):
                connect_ports(source_port, target_port)
            else:
                fallback = getattr(source_port, "connect_to", None)
                if not callable(fallback):  # pragma: no cover - 保険的分岐
                    raise AttributeError("connect_ports API が利用できません")
                fallback(target_port)
        except Exception as exc:  # pragma: no cover - Qt 依存の例外
            LOGGER.warning(
                "ポート接続に失敗しました（source=%s, target=%s）: %s",
                self._describe_port(source_port),
                self._describe_port(target_port),
                exc,
                exc_info=True,
            )
            raise

    def _disconnect_ports_compat(self, source_port: Port, target_port: Port) -> None:
        """NodeGraphQt のバージョン差異を吸収してポートを切断する。"""

        disconnect_ports = getattr(self._graph, "disconnect_ports", None)
        try:
            if callable(disconnect_ports):
                disconnect_ports(source_port, target_port)
            else:
                fallback = getattr(source_port, "disconnect_from", None)
                if not callable(fallback):  # pragma: no cover - 保険的分岐
                    raise AttributeError("disconnect_ports API が利用できません")
                fallback(target_port)
        except Exception as exc:  # pragma: no cover - Qt 依存の例外
            LOGGER.warning(
                "ポート切断に失敗しました（source=%s, target=%s）: %s",
                self._describe_port(source_port),
                self._describe_port(target_port),
                exc,
                exc_info=True,
            )
            raise

    def _connect_selected_nodes(self) -> None:
        nodes = self._graph.selected_nodes()
        if len(nodes) != 2:
            self._show_info_dialog("接続する 2 つのノードを選択してください。")
            return

        source, target = self._sort_nodes_by_position(nodes)
        source_port = self._first_output_port(source)
        target_port = self._first_input_port(target)
        if not source_port or not target_port:
            self._show_info_dialog("接続できるポートが見つかりませんでした。")
            return
        self._connect_ports_compat(source_port, target_port)
        self._set_modified(True)

    def _disconnect_selected_nodes(self) -> None:
        nodes = self._graph.selected_nodes()
        if len(nodes) != 2:
            self._show_info_dialog("切断する 2 つのノードを選択してください。")
            return

        source, target = self._sort_nodes_by_position(nodes)
        source_port = self._first_output_port(source)
        target_port = self._first_input_port(target)
        if not source_port or not target_port:
            self._show_info_dialog("切断できるポートが見つかりませんでした。")
            return

        disconnected = False
        for connected_port in list(source_port.connected_ports()):
            if connected_port.node() is target:
                self._disconnect_ports_compat(source_port, connected_port)
                disconnected = True
                self._set_modified(True)
        if not disconnected:
            self._show_info_dialog("選択されたノード間に接続が存在しません。")

    # ------------------------------------------------------------------
    # ユーティリティ
    # ------------------------------------------------------------------
    def _select_single_node(self, node) -> None:
        clear_selection = getattr(self._graph, "clear_selection", None)
        if callable(clear_selection):
            clear_selection()
        if hasattr(node, "set_selected"):
            try:
                node.set_selected(True)
            except Exception:
                pass
        view_item = getattr(node, "view", None)
        if hasattr(self._graph_widget, "centerOn") and view_item is not None:
            try:
                self._graph_widget.centerOn(view_item)
            except Exception:
                pass
        self._on_selection_changed()

    def _refresh_node_catalog(self) -> None:
        """既存ノード一覧を廃止したため更新処理は不要。"""
        return

    @staticmethod
    def _sort_nodes_by_position(nodes: Iterable) -> tuple:
        sorted_nodes = sorted(nodes, key=lambda node: node.pos()[0])
        return sorted_nodes[0], sorted_nodes[1]

    @staticmethod
    def _first_output_port(node) -> Optional[Port]:
        outputs = node.output_ports()
        return outputs[0] if outputs else None

    @staticmethod
    def _first_input_port(node) -> Optional[Port]:
        inputs = node.input_ports()
        return inputs[0] if inputs else None

    def _describe_port(self, port: Port) -> str:
        node_label = "不明ノード"
        node_getter = getattr(port, "node", None)
        node_obj = None
        if callable(node_getter):
            try:
                node_obj = node_getter()
            except Exception:  # pragma: no cover - Qt 依存の例外
                node_obj = None
        if node_obj is not None:
            node_label = self._safe_node_name(node_obj)
        port_label = None
        name_getter = getattr(port, "name", None)
        if callable(name_getter):
            try:
                port_label = str(name_getter())
            except Exception:  # pragma: no cover - Qt 依存の例外
                port_label = None
        if port_label:
            return f"{node_label}:{port_label}"
        return f"{node_label}:{repr(port)}"

    def _show_info_dialog(self, message: str) -> None:
        QMessageBox.information(self, "操作案内", message)

    def _show_warning_dialog(self, message: str) -> None:
        QMessageBox.warning(self, "警告", message)

    def _show_error_dialog(self, message: str) -> None:
        QMessageBox.critical(self, "エラー", message)

    def _search_nodes(
        self, keyword: Optional[str] = None, *, show_dialog: bool = True
    ):
        if keyword is None:
            keyword = (
                self._content_browser.current_search_text()
                if self._content_browser is not None
                else ""
            )
        keyword = keyword.strip()
        if not keyword:
            if show_dialog:
                self._show_info_dialog("検索キーワードを入力してください。")
            return None

        keyword_lower = keyword.lower()
        matched = [
            node
            for node in self._collect_all_nodes()
            if hasattr(node, "name") and keyword_lower in node.name().lower()
        ]
        if not matched:
            if show_dialog:
                self._show_info_dialog(f"「{keyword}」に一致するノードが見つかりません。")
            return None

        target = matched[0]
        self._select_single_node(target)
        return target

    def _collect_all_nodes(self) -> List:
        nodes: List = []
        all_nodes = getattr(self._graph, "all_nodes", None)
        if callable(all_nodes):
            result = all_nodes()
            if result is not None:
                nodes = list(result)
        if not nodes:
            nodes_attr = getattr(self._graph, "nodes", None)
            if callable(nodes_attr):
                result = nodes_attr()
                if result is not None:
                    nodes = list(result)
        if not nodes:
            nodes = list(self._known_nodes)
        return nodes

    def _on_selection_changed(self, *_args, **_kwargs) -> None:
        self._update_selected_node_info()

    def _on_port_connection_changed(self, *_ports, **_kwargs) -> None:
        self._set_modified(True)
        self._update_selected_node_info()

    def _update_selected_node_info(self) -> None:
        nodes = self._graph.selected_nodes()
        node = nodes[0] if nodes else None
        self._current_node = node

        if node is None:
            if self._detail_name_label:
                self._detail_name_label.setText("-")
            if self._detail_type_label:
                self._detail_type_label.setText("-")
            if self._detail_position_label:
                self._detail_position_label.setText("-")
            if self._detail_uuid_label:
                self._detail_uuid_label.setText("-")
            if self._rename_input is not None:
                self._rename_input.setText("")
                self._rename_input.setEnabled(False)
            if self._rename_button is not None:
                self._rename_button.setEnabled(False)
            self._update_memo_controls(None)
            return

        name = node.name() if hasattr(node, "name") else str(node)
        node_type = getattr(node, "type_", None)
        if callable(node_type):
            node_type = node_type()
        if not node_type:
            node_type = node.__class__.__name__
        position = node.pos() if hasattr(node, "pos") else (0, 0)
        pos_text = (
            f"({int(position[0])}, {int(position[1])})"
            if isinstance(position, (list, tuple)) and len(position) >= 2
            else "-"
        )

        node_uuid, _, metadata_changed = self._ensure_node_metadata(node)
        if metadata_changed:
            self._set_modified(True)

        if self._detail_name_label:
            self._detail_name_label.setText(name)
        if self._detail_type_label:
            self._detail_type_label.setText(str(node_type))
        if self._detail_position_label:
            self._detail_position_label.setText(pos_text)
        if self._detail_uuid_label:
            self._detail_uuid_label.setText(node_uuid)
        if self._rename_input is not None:
            self._rename_input.blockSignals(True)
            self._rename_input.setText(name)
            self._rename_input.setEnabled(True)
            self._rename_input.blockSignals(False)
        if self._rename_button is not None:
            self._rename_button.setEnabled(True)

        self._update_memo_controls(node)

    def _apply_node_rename(self) -> None:
        if self._current_node is None or self._rename_input is None:
            self._show_info_dialog("名前を変更するノードを選択してください。")
            return

        new_name = self._rename_input.text().strip()
        if not new_name:
            self._show_info_dialog("新しい名前を入力してください。")
            return

        if hasattr(self._current_node, "set_name"):
            self._current_node.set_name(new_name)
        self._update_selected_node_info()
        self._set_modified(True)
        self._refresh_node_catalog()

    def _handle_memo_text_changed(self) -> None:
        if self._memo_controls_active or self._memo_text_edit is None:
            return
        if self._current_node is None or not self._is_memo_node(self._current_node):
            return
        text = self._memo_text_edit.toPlainText()
        try:
            current = self._current_node.get_property("memo_text")
        except Exception:  # pragma: no cover - NodeGraph 依存の例外
            current = None
        if current == text:
            return
        try:
            self._current_node.set_property("memo_text", text)
        except Exception:  # pragma: no cover - NodeGraph 依存の例外
            LOGGER.debug("メモテキストの更新に失敗しました", exc_info=True)
            return
        self._set_modified(True)

    def _handle_memo_font_size_changed(self, value: int) -> None:
        if self._memo_controls_active or self._memo_font_spin is None:
            return
        if self._current_node is None or not self._is_memo_node(self._current_node):
            return
        try:
            current = self._current_node.get_property("memo_font_size")
        except Exception:  # pragma: no cover - NodeGraph 依存の例外
            current = None
        if current == value:
            return
        try:
            self._current_node.set_property("memo_font_size", value)
        except Exception:  # pragma: no cover - NodeGraph 依存の例外
            LOGGER.debug("メモフォントサイズの更新に失敗しました", exc_info=True)
            return
        self._set_modified(True)

    def _set_memo_controls_enabled(self, enabled: bool) -> None:
        if self._memo_text_edit is not None:
            self._memo_text_edit.setEnabled(enabled)
        if self._memo_font_spin is not None:
            self._memo_font_spin.setEnabled(enabled)

    def _update_memo_controls(self, node) -> None:
        if self._memo_text_edit is None or self._memo_font_spin is None:
            return
        is_memo = self._is_memo_node(node)
        self._memo_controls_active = True
        if not is_memo:
            self._memo_text_edit.setPlainText("")
            self._memo_font_spin.setValue(MemoNode.DEFAULT_FONT_SIZE)
            self._set_memo_controls_enabled(False)
            self._memo_controls_active = False
            return

        self._set_memo_controls_enabled(True)
        try:
            memo_text = node.get_property("memo_text")
        except Exception:  # pragma: no cover - NodeGraph 依存の例外
            memo_text = ""
        try:
            font_size = node.get_property("memo_font_size")
        except Exception:  # pragma: no cover - NodeGraph 依存の例外
            font_size = MemoNode.DEFAULT_FONT_SIZE
        self._memo_text_edit.setPlainText(str(memo_text or ""))
        try:
            normalized_size = int(font_size)
        except (TypeError, ValueError):
            normalized_size = MemoNode.DEFAULT_FONT_SIZE
        self._memo_font_spin.setValue(normalized_size)
        self._memo_controls_active = False

    def _is_memo_node(self, node) -> bool:
        if node is None:
            return False
        return self._node_type_identifier(node) == MemoNode.node_type_identifier()

    def _return_to_start(self) -> None:
        if not self._confirm_discard_changes("未保存の変更があります。スタート画面に戻りますか？"):
            return
        self.hide()
        self.return_to_start_requested.emit()

    # ------------------------------------------------------------------
    # プロジェクトの保存・読み込み
    # ------------------------------------------------------------------
    def _file_save(self) -> None:
        graph_path = self._graph_file_path()
        if graph_path is None:
            self._show_error_dialog("プロジェクトが選択されていません。")
            return
        if self._current_project_root is not None:
            self._project_service.ensure_structure(self._current_project_root)
        try:
            self._write_project_to_path(graph_path)
            self._set_modified(False)
            self._show_info_dialog("プロジェクトを保存しました。")
        except OSError as exc:
            self._show_error_dialog(f"保存に失敗しました: {exc}")

    def _file_import(self) -> None:
        if self._current_project_root is None:
            self._show_info_dialog("先にプロジェクトを開いてください。")
            return
        start_dir = str(self._current_project_root / "assets")
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "アセットをインポート",
            start_dir,
            "All Files (*)",
        )
        if not filename:
            return
        source_path = Path(filename)
        target_dir = self._current_project_root / "assets" / "source"
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            destination = target_dir / source_path.name
            if source_path != destination:
                shutil.copy2(source_path, destination)
        except OSError as exc:
            self._show_error_dialog(f"アセットのコピーに失敗しました: {exc}")
            return
        self._create_asset_node(source_path.stem)
        self._set_modified(True)
        self._show_info_dialog(f"アセット「{source_path.name}」を登録しました。")

    def _write_project_to_path(self, path: Path) -> None:
        state = self._export_project_state()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(state, handle, ensure_ascii=True, indent=2)

    def _graph_file_path(self) -> Optional[Path]:
        if self._current_project_root is None:
            return None
        return self._current_project_root / "config" / "node_graph.json"

    def _reset_graph(self) -> None:
        existing_nodes = self._collect_all_nodes()
        if existing_nodes:
            try:
                self._graph.delete_nodes(existing_nodes)
            except Exception:
                pass
            self._remove_node_metadata(existing_nodes)
        self._known_nodes.clear()
        self._node_metadata.clear()
        self._node_spawn_offset = 0
        self._task_count = 0
        self._review_count = 0
        self._memo_count = 0
        clear_selection = getattr(self._graph, "clear_selection", None)
        if callable(clear_selection):
            try:
                clear_selection()
            except Exception:
                pass
        self._on_selection_changed()
        self._refresh_node_catalog()

    def _load_project_graph(self) -> None:
        graph_path = self._graph_file_path()
        self._reset_graph()
        if graph_path is None or not graph_path.exists():
            self._set_modified(False)
            return
        try:
            metadata_changed = self._load_project_from_path(graph_path)
            self._set_modified(bool(metadata_changed))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            self._show_error_dialog(f"プロジェクトの読み込みに失敗しました: {exc}")
            self._reset_graph()
            self._set_modified(False)

    def _load_project_from_path(self, path: Path) -> bool:
        with path.open("r", encoding="utf-8") as handle:
            state = json.load(handle)
        return self._apply_project_state(state)

    def _export_project_state(self) -> Dict:
        nodes = self._collect_all_nodes()
        return self._build_state_from_nodes(nodes)

    def _build_state_from_nodes(self, nodes: Iterable) -> Dict:
        node_list = list(nodes)
        node_entries = []
        node_id_map: Dict = {}
        node_uuid_map: Dict[object, str] = {}
        for index, node in enumerate(node_list):
            node_id_map[node] = index
            node_uuid, assigned_at, _ = self._ensure_node_metadata(node)
            node_uuid_map[node] = node_uuid
            entry = {
                "id": index,
                "name": self._safe_node_name(node),
                "type": self._node_type_identifier(node),
                "position": self._safe_node_position(node),
                "uuid": node_uuid,
            }
            if assigned_at:
                entry["uuid_assigned_at"] = assigned_at
            custom_props = self._node_custom_properties(node)
            if custom_props:
                entry["custom_properties"] = custom_props
            node_entries.append(entry)

        connections = []
        seen_connections: Set[
            Tuple[str, Optional[int], str, str, Optional[int], str]
        ] = set()
        for node in node_list:
            for port in self._collect_ports(node, output=True):
                for connected in self._connected_ports(port):
                    if not isinstance(connected, Port):
                        continue
                    target_node = connected.node() if hasattr(connected, "node") else None
                    if target_node is None or target_node not in node_id_map:
                        continue
                    source_uuid = node_uuid_map.get(node)
                    target_uuid = node_uuid_map.get(target_node)
                    if source_uuid is None or target_uuid is None:
                        continue
                    source_id = node_id_map[node]
                    target_id = node_id_map[target_node]
                    source_name = self._safe_port_name(port)
                    target_name = self._safe_port_name(connected)
                    source_index = self._port_index_in_node(node, port, output=True)
                    target_index = self._port_index_in_node(target_node, connected, output=False)
                    key = (
                        source_uuid,
                        source_index,
                        source_name,
                        target_uuid,
                        target_index,
                        target_name,
                    )
                    if key in seen_connections:
                        continue
                    seen_connections.add(key)
                    entry = {
                        "source": source_id,
                        "source_uuid": source_uuid,
                        "source_port": source_name,
                        "target": target_id,
                        "target_uuid": target_uuid,
                        "target_port": target_name,
                    }
                    if source_index is not None:
                        entry["source_port_index"] = source_index
                    if target_index is not None:
                        entry["target_port_index"] = target_index
                    connections.append(entry)

        return {"nodes": node_entries, "connections": connections}

    def _file_export_selected_nodes(self) -> None:
        selected_nodes = getattr(self._graph, "selected_nodes", None)
        if not callable(selected_nodes):
            self._show_error_dialog("選択中のノードを取得できませんでした。")
            return
        nodes = list(selected_nodes() or [])
        if not nodes:
            self._show_info_dialog("保存するノードを選択してください。")
            return

        start_dir = (
            str(self._current_project_root)
            if self._current_project_root is not None
            else str(Path.home())
        )
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "選択ノードを保存",
            start_dir,
            "JSON Files (*.json);;All Files (*)",
        )
        if not filename:
            return

        path = Path(filename)
        try:
            state = self._build_state_from_nodes(nodes)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8") as handle:
                json.dump(state, handle, ensure_ascii=True, indent=2)
        except (OSError, TypeError) as exc:
            self._show_error_dialog(f"保存に失敗しました: {exc}")
            return

        self._show_info_dialog("選択したノードを保存しました。")

    def _apply_project_state(self, state: Dict) -> bool:
        nodes_info = state.get("nodes") if isinstance(state, dict) else None
        connections_info = state.get("connections") if isinstance(state, dict) else None
        if not isinstance(nodes_info, list) or not isinstance(connections_info, list):
            raise ValueError("プロジェクトファイルの形式が不正です。")

        existing_nodes = self._collect_all_nodes()
        if existing_nodes:
            self._graph.delete_nodes(existing_nodes)
            self._remove_node_metadata(existing_nodes)

        self._known_nodes.clear()
        self._node_metadata.clear()
        self._node_spawn_offset = 0
        self._task_count = 0
        self._review_count = 0

        identifier_map: Dict[int, object] = {}
        uuid_map: Dict[str, object] = {}
        metadata_changed = False
        for entry in nodes_info:
            if not isinstance(entry, dict):
                continue
            node_type = entry.get("type")
            node_name = entry.get("name")
            position = entry.get("position")
            if not isinstance(node_type, str) or not isinstance(node_name, str):
                continue
            node = self._graph.create_node(node_type, name=node_name)
            if isinstance(position, (list, tuple)) and len(position) >= 2:
                try:
                    node.set_pos(float(position[0]), float(position[1]))
                except Exception:
                    pass
            entry_id = entry.get("id")
            if isinstance(entry_id, int):
                identifier_map[entry_id] = node
            self._known_nodes.append(node)
            node_uuid = entry.get("uuid")
            assigned_at = entry.get("uuid_assigned_at")
            normalized_uuid, _, changed = self._ensure_node_metadata(
                node,
                uuid_value=node_uuid if isinstance(node_uuid, str) else None,
                assigned_at=assigned_at if isinstance(assigned_at, str) else None,
            )
            uuid_map[normalized_uuid] = node
            if changed:
                metadata_changed = True
            custom_props = entry.get("custom_properties")
            if isinstance(custom_props, dict):
                for key, value in custom_props.items():
                    try:
                        node.set_property(key, value, push_undo=False)
                    except Exception:  # pragma: no cover - NodeGraph 依存の例外
                        LOGGER.debug("プロパティ %s の適用に失敗しました", key, exc_info=True)

        failed_operations: List[str] = []

        for index, connection in enumerate(connections_info):
            if not isinstance(connection, dict):
                failed_operations.append(
                    f"接続エントリ #{index + 1} の形式が不正なため処理できませんでした。"
                )
                continue
            source_node = None
            target_node = None
            source_uuid = connection.get("source_uuid")
            target_uuid = connection.get("target_uuid")
            if isinstance(source_uuid, str):
                source_node = uuid_map.get(source_uuid)
            if isinstance(target_uuid, str):
                target_node = uuid_map.get(target_uuid)
            if source_node is None:
                source_id = connection.get("source")
                if isinstance(source_id, int):
                    source_node = identifier_map.get(source_id)
            if target_node is None:
                target_id = connection.get("target")
                if isinstance(target_id, int):
                    target_node = identifier_map.get(target_id)
            raw_source_id = connection.get("source")
            raw_target_id = connection.get("target")
            if isinstance(source_uuid, str) and source_uuid:
                source_label = source_uuid
            elif isinstance(raw_source_id, int):
                source_label = str(raw_source_id)
            else:
                source_label = "不明"
            if isinstance(target_uuid, str) and target_uuid:
                target_label = target_uuid
            elif isinstance(raw_target_id, int):
                target_label = str(raw_target_id)
            else:
                target_label = "不明"
            if source_node is None or target_node is None:
                failed_operations.append(
                    "接続（source="
                    + source_label
                    + ", target="
                    + target_label
                    + "）のノードが見つからないため再現できませんでした。"
                )
                continue
            source_name, source_index = self._parse_connection_port_reference(
                connection.get("source_port"),
                connection.get("source_port_index"),
            )
            target_name, target_index = self._parse_connection_port_reference(
                connection.get("target_port"),
                connection.get("target_port_index"),
            )
            source_port = self._find_port(
                source_node,
                port_name=source_name,
                port_index=source_index,
                output=True,
            )
            target_port = self._find_port(
                target_node,
                port_name=target_name,
                port_index=target_index,
                output=False,
            )
            if source_port is None:
                source_port = self._first_output_port(source_node)
            if target_port is None:
                target_port = self._first_input_port(target_node)
            if source_port is None or target_port is None:
                missing_parts: List[str] = []
                if source_port is None:
                    missing_parts.append("出力ポート")
                if target_port is None:
                    missing_parts.append("入力ポート")
                reason = "と".join(missing_parts)
                failed_operations.append(
                    f"接続（source={source_label}, target={target_label}）の{reason}を特定できませんでした。"
                )
                continue
            try:
                self._connect_ports_compat(source_port, target_port)
            except Exception as exc:
                failed_operations.append(
                    f"接続（source={source_label}, target={target_label}）の再現に失敗しました: {exc}"
                )
                continue

        self._node_spawn_offset = len(self._known_nodes)
        self._task_count = sum(
            1 for node in self._known_nodes if self._node_type_identifier(node) == "sotugyo.demo.TaskNode"
        )
        self._review_count = sum(
            1 for node in self._known_nodes if self._node_type_identifier(node) == "sotugyo.demo.ReviewNode"
        )
        self._memo_count = sum(
            1 for node in self._known_nodes if self._node_type_identifier(node) == MemoNode.node_type_identifier()
        )

        clear_selection = getattr(self._graph, "clear_selection", None)
        if callable(clear_selection):
            clear_selection()
        self._on_selection_changed()
        self._refresh_node_catalog()

        if failed_operations:
            summary = "\n".join(f"・{message}" for message in failed_operations)
            self._show_warning_dialog(
                "プロジェクトの再構成中に一部のコネクションを再現できませんでした。\n" + summary
            )

        return metadata_changed

    def _safe_node_name(self, node) -> str:
        if hasattr(node, "name"):
            try:
                return str(node.name())
            except Exception:
                pass
        return str(node)

    def _node_custom_properties(self, node) -> Dict[str, object]:
        model = getattr(node, "model", None)
        if model is None:
            return {}
        props = getattr(model, "custom_properties", None)
        if callable(props):
            try:
                props = props()
            except Exception:  # pragma: no cover - NodeGraph 依存の例外
                props = None
        if not isinstance(props, dict):
            return {}
        serializable: Dict[str, object] = {}
        for key, value in props.items():
            if isinstance(key, str):
                if isinstance(value, (str, int, float, bool)) or value is None:
                    serializable[key] = value
                else:
                    serializable[key] = str(value)
        return serializable

    def _node_type_identifier(self, node) -> str:
        type_getter = getattr(node, "type_", None)
        if callable(type_getter):
            try:
                return str(type_getter())
            except Exception:
                pass
        identifier = getattr(node, "__identifier__", "")
        class_name = node.__class__.__name__
        return f"{identifier}.{class_name}" if identifier else class_name

    def _safe_node_position(self, node) -> List[float]:
        position = getattr(node, "pos", None)
        if callable(position):
            try:
                pos = position()
                if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                    return [float(pos[0]), float(pos[1])]
            except Exception:
                pass
        return [0.0, 0.0]

    @staticmethod
    def _safe_port_name(port) -> str:
        name_method = getattr(port, "name", None)
        if callable(name_method):
            try:
                return str(name_method())
            except Exception:
                pass
        return str(port)

    @staticmethod
    def _connected_ports(port) -> List:
        connected_getter = getattr(port, "connected_ports", None)
        if not callable(connected_getter):
            return []
        try:
            return list(connected_getter() or [])
        except Exception:
            return []

    def _collect_ports(self, node, *, output: bool) -> List[Port]:
        accessor = "output_ports" if output else "input_ports"
        ports_getter = getattr(node, accessor, None)
        if not callable(ports_getter):
            return []
        try:
            raw_ports = ports_getter()
        except Exception:
            return []
        if not raw_ports:
            return []
        if isinstance(raw_ports, Mapping):
            candidates = raw_ports.values()
        elif isinstance(raw_ports, IterableABC) and not isinstance(raw_ports, (str, bytes)):
            candidates = raw_ports
        else:
            return []
        ports: List[Port] = []
        for entry in candidates:
            if isinstance(entry, Port):
                ports.append(entry)
        return ports

    def _port_index_in_node(self, node, port, *, output: bool) -> Optional[int]:
        for index, candidate in enumerate(self._collect_ports(node, output=output)):
            if candidate is port:
                return index
        return None

    @staticmethod
    def _parse_connection_port_reference(
        port_entry, index_entry
    ) -> Tuple[Optional[str], Optional[int]]:
        name: Optional[str] = None
        index: Optional[int] = None
        
        def _normalize_index(value) -> Optional[int]:
            if isinstance(value, bool):
                return None
            try:
                return int(value)
            except (TypeError, ValueError):
                return None

        if isinstance(port_entry, dict):
            raw_name = port_entry.get("name")
            if isinstance(raw_name, str):
                name = raw_name
            raw_index = port_entry.get("index")
            normalized = _normalize_index(raw_index)
            if normalized is not None:
                index = normalized
        elif isinstance(port_entry, str):
            name = port_entry
        normalized_index = _normalize_index(index_entry)
        if normalized_index is not None:
            index = normalized_index
        return name, index

    def _find_port(
        self,
        node,
        *,
        port_name: Optional[str],
        port_index: Optional[int],
        output: bool,
    ) -> Optional[Port]:
        ports = self._collect_ports(node, output=output)
        if not ports:
            return None
        if isinstance(port_index, int) and 0 <= port_index < len(ports):
            candidate = ports[port_index]
            candidate_name = self._safe_port_name(candidate)
            if port_name is not None and candidate_name != port_name:
                node_identifier = getattr(node, "name", None)
                if callable(node_identifier):
                    node_identifier = node_identifier()
                if node_identifier is None:
                    node_identifier = repr(node)
                LOGGER.debug(
                    "ポート名の不一致: index=%s, expected=%s, actual=%s, node=%s",
                    port_index,
                    port_name,
                    candidate_name,
                    node_identifier,
                )
            return candidate
        for index, port in enumerate(ports):
            if port_name is not None and self._safe_port_name(port) != port_name:
                continue
            if port_index is not None and port_index != index:
                continue
            return port
        return None

    def _set_modified(self, modified: bool) -> None:
        self._is_modified = modified
        self._refresh_window_title()

    def _refresh_window_title(self) -> None:
        title = self.WINDOW_TITLE
        if self._current_project_settings is not None:
            title += f" - {self._current_project_settings.project_name}"
        if self._current_user is not None:
            title += f" ({self._current_user.display_name})"
        self._base_window_title = title
        if self._is_modified:
            title = f"*{title}"
        self.setWindowTitle(title)

    def _confirm_project_change(self, project_name: str) -> bool:
        result = QMessageBox.question(
            self,
            "確認",
            f"プロジェクト「{project_name}」に切り替えますか？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return result == QMessageBox.StandardButton.Yes

    def _notify_start_window_refresh(self) -> None:
        parent = self.parent()
        if parent is None:
            return
        refresher = getattr(parent, "refresh_start_state", None)
        if callable(refresher):
            try:
                refresher()
            except Exception:
                pass

    def _confirm_discard_changes(self, message: Optional[str] = None) -> bool:
        if not self._is_modified:
            return True
        text = (
            message
            if message
            else "未保存の変更があります。操作を続行すると現在の編集内容が失われます。続行しますか？"
        )
        result = QMessageBox.warning(
            self,
            "確認",
            text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return result == QMessageBox.StandardButton.Yes

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._confirm_discard_changes("未保存の変更があります。ウィンドウを閉じますか？"):
            event.ignore()
            return
        super().closeEvent(event)
        self.return_to_start_requested.emit()
