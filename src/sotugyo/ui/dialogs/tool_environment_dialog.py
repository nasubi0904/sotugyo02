"""ツール起動環境の構成ダイアログ。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Optional

from qtpy import QtCore, QtWidgets

Qt = QtCore.Qt
QDialog = QtWidgets.QDialog
QDialogButtonBox = QtWidgets.QDialogButtonBox
QFormLayout = QtWidgets.QFormLayout
QHBoxLayout = QtWidgets.QHBoxLayout
QLabel = QtWidgets.QLabel
QLineEdit = QtWidgets.QLineEdit
QListWidget = QtWidgets.QListWidget
QListWidgetItem = QtWidgets.QListWidgetItem
QPushButton = QtWidgets.QPushButton
QComboBox = QtWidgets.QComboBox
QVBoxLayout = QtWidgets.QVBoxLayout
QWidget = QtWidgets.QWidget

from ...domain.tooling.models import RezPackageSpec
from ...domain.tooling.services.colorspace import ColorSpaceCandidate
from ...domain.tooling import ToolEnvironmentService
from ...infrastructure.paths.storage import get_tool_environment_dir


class ToolEnvironmentManagerDialog(QDialog):
    """ツール起動環境の構成を行うダイアログ。"""

    def __init__(self, service: ToolEnvironmentService, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._service = service
        self._refresh_on_accept = False
        self._environment_dir = get_tool_environment_dir()
        self._environment_items: list[Path] = []

        self.setWindowTitle("ツール起動環境の構成")
        self.resize(760, 520)

        self._build_ui()
        self._load_environment_list()

    def refresh_requested(self) -> bool:
        return self._refresh_on_accept

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        description = QLabel(
            "ツールパッケージをもとに起動環境を構成し、KDMenvs に保存された環境を一覧します。",
            self,
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        list_label = QLabel("現在参照可能な環境 (KDMenvs)", self)
        layout.addWidget(list_label)

        self._environment_list = QListWidget(self)
        self._environment_list.itemSelectionChanged.connect(self._update_edit_state)
        layout.addWidget(self._environment_list, 1)

        action_layout = QHBoxLayout()
        self._add_button = QPushButton("追加", self)
        self._add_button.clicked.connect(self._open_add_dialog)
        action_layout.addWidget(self._add_button)

        self._edit_button = QPushButton("編集", self)
        self._edit_button.setEnabled(False)
        self._edit_button.clicked.connect(self._open_edit_dialog)
        action_layout.addWidget(self._edit_button)
        action_layout.addStretch(1)
        layout.addLayout(action_layout)

        buttons = QDialogButtonBox(QDialogButtonBox.Close, Qt.Horizontal, self)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_environment_list(self) -> None:
        self._environment_dir.mkdir(parents=True, exist_ok=True)
        self._environment_list.clear()
        self._environment_items.clear()

        files = self._collect_environment_files(self._environment_dir)
        if not files:
            placeholder = QListWidgetItem("環境がありません", self._environment_list)
            placeholder.setFlags(Qt.NoItemFlags)
            self._update_edit_state()
            return

        for entry in files:
            item = QListWidgetItem(entry.stem, self._environment_list)
            item.setData(Qt.UserRole, entry)
            self._environment_items.append(entry)
        self._environment_list.setCurrentRow(0)
        self._update_edit_state()

    @staticmethod
    def _collect_environment_files(root: Path) -> list[Path]:
        if not root.exists():
            return []
        try:
            entries = [entry for entry in root.iterdir() if entry.is_file()]
        except OSError:
            return []
        preferred = [
            entry
            for entry in entries
            if entry.suffix.lower() in {".json", ".yml", ".yaml", ".toml"}
        ]
        return sorted(preferred or entries)

    def _selected_environment_path(self) -> Optional[Path]:
        selected = self._environment_list.currentItem()
        if selected is None:
            return None
        data = selected.data(Qt.UserRole)
        if isinstance(data, Path):
            return data
        return None

    def _update_edit_state(self) -> None:
        self._edit_button.setEnabled(self._selected_environment_path() is not None)

    def _open_add_dialog(self) -> None:
        dialog = ToolEnvironmentEditorDialog(
            service=self._service,
            environment_dir=self._environment_dir,
            environment_path=None,
            parent=self,
        )
        dialog.exec()

    def _open_edit_dialog(self) -> None:
        path = self._selected_environment_path()
        if path is None:
            return
        dialog = ToolEnvironmentEditorDialog(
            service=self._service,
            environment_dir=self._environment_dir,
            environment_path=path,
            parent=self,
        )
        dialog.exec()


class ToolEnvironmentEditorDialog(QDialog):
    """ツール環境定義の編集ダイアログ。"""

    def __init__(
        self,
        *,
        service: ToolEnvironmentService,
        environment_dir: Path,
        environment_path: Optional[Path],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._environment_dir = environment_dir
        self._environment_path = environment_path

        self.setWindowTitle("ツール環境の編集")
        self.resize(640, 480)

        self._build_ui()
        self._populate_packages()
        self._load_existing()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        description = QLabel(
            "ツールパッケージと色空間を選び、環境変数と起動引数コネクタを定義します。",
            self,
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)

        self._name_edit = QLineEdit(self)
        self._name_edit.setPlaceholderText("例: sRGB 環境")
        form.addRow("環境名", self._name_edit)

        self._package_combo = QComboBox(self)
        self._package_combo.currentIndexChanged.connect(self._on_package_changed)
        form.addRow("ツールパッケージ", self._package_combo)

        self._colorspace_combo = QComboBox(self)
        form.addRow("色空間 (環境変数名)", self._colorspace_combo)

        self._arg_connector = QLineEdit(self)
        self._arg_connector.setPlaceholderText("例: --colorspace {COLORSPACE}")
        form.addRow("起動引数コネクタ", self._arg_connector)

        layout.addLayout(form)

        hint = QLabel(
            "選択したツールパッケージを走査し、色空間に該当する候補を自動で列挙します。",
            self,
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        button_layout = QHBoxLayout()
        self._create_button = QPushButton("環境作成", self)
        self._create_button.clicked.connect(self._print_environment)
        button_layout.addWidget(self._create_button)
        button_layout.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.Close, Qt.Horizontal, self)
        buttons.rejected.connect(self.reject)
        button_layout.addWidget(buttons)
        layout.addLayout(button_layout)

    def _populate_packages(self) -> None:
        self._package_combo.clear()
        packages = self._service.list_rez_packages()
        if not packages:
            self._package_combo.addItem("パッケージがありません", None)
            self._package_combo.setEnabled(False)
            self._set_colorspace_options([])
            return
        for spec in sorted(packages, key=lambda item: (item.name, item.version or "")):
            label = f"{spec.name} ({spec.version})" if spec.version else spec.name
            self._package_combo.addItem(label, spec)
        self._package_combo.setEnabled(True)
        self._on_package_changed(0)

    def _load_existing(self) -> None:
        if self._environment_path is None:
            self._name_edit.setText("")
            return
        self._name_edit.setText(self._environment_path.stem)

    def _on_package_changed(self, index: int) -> None:
        spec = self._package_combo.itemData(index)
        if not isinstance(spec, RezPackageSpec):
            self._set_colorspace_options([])
            return
        candidates = self._service.list_colorspace_candidates(spec)
        self._set_colorspace_options(candidates)

    def _set_colorspace_options(self, options: Iterable[ColorSpaceCandidate]) -> None:
        self._colorspace_combo.clear()
        normalized = list(options)
        if not normalized:
            self._colorspace_combo.addItem("色空間が見つかりません", None)
            self._colorspace_combo.setEnabled(False)
            return
        for entry in normalized:
            index = self._colorspace_combo.count()
            self._colorspace_combo.addItem(entry.label, entry.env_var)
            if entry.config_path:
                self._colorspace_combo.setItemData(
                    index,
                    str(entry.config_path),
                    Qt.ToolTipRole,
                )
        self._colorspace_combo.setEnabled(True)

    def _print_environment(self) -> None:
        package = self._package_combo.currentData()
        colorspace = self._colorspace_combo.currentData()
        payload = {
            "name": self._name_edit.text().strip() or "無名の環境",
            "package": package.name if isinstance(package, RezPackageSpec) else None,
            "package_version": package.version if isinstance(package, RezPackageSpec) else None,
            "colorspace_env": colorspace,
            "launch_argument_connector": self._arg_connector.text().strip(),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
