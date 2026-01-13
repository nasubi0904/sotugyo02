"""ノードエディタ向けコンテンツブラウザコンポーネント。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

from qtpy import QtCore, QtGui, QtWidgets

Qt = QtCore.Qt
Signal = QtCore.Signal
QFileInfo = QtCore.QFileInfo
QSize = QtCore.QSize
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
QFileIconProvider = QtWidgets.QFileIconProvider
QFrame = QtWidgets.QFrame
QHBoxLayout = QtWidgets.QHBoxLayout
QInputDialog = QtWidgets.QInputDialog
QLabel = QtWidgets.QLabel
QLineEdit = QtWidgets.QLineEdit
QListView = QtWidgets.QListView
QMenu = QtWidgets.QMenu
QMessageBox = QtWidgets.QMessageBox
QPushButton = QtWidgets.QPushButton
QSizePolicy = QtWidgets.QSizePolicy
QSlider = QtWidgets.QSlider
QSpinBox = QtWidgets.QSpinBox
QSpacerItem = QtWidgets.QSpacerItem
QStyle = QtWidgets.QStyle
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

    def searchable_text(self) -> str:
        parts = [self.title, self.subtitle, self.node_type, *self.keywords]
        return "\n".join(part.lower() for part in parts if part)


@dataclass
class CatalogItem:
    """アイコン一覧に表示するアイテムの情報。"""

    kind: str
    title: str
    entry: Optional[NodeCatalogEntry] = None
    folder: Optional["CatalogFolder"] = None

    def is_folder(self) -> bool:
        return self.kind == "folder"

    def is_entry(self) -> bool:
        return self.kind == "entry"


@dataclass
class CatalogFolder:
    """コンテンツブラウザ内の仮想フォルダ。"""

    name: str
    parent: Optional["CatalogFolder"]
    items: List[CatalogItem] = field(default_factory=list)

    def path_labels(self) -> List[str]:
        labels = []
        current: Optional[CatalogFolder] = self
        while current is not None and current.parent is not None:
            labels.append(current.name)
            current = current.parent
        return list(reversed(labels))

    def iter_items(self) -> Iterator[CatalogItem]:
        for item in self.items:
            yield item
            if item.folder is not None:
                yield from item.folder.iter_items()


class CatalogIconView(QListView):
    """フォルダへのドロップを扱うアイコンビュー。"""

    folder_drop_requested = Signal(object, list)

    def dropEvent(self, event: QtGui.QDropEvent) -> None:  # noqa: D401
        """ドロップ先がフォルダの場合は移動を要求する。"""

        model = self.model()
        index = self.indexAt(self._event_pos(event))
        if model is not None and index.isValid():
            item = model.itemFromIndex(index)
            catalog_item = item.data(Qt.UserRole)
            if isinstance(catalog_item, CatalogItem) and catalog_item.is_folder():
                selected_items = self._selected_catalog_items()
                if selected_items:
                    self.folder_drop_requested.emit(catalog_item.folder, selected_items)
                    event.acceptProposedAction()
                    return
        super().dropEvent(event)

    def _event_pos(self, event: QtGui.QDropEvent) -> QtCore.QPoint:
        position = getattr(event, "position", None)
        if callable(position):
            return position().toPoint()
        return event.pos()

    def _selected_catalog_items(self) -> List[CatalogItem]:
        selection = self.selectionModel()
        if selection is None:
            return []
        items: List[CatalogItem] = []
        for index in selection.selectedIndexes():
            model = self.model()
            if model is None:
                continue
            item = model.itemFromIndex(index)
            catalog_item = item.data(Qt.UserRole)
            if isinstance(catalog_item, CatalogItem):
                items.append(catalog_item)
        return items


class NodeContentBrowser(QWidget):
    """ノード追加と検索をまとめたコンテンツブラウザ。"""

    node_type_requested = Signal(str)
    search_submitted = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._search_line: QLineEdit = QLineEdit(self)
        self._available_view: CatalogIconView = CatalogIconView(self)
        self._available_model: QStandardItemModel = QStandardItemModel(self)
        self._icon_size_slider: QSlider = QSlider(Qt.Horizontal, self)
        self._icon_size_spin: QSpinBox = QSpinBox(self)
        self._icon_size_levels: Dict[int, int] = {
            1: 40,
            2: 48,
            3: 64,
            4: 80,
            5: 96,
            6: 120,
        }
        self._icon_size_default_level: int = 3
        self._icon_size_level: int = self._icon_size_default_level
        self._icon_size: int = self._icon_size_from_level(self._icon_size_level)
        self._icon_control_container: Optional[QWidget] = None
        self._outer_layout: Optional[QVBoxLayout] = None
        self._card_frame: Optional[QFrame] = None
        self._card_layout: Optional[QVBoxLayout] = None
        self._control_header: Optional[QWidget] = None
        self._control_header_layout: Optional[QBoxLayout] = None
        self._control_header_spacer: Optional[QSpacerItem] = None
        self._result_summary_label: Optional[QLabel] = None
        self._path_label: Optional[QLabel] = None
        self._up_folder_button: Optional[QPushButton] = None
        self._new_folder_button: Optional[QPushButton] = None
        self._icon_cache: Dict[Tuple[str, str, int], QIcon] = {}
        self._file_icon_provider: QFileIconProvider = QFileIconProvider()
        self._folder_icon: QIcon = self.style().standardIcon(QStyle.SP_DirIcon)
        self._root_folder: CatalogFolder = CatalogFolder("root", None)
        self._current_folder: CatalogFolder = self._root_folder
        self._search_keyword: str = ""
        self._clipboard_items: List[CatalogItem] = []
        self._total_entry_count: int = 0
        self._visible_entry_count: int = 0
        self._protected_folder_names: Tuple[str, ...] = ("ワークフロー", "環境定義")

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
        self._total_entry_count = len(catalog_entries)
        self._sync_catalog_entries(catalog_entries)
        self._refresh_view()

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
        model = self._available_model
        for row in range(model.rowCount()):
            item = model.item(row)
            if item is None:
                continue
            catalog_item = item.data(Qt.UserRole)
            if isinstance(catalog_item, CatalogItem) and catalog_item.entry:
                return catalog_item.entry.node_type
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
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(6)
        self._card_frame = card
        self._card_layout = card_layout

        path_layout = QHBoxLayout()
        path_layout.setContentsMargins(0, 0, 0, 0)
        path_layout.setSpacing(4)

        self._path_label = QLabel("/", card)
        self._path_label.setObjectName("contentPathLabel")
        self._path_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        path_layout.addWidget(self._path_label, 1)

        card_layout.addLayout(path_layout)

        search_layout = QHBoxLayout()
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(4)

        self._search_line.setPlaceholderText("検索")
        self._search_line.setClearButtonEnabled(True)
        search_layout.addWidget(self._search_line, 1)

        card_layout.addLayout(search_layout)

        self._configure_icon_view(self._available_view)

        icon_control = self._create_icon_size_control(card)
        summary_widget = self._create_result_summary(card)
        header_container = QWidget(card)
        header_container_layout = QHBoxLayout(header_container)
        header_container_layout.setContentsMargins(0, 0, 0, 0)
        header_container_layout.setSpacing(6)
        header_container_layout.addWidget(summary_widget)
        spacer = QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum)
        header_container_layout.addItem(spacer)
        up_button = QPushButton("上へ", card)
        up_button.setEnabled(False)
        self._up_folder_button = up_button
        header_container_layout.addWidget(up_button)
        new_folder_button = QPushButton("新規フォルダ", card)
        self._new_folder_button = new_folder_button
        header_container_layout.addWidget(new_folder_button)
        header_container_layout.addWidget(icon_control)
        self._control_header = header_container
        self._control_header_layout = header_container_layout
        self._control_header_spacer = spacer

        card_layout.addWidget(header_container)
        card_layout.addWidget(self._available_view, 1)

        outer_layout.addWidget(card, 1)

    def _configure_icon_view(self, widget: CatalogIconView) -> None:
        widget.setObjectName("contentIconGrid")
        widget.setModel(self._available_model)
        widget.setViewMode(QListView.IconMode)
        widget.setWrapping(True)
        widget.setResizeMode(QListView.Adjust)
        widget.setMovement(QListView.Snap)
        widget.setUniformItemSizes(False)
        widget.setSelectionMode(QAbstractItemView.ExtendedSelection)
        widget.setSelectionBehavior(QAbstractItemView.SelectItems)
        widget.setDragDropMode(QAbstractItemView.InternalMove)
        widget.setDragEnabled(True)
        widget.setAcceptDrops(True)
        widget.setDropIndicatorShown(True)
        widget.setSpacing(12)
        widget.setContextMenuPolicy(Qt.CustomContextMenu)
        widget.setIconSize(QSize(self._current_icon_size_value(), self._current_icon_size_value()))
        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._apply_icon_size()

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

        summary = QLabel("0 件", container)
        summary.setObjectName("contentSummaryLabel")
        summary.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._result_summary_label = summary

        layout.addWidget(summary)

        return container

    def _connect_signals(self) -> None:
        self._search_line.textChanged.connect(self._apply_filter)
        self._search_line.returnPressed.connect(self._on_search_submitted)
        self._available_view.doubleClicked.connect(self._on_item_double_clicked)
        self._available_view.folder_drop_requested.connect(self._on_folder_drop_requested)
        self._available_view.customContextMenuRequested.connect(self._open_context_menu)
        self._available_model.rowsMoved.connect(self._on_rows_moved)
        self._icon_size_slider.valueChanged.connect(self._on_icon_size_changed)
        self._icon_size_spin.valueChanged[int].connect(self._on_icon_size_changed)
        if self._up_folder_button is not None:
            self._up_folder_button.clicked.connect(self._move_to_parent_folder)
        if self._new_folder_button is not None:
            self._new_folder_button.clicked.connect(self._create_new_folder)

    def _apply_filter(self) -> None:
        self._search_keyword = self._search_line.text().strip().lower()
        self._refresh_view()
        self._update_drag_drop_state()

    def _on_search_submitted(self) -> None:
        self.search_submitted.emit(self._search_line.text())

    def _on_item_double_clicked(self, index: QtCore.QModelIndex) -> None:
        item = self._available_model.itemFromIndex(index)
        if item is None:
            return
        catalog_item = item.data(Qt.UserRole)
        if not isinstance(catalog_item, CatalogItem):
            return
        if catalog_item.is_folder() and catalog_item.folder is not None:
            self._open_folder(catalog_item.folder)
            return
        if catalog_item.entry is not None:
            self.node_type_requested.emit(catalog_item.entry.node_type)

    def _open_context_menu(self, pos: QtCore.QPoint) -> None:
        selected_items = self._selected_catalog_items()
        clicked_index = self._available_view.indexAt(pos)
        if clicked_index.isValid() and not selected_items:
            item = self._available_model.itemFromIndex(clicked_index)
            catalog_item = item.data(Qt.UserRole) if item else None
            if isinstance(catalog_item, CatalogItem):
                selected_items = [catalog_item]
        menu = QMenu(self)
        if not clicked_index.isValid():
            paste_action = menu.addAction("貼り付け")
            paste_action.setEnabled(self._can_paste_to_current_folder())
            action = menu.exec_(self._available_view.mapToGlobal(pos))
            if action == paste_action:
                self._paste_from_clipboard()
            return
        copy_action = menu.addAction("コピー")
        delete_action = menu.addAction("削除")
        protected_items = [item for item in selected_items if self._is_protected_folder(item)]
        if protected_items:
            delete_action.setEnabled(False)
        action = menu.exec_(self._available_view.mapToGlobal(pos))
        if action == copy_action:
            self._copy_selected_to_clipboard(selected_items)
        if action == delete_action and delete_action.isEnabled():
            self._confirm_delete_selected(selected_items)

    def _on_folder_drop_requested(
        self,
        target_folder: Optional[CatalogFolder],
        items: List[CatalogItem],
    ) -> None:
        if target_folder is None:
            return
        self._move_items_to_folder(items, target_folder)
        self._refresh_view()

    def _on_rows_moved(
        self,
        parent: QtCore.QModelIndex,
        start: int,
        end: int,
        destination: QtCore.QModelIndex,
        row: int,
    ) -> None:
        if self._search_keyword:
            return
        if parent.isValid() or destination.isValid():
            return
        self._sync_current_folder_order_from_model()

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
        self._available_view.setIconSize(icon_size)
        self._available_view.setGridSize(self._grid_size(icon_size_value))
        self._refresh_icons()
        tooltip = (
            f"表示サイズ: {icon_size_value}px"
            f" / {self._icon_size_level} 段階 ({len(self._icon_size_levels)}段階中)"
        )
        self._icon_size_slider.setToolTip(tooltip)
        self._icon_size_spin.setToolTip(tooltip)
        if self._result_summary_label is not None and self._visible_entry_count:
            self._update_summary_label()

    def _update_layout_for_size(self, size: QSize) -> None:
        width = size.width() if size is not None else self.width()
        self._adjust_control_header(width)
        self._apply_icon_size()

    def _adjust_control_header(self, width: int) -> None:
        if self._control_header_layout is None:
            return
        is_vertical = width < 720
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

    def _refresh_view(self) -> None:
        self._available_model.clear()
        items = self._current_display_items()
        for catalog_item in items:
            item = QStandardItem(self._format_item_text(catalog_item))
            item.setEditable(False)
            item.setData(catalog_item, Qt.UserRole)
            item.setTextAlignment(Qt.AlignHCenter | Qt.AlignTop)
            if catalog_item.is_folder():
                item.setIcon(self._folder_icon)
                item.setFlags(
                    Qt.ItemIsEnabled
                    | Qt.ItemIsSelectable
                    | Qt.ItemIsDragEnabled
                    | Qt.ItemIsDropEnabled
                )
            else:
                item.setIcon(self._icon_for_entry(catalog_item.entry))
                item.setFlags(
                    Qt.ItemIsEnabled
                    | Qt.ItemIsSelectable
                    | Qt.ItemIsDragEnabled
                )
            self._available_model.appendRow(item)
        self._update_path_label()
        self._update_summary_label()
        self._update_drag_drop_state()

    def _refresh_icons(self) -> None:
        for row in range(self._available_model.rowCount()):
            item = self._available_model.item(row)
            if item is None:
                continue
            catalog_item = item.data(Qt.UserRole)
            if not isinstance(catalog_item, CatalogItem):
                continue
            if catalog_item.is_folder():
                item.setIcon(self._folder_icon)
            else:
                item.setIcon(self._icon_for_entry(catalog_item.entry))

    def _update_drag_drop_state(self) -> None:
        filtered = bool(self._search_keyword)
        self._available_view.setDragEnabled(not filtered)
        self._available_view.setAcceptDrops(not filtered)
        self._available_view.setDropIndicatorShown(not filtered)

    def _current_display_items(self) -> List[CatalogItem]:
        items: List[CatalogItem] = []
        keyword = self._search_keyword
        for item in self._current_folder.items:
            if item.is_folder():
                if not keyword or self._folder_has_match(item.folder, keyword):
                    items.append(item)
            elif self._entry_matches(item.entry, keyword):
                items.append(item)
        return items

    def _folder_has_match(self, folder: Optional[CatalogFolder], keyword: str) -> bool:
        if folder is None:
            return False
        for item in folder.items:
            if item.is_folder():
                if self._folder_has_match(item.folder, keyword):
                    return True
            elif self._entry_matches(item.entry, keyword):
                return True
        return False

    def _entry_matches(self, entry: Optional[NodeCatalogEntry], keyword: str) -> bool:
        if entry is None:
            return False
        if not keyword:
            return True
        return keyword in entry.searchable_text()

    def _format_item_text(self, item: CatalogItem) -> str:
        if item.is_folder():
            return item.title
        entry = item.entry
        if entry is None:
            return item.title
        title = entry.title.strip()
        subtitle = entry.subtitle.strip()
        if title and subtitle:
            return f"{title}\n{subtitle}"
        return title or subtitle or entry.node_type.strip()

    def _update_summary_label(self) -> None:
        if self._result_summary_label is None:
            return
        visible_entries = 0
        visible_folders = 0
        for row in range(self._available_model.rowCount()):
            item = self._available_model.item(row)
            if item is None:
                continue
            catalog_item = item.data(Qt.UserRole)
            if isinstance(catalog_item, CatalogItem):
                if catalog_item.is_folder():
                    visible_folders += 1
                else:
                    visible_entries += 1
        total_entries = sum(1 for item in self._current_folder.items if item.is_entry())
        self._visible_entry_count = visible_entries
        text = (
            f"{visible_entries} 件 / {total_entries} 件"
            f"（フォルダ {visible_folders}）"
        )
        self._result_summary_label.setText(text)

    def _update_path_label(self) -> None:
        if self._path_label is None:
            return
        labels = self._current_folder.path_labels()
        if not labels:
            self._path_label.setText("")
        else:
            self._path_label.setText(" / ".join(labels))
        if self._up_folder_button is not None:
            self._up_folder_button.setEnabled(self._current_folder.parent is not None)

    def _selected_catalog_items(self) -> List[CatalogItem]:
        selection = self._available_view.selectionModel()
        if selection is None:
            return []
        items: List[CatalogItem] = []
        for index in selection.selectedIndexes():
            model_item = self._available_model.itemFromIndex(index)
            catalog_item = model_item.data(Qt.UserRole) if model_item else None
            if isinstance(catalog_item, CatalogItem):
                items.append(catalog_item)
        return items

    def _confirm_delete_selected(self, items: List[CatalogItem]) -> None:
        protected = [item for item in items if self._is_protected_folder(item)]
        if protected:
            QMessageBox.warning(
                self,
                "削除不可",
                "既定フォルダは削除できません。",
            )
            return
        folder_count = sum(1 for item in items if item.is_folder())
        entry_count = sum(1 for item in items if item.is_entry())
        message = self._delete_message(folder_count, entry_count)
        result = QMessageBox.question(
            self,
            "削除確認",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if result != QMessageBox.StandardButton.Yes:
            return
        self._delete_items(items)
        self._refresh_view()

    def _delete_message(self, folder_count: int, entry_count: int) -> str:
        parts = []
        if folder_count:
            parts.append(f"フォルダ {folder_count} 件")
        if entry_count:
            parts.append(f"アイテム {entry_count} 件")
        summary = "、".join(parts) if parts else "選択中の項目"
        return f"{summary}を削除します。よろしいですか？"

    def _delete_items(self, items: List[CatalogItem]) -> None:
        for item in items:
            if item in self._current_folder.items:
                self._current_folder.items.remove(item)

    def _is_protected_folder(self, item: CatalogItem) -> bool:
        if not item.is_folder():
            return False
        return item.title in self._protected_folder_names

    def _is_folder_protected(self, folder: Optional[CatalogFolder]) -> bool:
        current = folder
        while current is not None and current.parent is not None:
            if current.name in self._protected_folder_names:
                return True
            current = current.parent
        return False

    def _is_current_folder_protected(self) -> bool:
        return self._is_folder_protected(self._current_folder)

    def _move_to_parent_folder(self) -> None:
        if self._current_folder.parent is None:
            return
        self._current_folder = self._current_folder.parent
        self._refresh_view()

    def _open_folder(self, folder: CatalogFolder) -> None:
        self._current_folder = folder
        self._refresh_view()

    def _create_new_folder(self) -> None:
        if self._new_folder_button is None:
            return
        name, ok = QInputDialog.getText(
            self,
            "新規フォルダ",
            "フォルダ名を入力してください。",
        )
        if not ok:
            return
        name = name.strip()
        if not name:
            QMessageBox.warning(self, "入力エラー", "フォルダ名が空です。")
            return
        if any(
            item.is_folder() and item.title == name
            for item in self._current_folder.items
        ):
            QMessageBox.warning(self, "入力エラー", "同じ名前のフォルダが存在します。")
            return
        new_folder = CatalogFolder(name=name, parent=self._current_folder)
        new_item = CatalogItem(kind="folder", title=name, folder=new_folder)
        self._current_folder.items.append(new_item)
        self._refresh_view()

    def _copy_selected_to_clipboard(self, items: List[CatalogItem]) -> None:
        self._clipboard_items = list(items)
        QMessageBox.information(self, "コピー", "選択中の項目をコピーしました。")

    def _can_paste_to_current_folder(self) -> bool:
        return bool(self._clipboard_items) and not self._is_current_folder_protected()

    def _paste_from_clipboard(self) -> None:
        if self._is_current_folder_protected():
            QMessageBox.warning(
                self,
                "貼り付け不可",
                "既定フォルダ内には貼り付けできません。",
            )
            return
        if not self._clipboard_items:
            QMessageBox.information(self, "貼り付け", "貼り付ける項目がありません。")
            return
        self._copy_items_to_folder(self._clipboard_items, self._current_folder)
        self._refresh_view()

    def _move_items_to_folder(
        self,
        items: List[CatalogItem],
        target_folder: CatalogFolder,
    ) -> None:
        if not items:
            return
        moving_items = [item for item in items if item in self._current_folder.items]
        if not moving_items:
            return
        for item in moving_items:
            if item.is_folder() and item.folder is not None:
                if item.folder is target_folder or self._is_descendant_folder(target_folder, item.folder):
                    continue
            if item in target_folder.items:
                continue
            self._current_folder.items.remove(item)
            if item.is_folder() and item.folder is not None:
                item.folder.parent = target_folder
            target_folder.items.append(item)

    def _copy_items_to_folder(
        self,
        items: List[CatalogItem],
        target_folder: CatalogFolder,
    ) -> None:
        for item in items:
            if item.is_folder() and item.folder is not None:
                copied_folder = self._clone_folder(item.folder, target_folder)
                target_folder.items.append(
                    CatalogItem(kind="folder", title=copied_folder.name, folder=copied_folder)
                )
            elif item.entry is not None:
                target_folder.items.append(
                    CatalogItem(kind="entry", title=item.title, entry=item.entry)
                )

    def _clone_folder(self, source: CatalogFolder, parent: CatalogFolder) -> CatalogFolder:
        new_name = self._unique_folder_name(source.name, parent)
        new_folder = CatalogFolder(name=new_name, parent=parent)
        for item in source.items:
            if item.is_folder() and item.folder is not None:
                child_folder = self._clone_folder(item.folder, new_folder)
                new_folder.items.append(
                    CatalogItem(kind="folder", title=child_folder.name, folder=child_folder)
                )
            elif item.entry is not None:
                new_folder.items.append(
                    CatalogItem(kind="entry", title=item.title, entry=item.entry)
                )
        return new_folder

    def _unique_folder_name(self, base_name: str, parent: CatalogFolder) -> str:
        existing = {item.title for item in parent.items if item.is_folder()}
        if base_name not in existing:
            return base_name
        suffix = 1
        while True:
            candidate = f"{base_name} コピー{suffix}"
            if candidate not in existing:
                return candidate
            suffix += 1

    def _is_descendant_folder(
        self,
        target: CatalogFolder,
        candidate_parent: Optional[CatalogFolder],
    ) -> bool:
        current = target.parent
        while current is not None:
            if current is candidate_parent:
                return True
            current = current.parent
        return False

    def _sync_current_folder_order_from_model(self) -> None:
        new_order: List[CatalogItem] = []
        for row in range(self._available_model.rowCount()):
            item = self._available_model.item(row)
            if item is None:
                continue
            catalog_item = item.data(Qt.UserRole)
            if isinstance(catalog_item, CatalogItem):
                new_order.append(catalog_item)
        if new_order:
            self._current_folder.items = new_order

    def _sync_catalog_entries(self, entries: Sequence[NodeCatalogEntry]) -> None:
        if not self._root_folder.items:
            self._build_default_folders()

        entry_map = {entry.node_type: entry for entry in entries}
        existing_items = self._entry_items_by_type()

        for node_type, item in list(existing_items.items()):
            if node_type not in entry_map:
                self._remove_item_from_parent(item)

        for entry in entries:
            existing_item = existing_items.get(entry.node_type)
            if existing_item is not None:
                existing_item.entry = entry
                existing_item.title = entry.title or existing_item.title
                continue
            folder = self._select_default_folder(entry)
            folder_item = CatalogItem(kind="entry", title=entry.title or entry.node_type, entry=entry)
            folder.items.append(folder_item)

        if self._current_folder is None or self._current_folder.parent is None:
            self._current_folder = self._root_folder

    def _build_default_folders(self) -> None:
        self._root_folder = CatalogFolder("root", None)
        workflow = CatalogFolder("ワークフロー", self._root_folder)
        environment = CatalogFolder("環境定義", self._root_folder)
        self._root_folder.items = [
            CatalogItem(kind="folder", title=workflow.name, folder=workflow),
            CatalogItem(kind="folder", title=environment.name, folder=environment),
        ]
        self._current_folder = self._root_folder

    def _entry_items_by_type(self) -> Dict[str, CatalogItem]:
        items: Dict[str, CatalogItem] = {}
        for item in self._root_folder.iter_items():
            if item.entry is not None:
                items[item.entry.node_type] = item
        return items

    def _remove_item_from_parent(self, target: CatalogItem) -> None:
        for item in self._root_folder.iter_items():
            if item.folder is not None and target in item.folder.items:
                item.folder.items.remove(target)
                return
        if target in self._root_folder.items:
            self._root_folder.items.remove(target)

    def _select_default_folder(self, entry: NodeCatalogEntry) -> CatalogFolder:
        workflow, environment = self._default_folders()
        normalized = entry.node_type.lower()
        genre = entry.genre
        if genre == "ツール環境":
            return environment
        if genre in {"ワークフロー", "メモ"}:
            return workflow
        if "memo" in normalized or "date" in normalized:
            return workflow
        return workflow

    def _default_folders(self) -> Tuple[CatalogFolder, CatalogFolder]:
        workflow = self._find_folder("ワークフロー")
        environment = self._find_folder("環境定義")
        if workflow is None or environment is None:
            self._build_default_folders()
            workflow = self._find_folder("ワークフロー")
            environment = self._find_folder("環境定義")
        if workflow is None or environment is None:
            raise RuntimeError("既定フォルダの初期化に失敗しました。")
        return workflow, environment

    def _find_folder(self, name: str) -> Optional[CatalogFolder]:
        for item in self._root_folder.items:
            if item.is_folder() and item.folder is not None and item.folder.name == name:
                return item.folder
        return None

    def _grid_size(self, icon_size: int) -> QSize:
        font: QFontMetrics = self._available_view.fontMetrics()
        line_spacing = font.lineSpacing()
        text_height = line_spacing * 2
        height = icon_size + text_height + 16
        text_width = font.horizontalAdvance("M" * 12)
        width = max(icon_size + 24, text_width)
        return QSize(width, height)

    def _icon_size_from_level(self, level: int) -> int:
        return self._icon_size_levels.get(
            level,
            self._icon_size_levels.get(self._icon_size_default_level, 64),
        )

    def _current_icon_size_value(self) -> int:
        return self._icon_size

    def _icon_for_entry(self, entry: Optional[NodeCatalogEntry]) -> QIcon:
        if entry is None:
            return QIcon()
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

    def _guess_genre(self, node_type: str) -> str:
        normalized = node_type.strip()
        if normalized.startswith("tool-environment:") or normalized.startswith("sotugyo.tooling"):
            return "ツール環境"
        if normalized.startswith("sotugyo.demo."):
            return "ワークフロー"
        if normalized.startswith("sotugyo.memo.") or normalized.startswith("sotugyo.date."):
            return "メモ"
        return "その他"
