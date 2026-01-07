"""ノードエディタ向けコンテンツブラウザコンポーネント。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from qtpy import QtCore, QtGui, QtWidgets

Qt = QtCore.Qt
Signal = QtCore.Signal
QSize = QtCore.QSize
QFileInfo = QtCore.QFileInfo
QColor = QtGui.QColor
QFont = QtGui.QFont
QFontMetrics = QtGui.QFontMetrics
QIcon = QtGui.QIcon
QPainter = QtGui.QPainter
QPen = QtGui.QPen
QPixmap = QtGui.QPixmap
QResizeEvent = QtGui.QResizeEvent
QStandardItem = QtGui.QStandardItem
QStandardItemModel = QtGui.QStandardItemModel
QAbstractItemView = QtWidgets.QAbstractItemView
QBoxLayout = QtWidgets.QBoxLayout
QComboBox = QtWidgets.QComboBox
QFrame = QtWidgets.QFrame
QHBoxLayout = QtWidgets.QHBoxLayout
QLabel = QtWidgets.QLabel
QLineEdit = QtWidgets.QLineEdit
QPushButton = QtWidgets.QPushButton
QFileIconProvider = QtWidgets.QFileIconProvider
QSizePolicy = QtWidgets.QSizePolicy
QSlider = QtWidgets.QSlider
QSpinBox = QtWidgets.QSpinBox
QSpacerItem = QtWidgets.QSpacerItem
QTreeView = QtWidgets.QTreeView
QVBoxLayout = QtWidgets.QVBoxLayout
QWidget = QtWidgets.QWidget


@dataclass(frozen=True)
class NodeCatalogEntry:
    """ノード追加候補を表現するエントリ。"""

    node_type: str
    title: str
    subtitle: str
    genre: str
    keywords: Tuple[str, ...] = ()
    icon_path: Optional[str] = None
    tool_name: Optional[str] = None
    version_label: Optional[str] = None

    def searchable_text(self) -> str:
        parts = [
            self.title,
            self.subtitle,
            self.node_type,
            self.tool_name or "",
            self.version_label or "",
            *self.keywords,
        ]
        return "\n".join(part.lower() for part in parts if part)


@dataclass(frozen=True)
class BrowserLayoutProfile:
    """コンテンツブラウザのレイアウト設定。"""

    min_width: int
    compact: bool
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
        self._available_tree: QTreeView = QTreeView(self)
        self._available_model: QStandardItemModel = QStandardItemModel(self)
        self._genre_items: Dict[str, QStandardItem] = {}
        self._tool_group_items: Dict[Tuple[str, str], QStandardItem] = {}
        self._entry_items: List[Tuple[NodeCatalogEntry, QStandardItem]] = []
        self._tree_selection_model: Optional[QtCore.QItemSelectionModel] = None
        self._tree_selection_connected: bool = False
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
        self._icon_cache: Dict[Tuple[str, str, int], QIcon] = {}
        self._file_icon_provider: QFileIconProvider = QFileIconProvider()
        self._layout_profiles: List[BrowserLayoutProfile] = [
            BrowserLayoutProfile(
                min_width=1080,
                compact=False,
                section_spacing=10,
                card_padding=(16, 16, 16, 16),
                section_padding=(10, 10, 10, 10),
            ),
            BrowserLayoutProfile(
                min_width=860,
                compact=False,
                section_spacing=10,
                card_padding=(16, 16, 16, 16),
                section_padding=(10, 10, 10, 10),
            ),
            BrowserLayoutProfile(
                min_width=660,
                compact=False,
                section_spacing=8,
                card_padding=(14, 14, 14, 14),
                section_padding=(8, 8, 8, 8),
            ),
            BrowserLayoutProfile(
                min_width=520,
                compact=False,
                section_spacing=8,
                card_padding=(12, 12, 12, 12),
                section_padding=(8, 8, 8, 8),
            ),
            BrowserLayoutProfile(
                min_width=0,
                compact=True,
                section_spacing=6,
                card_padding=(12, 12, 12, 12),
                section_padding=(6, 6, 6, 6),
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
        self._available_model.clear()
        self._available_model.setHorizontalHeaderLabels(["ノード"])
        self._available_tree.setModel(self._available_model)
        self._connect_tree_selection_model()
        self._genre_items = {}
        self._tool_group_items = {}
        self._entry_items = []
        self._icon_cache.clear()

        for entry in catalog_entries:
            genre_item = self._genre_items.get(entry.genre)
            if genre_item is None:
                genre_item = QStandardItem(entry.genre)
                genre_item.setEditable(False)
                genre_item.setSelectable(True)
                font = QFont()
                font.setBold(True)
                genre_item.setFont(font)
                self._available_model.appendRow(genre_item)
                self._genre_items[entry.genre] = genre_item

            item = QStandardItem(self._format_entry_text(entry))
            item.setEditable(False)
            item.setSelectable(True)
            item.setToolTip(self._entry_tooltip(entry))
            item.setData(entry.node_type, Qt.UserRole)
            item.setData(entry.searchable_text(), Qt.UserRole + 1)
            item.setData(entry.genre, Qt.UserRole + 2)
            item.setData(entry, Qt.UserRole + 3)
            item.setIcon(self._icon_for_entry(entry))
            group_item = self._resolve_tool_group_item(entry, genre_item)
            if group_item is not None:
                group_item.appendRow(item)
            else:
                genre_item.appendRow(item)
            self._entry_items.append((entry, item))

        self._populate_genre_options()
        self._apply_icon_size()
        self._update_item_texts()
        self._update_parent_labels()
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
        for entry, item in self._entry_items:
            if self._is_item_visible(item):
                node_type = item.data(Qt.UserRole)
                if isinstance(node_type, str):
                    return node_type
        return None

    # ------------------------------------------------------------------
    # UI 構築
    # ------------------------------------------------------------------
    def _setup_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(6)
        self._outer_layout = outer_layout

        card = QFrame(self)
        card.setObjectName("panelCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(8)
        self._card_frame = card
        self._card_layout = card_layout

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

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
        search_layout.setSpacing(6)

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

        self._configure_tree_view(self._available_tree)

        icon_control = self._create_icon_size_control(card)
        summary_widget = self._create_result_summary(card)
        header_container = QWidget(card)
        header_container_layout = QHBoxLayout(header_container)
        header_container_layout.setContentsMargins(0, 0, 0, 0)
        header_container_layout.setSpacing(6)
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
                self._available_tree,
                header_widget=header_container,
            ),
            1,
        )

        outer_layout.addWidget(card, 1)

    def _configure_tree_view(self, widget: QTreeView) -> None:
        widget.setObjectName("contentTree")
        widget.setModel(self._available_model)
        widget.setHeaderHidden(True)
        widget.setRootIsDecorated(True)
        widget.setAnimated(True)
        widget.setItemsExpandable(True)
        widget.setUniformRowHeights(False)
        widget.setIndentation(18)
        widget.setSelectionMode(QAbstractItemView.SingleSelection)
        widget.setSelectionBehavior(QAbstractItemView.SelectRows)
        widget.setEditTriggers(QAbstractItemView.NoEditTriggers)
        widget.setWordWrap(True)
        widget.setTextElideMode(Qt.TextElideMode.ElideNone)
        widget.setIconSize(
            QSize(self._current_icon_size_value(), self._current_icon_size_value())
        )
        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._apply_icon_size()

    def _build_section(
        self,
        title: str,
        widget: QWidget,
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
        self._available_tree.doubleClicked.connect(self._on_tree_item_double_clicked)
        self._connect_tree_selection_model()
        self._icon_size_slider.valueChanged.connect(self._on_icon_size_changed)
        self._icon_size_spin.valueChanged[int].connect(self._on_icon_size_changed)
        if self._genre_combo is not None:
            self._genre_combo.currentIndexChanged.connect(self._on_genre_changed)

    def _apply_filter(self) -> None:
        keyword = self._search_line.text().strip().lower()
        self._view_model.set_keyword(keyword)
        visible_counts: Dict[str, int] = {}
        total_counts: Dict[str, int] = {}
        group_visible_counts: Dict[Tuple[str, str], int] = {}
        group_total_counts: Dict[Tuple[str, str], int] = {}
        visible_count = 0

        for entry, item in self._entry_items:
            parent_item = item.parent()
            parent_index = parent_item.index() if parent_item is not None else QtCore.QModelIndex()
            matches = self._view_model.matches(entry)
            self._available_tree.setRowHidden(item.row(), parent_index, not matches)
            total_counts[entry.genre] = total_counts.get(entry.genre, 0) + 1
            if matches:
                visible_counts[entry.genre] = visible_counts.get(entry.genre, 0) + 1
                visible_count += 1
            group_key = self._tool_group_key(entry)
            if group_key is not None:
                group_total_counts[group_key] = group_total_counts.get(group_key, 0) + 1
                if matches:
                    group_visible_counts[group_key] = group_visible_counts.get(group_key, 0) + 1

        for group_key, group_item in self._tool_group_items.items():
            visible = group_visible_counts.get(group_key, 0)
            parent_item = group_item.parent()
            parent_index = parent_item.index() if parent_item is not None else QtCore.QModelIndex()
            self._available_tree.setRowHidden(group_item.row(), parent_index, visible == 0)
            self._available_tree.setExpanded(group_item.index(), visible > 0)

        root_index = QtCore.QModelIndex()
        for genre, genre_item in self._genre_items.items():
            genre_visible = visible_counts.get(genre, 0)
            parent_row = genre_item.row()
            parent_visible = genre_visible > 0
            self._available_tree.setRowHidden(parent_row, root_index, not parent_visible)
            self._available_tree.setExpanded(genre_item.index(), parent_visible)

        self._visible_entry_count = visible_count
        self._update_parent_labels(visible_counts, total_counts)
        self._update_tool_group_labels(group_visible_counts, group_total_counts)
        self._update_summary_label(visible_count)

    def _on_search_submitted(self) -> None:
        self.search_submitted.emit(self._search_line.text())

    def _on_tree_item_double_clicked(self, index: QtCore.QModelIndex) -> None:
        item = self._available_model.itemFromIndex(index)
        self._emit_node_request_if_available(item)

    def _on_tree_selection_changed(
        self,
        selected: QtCore.QItemSelection,
        deselected: QtCore.QItemSelection,
    ) -> None:
        indexes = selected.indexes()
        if not indexes:
            return
        item = self._available_model.itemFromIndex(indexes[0])
        self._emit_node_request_if_available(item)

    def _emit_node_request_if_available(self, item: Optional[QStandardItem]) -> None:
        if item is None or item.hasChildren():
            return
        node_type = item.data(Qt.UserRole)
        if isinstance(node_type, str) and node_type:
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
        self._available_tree.setIconSize(icon_size)
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
        self._available_tree.setIndentation(14 if profile.compact else 18)
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
        spacing = 4 if is_vertical else 6
        if self._control_header_layout.spacing() != spacing:
            self._control_header_layout.setSpacing(spacing)
        if self._control_header is not None:
            self._control_header.updateGeometry()
        self._control_header_layout.invalidate()

    def _refresh_item_sizes(self) -> None:
        item_size = self._list_item_size_hint()
        parent_size = self._parent_item_size_hint()
        for genre_item in self._genre_items.values():
            genre_item.setSizeHint(parent_size)
            for row in range(genre_item.rowCount()):
                child = genre_item.child(row)
                if child is not None:
                    if child.hasChildren():
                        child.setSizeHint(parent_size)
                        for nested_row in range(child.rowCount()):
                            nested_child = child.child(nested_row)
                            if nested_child is not None:
                                nested_child.setSizeHint(item_size)
                    else:
                        child.setSizeHint(item_size)
        self._available_tree.updateGeometry()
        self._available_tree.doItemsLayout()
        viewport = self._available_tree.viewport()
        if viewport is not None:
            viewport.update()

    def _refresh_icons(self) -> None:
        for entry, item in self._entry_items:
            item.setIcon(self._icon_for_entry(entry))

    def _list_item_size_hint(self) -> QSize:
        font: QFontMetrics = self._available_tree.fontMetrics()
        icon_size = self._current_icon_size_value()
        viewport = self._available_tree.viewport()
        viewport_width = viewport.width() if viewport is not None else 0
        if viewport_width <= 0:
            viewport_width = max(self.width() - 40, icon_size + 64)

        line_spacing = font.lineSpacing()
        leading = font.leading()
        profile = self._current_profile

        if profile.compact:
            vertical_padding = max(6, leading + 2)
            text_lines = 2
            text_height = line_spacing * text_lines
            height = max(icon_size + vertical_padding, text_height + vertical_padding)
            width = max(220, viewport_width)
            return QSize(width, height)

        width = max(icon_size + 72, viewport_width)
        title_width = font.horizontalAdvance("M" * 18)
        width = max(width, title_width + icon_size // 2)

        vertical_padding = max(10, leading + 6)
        text_lines = 2
        text_height = line_spacing * text_lines
        height = max(icon_size + vertical_padding, text_height + vertical_padding)
        return QSize(width, height)

    def _parent_item_size_hint(self) -> QSize:
        font: QFontMetrics = self._available_tree.fontMetrics()
        line_spacing = font.lineSpacing()
        leading = font.leading()
        height = line_spacing + max(4, leading)
        viewport = self._available_tree.viewport()
        viewport_width = viewport.width() if viewport is not None else 0
        width = max(220, viewport_width)
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
        cache_key = (entry.node_type, entry.icon_path or "", icon_size)
        cached = self._icon_cache.get(cache_key)
        if cached is not None:
            return cached

        if entry.icon_path:
            icon = self._load_icon_from_path(entry.icon_path, icon_size)
            if icon is not None:
                self._icon_cache[cache_key] = icon
                return icon

        pixmap = self._create_entry_pixmap(entry)
        icon = QIcon(pixmap)
        self._icon_cache[cache_key] = icon
        return icon

    def _load_icon_from_path(self, path: str, size: int) -> Optional[QIcon]:
        file_info = QFileInfo(path)
        if not file_info.exists():
            return None
        icon = self._file_icon_provider.icon(file_info)
        if icon.isNull():
            return None
        pixmap = icon.pixmap(QSize(size, size))
        if pixmap.isNull():
            return None
        return QIcon(pixmap)

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
        if entry.tool_name:
            lines.append(f"ツール: {entry.tool_name}")
        if entry.version_label:
            lines.append(f"バージョン: {entry.version_label}")
        lines.append(f"タイプ: {entry.node_type}")
        if entry.genre:
            lines.append(f"ジャンル: {entry.genre}")
        if entry.keywords:
            lines.append("キーワード: " + ", ".join(entry.keywords))
        return "\n".join(lines)

    def _update_item_texts(self) -> None:
        for entry, item in self._entry_items:
            item.setText(self._format_entry_text(entry))
        self._available_tree.doItemsLayout()

    def _update_summary_label(self, visible_count: Optional[int] = None) -> None:
        if self._result_summary_label is None:
            return
        if visible_count is None:
            visible_count = sum(
                1
                for entry, item in self._entry_items
                if self._is_item_visible(item)
            )
        self._visible_entry_count = visible_count
        if self._current_genre:
            total = self._view_model.genre_total(self._current_genre)
            text = f"{visible_count} 件 / {total} 件（ジャンル: {self._current_genre}）"
        else:
            text = f"{visible_count} 件 / 全 {self._total_entry_count} 件"
        self._result_summary_label.setText(text)

    def _update_parent_labels(
        self,
        visible_counts: Optional[Dict[str, int]] = None,
        total_counts: Optional[Dict[str, int]] = None,
    ) -> None:
        if visible_counts is None or total_counts is None:
            visible_counts = {}
            total_counts = {}
            for entry, _ in self._entry_items:
                total_counts[entry.genre] = total_counts.get(entry.genre, 0) + 1
                visible_counts[entry.genre] = visible_counts.get(entry.genre, 0) + 1
        for genre, genre_item in self._genre_items.items():
            visible = visible_counts.get(genre, 0)
            total = total_counts.get(genre, 0)
            genre_item.setText(f"{genre} ({visible} / {total})")

    def _update_tool_group_labels(
        self,
        visible_counts: Dict[Tuple[str, str], int],
        total_counts: Dict[Tuple[str, str], int],
    ) -> None:
        for group_key, group_item in self._tool_group_items.items():
            tool_name = group_item.data(Qt.UserRole + 4)
            label = str(tool_name) if tool_name is not None else group_item.text()
            visible = visible_counts.get(group_key, 0)
            total = total_counts.get(group_key, 0)
            group_item.setText(f"{label} ({visible} / {total})")

    def _resolve_tool_group_item(
        self,
        entry: NodeCatalogEntry,
        genre_item: QStandardItem,
    ) -> Optional[QStandardItem]:
        group_key = self._tool_group_key(entry)
        if group_key is None:
            return None
        group_item = self._tool_group_items.get(group_key)
        if group_item is None:
            group_item = QStandardItem(group_key[1])
            group_item.setEditable(False)
            group_item.setSelectable(True)
            group_item.setData(group_key[1], Qt.UserRole + 4)
            font = QFont()
            font.setBold(True)
            group_item.setFont(font)
            genre_item.appendRow(group_item)
            self._tool_group_items[group_key] = group_item
        return group_item

    def _tool_group_key(self, entry: NodeCatalogEntry) -> Optional[Tuple[str, str]]:
        tool_name = (entry.tool_name or "").strip()
        if not tool_name:
            return None
        return (entry.genre, tool_name)

    def _entry_from_item(self, item: Optional[QStandardItem]) -> Optional[NodeCatalogEntry]:
        if item is None:
            return None
        entry = item.data(Qt.UserRole + 3)
        return entry if isinstance(entry, NodeCatalogEntry) else None

    def _is_item_visible(self, item: QStandardItem) -> bool:
        if item is None:
            return False
        index = item.index()
        parent = index.parent()
        if self._available_tree.isRowHidden(index.row(), parent):
            return False
        if parent.isValid() and self._available_tree.isRowHidden(parent.row(), parent.parent()):
            return False
        return True

    def _connect_tree_selection_model(self) -> None:
        if self._tree_selection_model is not None and self._tree_selection_connected:
            self._tree_selection_model.selectionChanged.disconnect(
                self._on_tree_selection_changed
            )
            self._tree_selection_connected = False
        self._tree_selection_model = self._available_tree.selectionModel()
        if self._tree_selection_model is not None:
            self._tree_selection_model.selectionChanged.connect(
                self._on_tree_selection_changed
            )
            self._tree_selection_connected = True

    def _guess_genre(self, node_type: str) -> str:
        normalized = node_type.strip()
        if normalized.startswith("tool-environment:") or normalized.startswith("sotugyo.tooling"):
            return "ツール環境"
        if normalized.startswith("sotugyo.demo."):
            return "ワークフロー"
        if normalized.startswith("sotugyo.memo."):
            return "メモ"
        return "その他"
