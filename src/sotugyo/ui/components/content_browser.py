"""ノードエディタ向けコンテンツブラウザコンポーネント。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QIcon,
    QPainter,
    QPen,
    QPixmap,
    QResizeEvent,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QBoxLayout,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True)
class NodeCatalogEntry:
    """ノード追加候補を表現するエントリ。"""

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
    section_padding: Tuple[int, int, int, int]


class NodeCatalogViewModel:
    """コンテンツブラウザ表示用のビューモデル。"""

    def __init__(self) -> None:
        self._entries: List[NodeCatalogEntry] = []
        self._keyword: str = ""
        self._genre: Optional[str] = None

    @property
    def entries(self) -> Sequence[NodeCatalogEntry]:
        return tuple(self._entries)

    def set_entries(self, entries: Iterable[NodeCatalogEntry]) -> None:
        self._entries = list(entries)

    def set_keyword(self, keyword: str) -> None:
        self._keyword = keyword.strip().lower()

    def set_genre(self, genre: Optional[str]) -> None:
        self._genre = genre or None

    def total_count(self) -> int:
        return len(self._entries)

    def genre_total(self, genre: Optional[str]) -> int:
        if genre is None:
            return self.total_count()
        return sum(1 for entry in self._entries if entry.genre == genre)

    def genres(self) -> List[str]:
        return sorted({entry.genre for entry in self._entries if entry.genre})

    def matches(self, entry: NodeCatalogEntry) -> bool:
        keyword = self._keyword
        if keyword and keyword not in entry.searchable_text():
            return False
        if self._genre and entry.genre != self._genre:
            return False
        return True


class NodeContentBrowser(QWidget):
    """ノード追加と検索をまとめたコンテンツブラウザ。"""

    node_type_requested = Signal(str)
    search_submitted = Signal(str)
    back_requested = Signal()
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._view_model = NodeCatalogViewModel()
        self._search_line: QLineEdit = QLineEdit(self)
        self._genre_combo: Optional[QComboBox] = None
        self._available_list: QListWidget = QListWidget(self)
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
        self._outer_layout: Optional[QVBoxLayout] = None
        self._card_frame: Optional[QFrame] = None
        self._card_layout: Optional[QVBoxLayout] = None
        self._section_frames: List[QFrame] = []
        self._control_header: Optional[QWidget] = None
        self._control_header_layout: Optional[QBoxLayout] = None
        self._control_header_spacer: Optional[QSpacerItem] = None
        self._result_summary_label: Optional[QLabel] = None
        self._icon_cache: Dict[Tuple[str, int], QIcon] = {}
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
                section_padding=(16, 16, 16, 16),
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
                section_padding=(16, 16, 16, 16),
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
                section_padding=(14, 14, 14, 14),
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
                section_padding=(12, 12, 12, 12),
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
                section_padding=(10, 10, 10, 10),
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

    # ------------------------------------------------------------------
    # カタログ操作
    # ------------------------------------------------------------------
    def set_catalog_entries(self, entries: Iterable[NodeCatalogEntry]) -> None:
        catalog_entries = list(entries)
        self._view_model.set_entries(catalog_entries)
        self._total_entry_count = self._view_model.total_count()
        self._available_list.clear()
        self._icon_cache.clear()

        alignment = Qt.AlignLeft | Qt.AlignTop
        item_size = self._list_item_size_hint()
        for entry in catalog_entries:
            item = QListWidgetItem(self._format_entry_text(entry))
            item.setData(Qt.UserRole, entry.node_type)
            item.setData(Qt.UserRole + 1, entry.searchable_text())
            item.setData(Qt.UserRole + 2, entry.genre)
            item.setToolTip(self._entry_tooltip(entry))
            item.setTextAlignment(alignment)
            item.setSizeHint(item_size)
            item.setIcon(self._icon_for_entry(entry))
            self._available_list.addItem(item)

        self._populate_genre_options()
        self._apply_icon_size()
        self._update_item_texts()
        self._apply_filter()

    def set_available_nodes(self, entries: Iterable[Dict[str, str]]) -> None:
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
            elif isinstance(raw_keywords, Iterable):
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
        self.set_catalog_entries(catalog_entries)

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

    # ------------------------------------------------------------------
    # UI 構築
    # ------------------------------------------------------------------
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
        padding = getattr(self._current_profile, "section_padding", (16, 16, 16, 16))
        frame_layout.setContentsMargins(*padding)
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

        self._section_frames.append(frame)

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

    def _apply_filter(self) -> None:
        keyword = self._search_line.text().strip().lower()
        self._view_model.set_keyword(keyword)
        visible_count = 0
        for index, entry in enumerate(self._view_model.entries):
            item = self._available_list.item(index)
            if item is None:
                continue
            matches = self._view_model.matches(entry)
            item.setHidden(not matches)
            if matches:
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
        self._refresh_icons()
        self._refresh_item_sizes()
        tooltip = (
            f"表示サイズ: {icon_size_value}px"
            f" / {self._icon_size_level} 段階 ({len(self._icon_size_levels)}段階中)"
        )
        self._icon_size_slider.setToolTip(tooltip)
        self._icon_size_spin.setToolTip(tooltip)
        if self._result_summary_label is not None and self._visible_entry_count:
            self._update_summary_label()

    def _on_genre_changed(self, index: int) -> None:
        if self._genre_combo is None:
            return
        data = self._genre_combo.itemData(index)
        self._current_genre = data if isinstance(data, str) and data else None
        self._view_model.set_genre(self._current_genre)
        self._apply_filter()

    def _populate_genre_options(self) -> None:
        if self._genre_combo is None:
            return
        previous = self._current_genre
        genres = self._view_model.genres()
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
        self._view_model.set_genre(previous)
        tooltip_lines = ["ジャンルで一覧を絞り込みます。"]
        if genres:
            tooltip_lines.append("登録ジャンル: " + ", ".join(genres))
        self._genre_combo.setToolTip("\n".join(tooltip_lines))

    def _update_layout_for_size(self, size: QSize) -> None:
        width = size.width() if size is not None else self.width()
        profile = self._select_layout_profile(width)
        if profile != self._current_profile:
            self._apply_profile(profile)

        self._apply_icon_size()
        self._refresh_item_sizes()
        self._update_item_texts()
        self._adjust_control_header(width)

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
        self._available_list.setSpacing(
            16 if profile.view_mode == QListWidget.IconMode else 8
        )
        self._available_list.setWordWrap(
            False if profile.view_mode == QListWidget.IconMode else True
        )
        padding = profile.card_padding
        if self._card_layout is not None:
            self._card_layout.setContentsMargins(*padding)
        for frame in self._section_frames:
            layout = frame.layout()
            if isinstance(layout, QVBoxLayout):
                layout.setContentsMargins(*profile.section_padding)
                layout.setSpacing(profile.section_spacing)

    def _adjust_control_header(self, width: int) -> None:
        if self._control_header_layout is None:
            return
        is_vertical = width < 720 or self._compact_mode
        target_direction = QBoxLayout.TopToBottom if is_vertical else QBoxLayout.LeftToRight
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
            self._control_header_layout.setAlignment(self._icon_control_container, alignment)
        spacing = 4 if is_vertical else 8
        if self._control_header_layout.spacing() != spacing:
            self._control_header_layout.setSpacing(spacing)
        if self._control_header is not None:
            self._control_header.updateGeometry()
        self._control_header_layout.invalidate()

    def _refresh_item_sizes(self) -> None:
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

    def _refresh_icons(self) -> None:
        for index, entry in enumerate(self._view_model.entries):
            item = self._available_list.item(index)
            if item is None:
                continue
            item.setIcon(self._icon_for_entry(entry))

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

        if profile.view_mode == QListWidget.IconMode and not profile.compact:
            padding = max(12, icon_size // 4)
            cell = icon_size + padding * 2
            return QSize(cell, cell)

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

    def _icon_size_from_level(self, level: int) -> int:
        return self._icon_size_levels.get(
            level,
            self._icon_size_levels.get(self._icon_size_default_level, 32),
        )

    def _current_icon_size_value(self) -> int:
        return self._icon_size

    def _icon_for_entry(self, entry: NodeCatalogEntry) -> QIcon:
        icon_size = self._current_icon_size_value()
        key = (entry.node_type, icon_size)
        cached = self._icon_cache.get(key)
        if cached is not None:
            return cached

        pixmap = self._create_entry_pixmap(entry)
        icon = QIcon(pixmap)
        self._icon_cache[key] = icon
        return icon

    def _create_entry_pixmap(self, entry: NodeCatalogEntry) -> QPixmap:
        icon_size = self._current_icon_size_value()
        if hasattr(self, "devicePixelRatioF"):
            device_ratio = max(1.0, float(self.devicePixelRatioF()))
        else:
            device_ratio = 1.0
        pixel_size = max(1, int(round(icon_size * device_ratio)))
        pixmap = QPixmap(pixel_size, pixel_size)
        pixmap.setDevicePixelRatio(device_ratio)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)

        rect_margin = max(4, pixel_size // 12)
        rect = pixmap.rect().adjusted(rect_margin, rect_margin, -rect_margin, -rect_margin)

        fill_color = self._genre_color(entry.genre)
        painter.setBrush(fill_color)

        border_color = QColor(fill_color)
        border_color = border_color.darker(125)
        border_color.setAlpha(255)
        border_pen = QPen(border_color)
        border_pen.setWidth(max(2, pixel_size // 20))
        painter.setPen(border_pen)
        corner_radius = max(6, pixel_size // 10)
        painter.drawRoundedRect(rect, corner_radius, corner_radius)

        title_source = entry.title or entry.subtitle or entry.node_type
        label_text = self._icon_label_text(title_source)
        if label_text:
            text_color = QColor(255, 255, 255)
            painter.setPen(text_color)
            font = QFont()
            font.setBold(True)
            font.setPointSizeF(max(8.0, icon_size * 0.32))
            painter.setFont(font)
            painter.drawText(rect, Qt.AlignCenter, label_text)

        painter.end()
        return pixmap

    def _genre_color(self, genre: str) -> QColor:
        palette = {
            "ツール環境": QColor(14, 165, 233),
            "ワークフロー": QColor(34, 197, 94),
            "メモ": QColor(249, 115, 22),
        }
        color = palette.get(genre)
        if color is None:
            color = QColor(99, 102, 241)
        return color

    def _icon_label_text(self, source_text: str) -> str:
        for char in source_text:
            if char.isalnum():
                return char.upper()
            if char.strip():
                return char
        return ""

    def _format_entry_text(self, entry: NodeCatalogEntry) -> str:
        if self._current_profile.view_mode == QListWidget.IconMode and not self._compact_mode:
            return ""

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
            if not parts:
                return ""
            return " – ".join(parts) if len(parts) > 1 else parts[0]

        lines = [text for text in (title, subtitle) if text]
        if not lines and node_type:
            lines.append(node_type)
        return "\n".join(lines)

    def _entry_tooltip(self, entry: NodeCatalogEntry) -> str:
        lines: List[str] = []
        if entry.title:
            lines.append(entry.title)
        if entry.subtitle:
            lines.append(entry.subtitle)
        lines.append(f"タイプ: {entry.node_type}")
        if entry.genre:
            lines.append(f"ジャンル: {entry.genre}")
        if entry.keywords:
            lines.append("キーワード: " + ", ".join(entry.keywords))
        return "\n".join(lines)

    def _update_item_texts(self) -> None:
        for index, entry in enumerate(self._view_model.entries):
            item = self._available_list.item(index)
            if item is None:
                continue
            item.setText(self._format_entry_text(entry))

    def _update_summary_label(self, visible_count: Optional[int] = None) -> None:
        if self._result_summary_label is None:
            return
        if visible_count is None:
            visible_count = sum(
                0 if item is None or item.isHidden() else 1
                for item in (
                    self._available_list.item(i)
                    for i in range(self._available_list.count())
                )
            )
        self._visible_entry_count = visible_count
        if self._current_genre:
            total = self._view_model.genre_total(self._current_genre)
            text = f"{visible_count} 件 / {total} 件（ジャンル: {self._current_genre}）"
        else:
            text = f"{visible_count} 件 / 全 {self._total_entry_count} 件"
        self._result_summary_label.setText(text)

    def _guess_genre(self, node_type: str) -> str:
        normalized = node_type.strip()
        if normalized.startswith("tool-environment:") or normalized.startswith("sotugyo.tooling"):
            return "ツール環境"
        if normalized.startswith("sotugyo.demo."):
            return "ワークフロー"
        if normalized.startswith("sotugyo.memo."):
            return "メモ"
        return "その他"
