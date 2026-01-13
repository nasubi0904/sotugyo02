"""ツール起動環境の構成ダイアログ。"""

from __future__ import annotations

from typing import Optional

from qtpy import QtCore, QtWidgets

Qt = QtCore.Qt
QDialog = QtWidgets.QDialog
QDialogButtonBox = QtWidgets.QDialogButtonBox
QLabel = QtWidgets.QLabel
QVBoxLayout = QtWidgets.QVBoxLayout
QWidget = QtWidgets.QWidget

from ...domain.tooling import ToolEnvironmentService


class ToolEnvironmentManagerDialog(QDialog):
    """ツール起動環境の構成を行うダイアログ。"""

    def __init__(self, service: ToolEnvironmentService, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._service = service
        self._refresh_on_accept = False

        self.setWindowTitle("ツール起動環境の構成")
        self.resize(520, 420)

        self._build_ui()

    def refresh_requested(self) -> bool:
        return self._refresh_on_accept

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        description = QLabel("この画面は再構成中です。", self)
        description.setWordWrap(True)
        layout.addWidget(description)
        layout.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.Close, Qt.Horizontal, self)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
