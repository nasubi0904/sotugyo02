"""プラグイン管理ダイアログ。"""

from __future__ import annotations

from typing import Optional

from qtpy import QtCore, QtWidgets

Qt = QtCore.Qt
QComboBox = QtWidgets.QComboBox
QDialog = QtWidgets.QDialog
QDialogButtonBox = QtWidgets.QDialogButtonBox
QGroupBox = QtWidgets.QGroupBox
QHBoxLayout = QtWidgets.QHBoxLayout
QLabel = QtWidgets.QLabel
QMessageBox = QtWidgets.QMessageBox
QPushButton = QtWidgets.QPushButton
QTreeWidget = QtWidgets.QTreeWidget
QTreeWidgetItem = QtWidgets.QTreeWidgetItem
QVBoxLayout = QtWidgets.QVBoxLayout
QWidget = QtWidgets.QWidget

from ...domain.tooling import RezPackageSpec, ToolEnvironmentService


class PluginManagerDialog(QDialog):
    """ツールパッケージごとのプラグインを管理する。"""

    def __init__(
        self, service: ToolEnvironmentService, parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._package_combo: Optional[QComboBox] = None
        self._plugin_list: Optional[QTreeWidget] = None
        self._status_label: Optional[QLabel] = None
        self._packages: list[RezPackageSpec] = []

        self.setWindowTitle("プラグインの管理")
        self.resize(560, 420)

        self._build_ui()
        self._refresh_package_list()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        description = QLabel(
            "ツール環境設定で追加されたパッケージごとに、"
            "appdata/local/KDMplugins へ配置するプラグインを管理します。",
            self,
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        package_box = QGroupBox("対象パッケージ", self)
        package_layout = QHBoxLayout(package_box)
        package_layout.setContentsMargins(10, 8, 10, 8)
        package_label = QLabel("パッケージ:", package_box)
        package_combo = QComboBox(package_box)
        package_combo.currentIndexChanged.connect(self._refresh_plugin_list)
        package_layout.addWidget(package_label)
        package_layout.addWidget(package_combo, 1)
        layout.addWidget(package_box)
        self._package_combo = package_combo

        plugin_list = QTreeWidget(self)
        plugin_list.setColumnCount(2)
        plugin_list.setHeaderLabels(["プラグイン", "状態"])
        plugin_list.setRootIsDecorated(False)
        plugin_list.setAlternatingRowColors(True)
        plugin_list.setUniformRowHeights(True)
        plugin_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        plugin_list.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        layout.addWidget(plugin_list, 1)
        self._plugin_list = plugin_list

        button_row = QHBoxLayout()
        add_button = QPushButton("追加", self)
        add_button.clicked.connect(self._handle_add_plugin)
        edit_button = QPushButton("編集", self)
        edit_button.clicked.connect(self._handle_edit_plugin)
        button_row.addWidget(add_button)
        button_row.addWidget(edit_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        status_label = QLabel("プラグイン数: 0", self)
        status_label.setObjectName("statusLabel")
        layout.addWidget(status_label)
        self._status_label = status_label

        buttons = QDialogButtonBox(QDialogButtonBox.Close, Qt.Horizontal, self)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _refresh_package_list(self) -> None:
        if self._package_combo is None:
            return
        self._package_combo.blockSignals(True)
        self._package_combo.clear()
        try:
            self._packages = self._service.list_rez_packages()
        except OSError as exc:
            self._packages = []
            QMessageBox.critical(self, "エラー", f"パッケージの読み込みに失敗しました: {exc}")
        if not self._packages:
            self._package_combo.addItem("登録済みパッケージがありません")
            self._package_combo.setEnabled(False)
        else:
            for package in self._packages:
                self._package_combo.addItem(self._format_package_label(package))
            self._package_combo.setEnabled(True)
        self._package_combo.blockSignals(False)
        self._refresh_plugin_list()

    def _refresh_plugin_list(self) -> None:
        if self._plugin_list is None:
            return
        self._plugin_list.clear()
        selected = self._current_package()
        if selected is None:
            self._update_status(0)
            return
        self._update_status(0)
        placeholder = QTreeWidgetItem(["プラグインは未登録です。", "-"])
        placeholder.setFlags(QtCore.Qt.ItemIsEnabled)
        self._plugin_list.addTopLevelItem(placeholder)

    def _current_package(self) -> Optional[RezPackageSpec]:
        if self._package_combo is None:
            return None
        index = self._package_combo.currentIndex()
        if index < 0:
            return None
        if index >= len(self._packages):
            return None
        return self._packages[index]

    def _update_status(self, count: int) -> None:
        if self._status_label is None:
            return
        self._status_label.setText(f"プラグイン数: {count}")

    @staticmethod
    def _format_package_label(package: RezPackageSpec) -> str:
        if package.version:
            return f"{package.name} ({package.version})"
        return package.name

    def _handle_add_plugin(self) -> None:
        QMessageBox.information(self, "追加", "プラグイン追加は準備中です。")

    def _handle_edit_plugin(self) -> None:
        QMessageBox.information(self, "編集", "プラグイン編集は準備中です。")
