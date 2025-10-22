"""GUI 全体で共有するスタイル定義。"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget


# 共通で用いるダークトーンのスタイルシート。スタート画面の印象を
# 維持しつつ、ダイアログやドックウィジェットでも同様のトーンを
# 再現する。
BASE_STYLE_SHEET = """
* {
    font-family: "Yu Gothic UI", "Meiryo", "Segoe UI", sans-serif;
    font-size: 13px;
    letter-spacing: 0.2px;
}
QWidget {
    background-color: #040b18;
    color: #e8eefc;
}
QMainWindow {
    background-color: #040b18;
}
QDialog {
    background-color: #040b18;
}
QDialog#appDialog {
    background: qradialgradient(
        cx: 0.28, cy: 0.08, radius: 1.2,
        fx: 0.3, fy: 0.1,
        stop: 0 #1f2741,
        stop: 0.6 #111a31,
        stop: 1 #050912
    );
}
QFrame#startCard,
QFrame#dialogCard,
QFrame#panelCard,
QFrame#inspectorSection {
    background-color: rgba(13, 23, 42, 0.94);
    border: 1px solid rgba(148, 178, 219, 0.25);
    border-radius: 16px;
}
QWidget#graphCentralContainer {
    background-color: rgba(9, 16, 30, 0.96);
    border: 1px solid rgba(148, 178, 219, 0.18);
    border-radius: 18px;
}
QWidget#dockContentContainer {
    background-color: transparent;
}
QLabel {
    color: #e8eefc;
    font-weight: 450;
    background-color: transparent;
}
QLabel[hint="secondary"] {
    color: #a9b6d8;
}
QLabel#panelTitle {
    font-weight: 650;
    font-size: 14px;
    letter-spacing: 0.4px;
}
QLabel#formLabel {
    color: #bac8ea;
    font-weight: 600;
}
QLabel#projectInfoLabel {
    color: #e8eefc;
    background-color: rgba(25, 36, 56, 0.76);
    border: 1px solid rgba(148, 178, 219, 0.2);
    border-radius: 14px;
    padding: 14px 16px;
}
QLabel#structureStatusLabel,
QLabel#structureWarningLabel {
    background-color: transparent;
    border-radius: 12px;
    border: none;
    padding: 0;
}
QLabel#structureStatusLabel[status="ok"],
QLabel#structureWarningLabel[status="ok"] {
    color: #34d399;
    background-color: rgba(34, 197, 94, 0.12);
    border: 1px solid rgba(34, 197, 94, 0.4);
    padding: 12px 14px;
}
QLabel#structureStatusLabel[status="error"],
QLabel#structureWarningLabel[status="error"] {
    color: #fca5a5;
    background-color: rgba(248, 113, 113, 0.14);
    border: 1px solid rgba(248, 113, 113, 0.45);
    padding: 12px 14px;
}
QLabel#structureStatusLabel[status="warning"],
QLabel#structureWarningLabel[status="warning"] {
    color: #fcd34d;
    background-color: rgba(251, 191, 36, 0.14);
    border: 1px solid rgba(251, 191, 36, 0.45);
    padding: 12px 14px;
}
QLineEdit,
QPlainTextEdit,
QTextEdit,
QComboBox,
QSpinBox,
QDoubleSpinBox,
QListWidget,
QTreeView,
QTableView,
QAbstractItemView,
QSlider,
QDialogButtonBox,
QTabWidget::pane {
    background-color: rgba(11, 20, 36, 0.94);
}
QLineEdit,
QPlainTextEdit,
QTextEdit,
QComboBox,
QSpinBox,
QDoubleSpinBox,
QAbstractSpinBox,
QListWidget,
QTreeView,
QTableView {
    border: 1px solid rgba(148, 178, 219, 0.35);
    border-radius: 12px;
    padding: 10px 14px;
    min-height: 38px;
    selection-background-color: rgba(99, 163, 255, 0.32);
    selection-color: #f8fbff;
}
QLineEdit:focus,
QPlainTextEdit:focus,
QTextEdit:focus,
QComboBox:focus,
QSpinBox:focus,
QDoubleSpinBox:focus,
QAbstractSpinBox:focus {
    border: 1px solid rgba(99, 163, 255, 0.85);
    background-color: rgba(23, 40, 74, 0.94);
}
QComboBox {
    padding-right: 36px;
}
QComboBox::drop-down {
    width: 32px;
    border-left: 1px solid rgba(148, 178, 219, 0.25);
    background-color: rgba(20, 33, 57, 0.92);
    border-top-right-radius: 12px;
    border-bottom-right-radius: 12px;
}
QComboBox::down-arrow {
    image: url(:/qt-project.org/styles/commonstyle/images/down_arrow.png);
    width: 12px;
    height: 12px;
}
QComboBox QAbstractItemView {
    background-color: rgba(11, 20, 36, 0.98);
    border: 1px solid rgba(148, 178, 219, 0.35);
    border-radius: 12px;
    padding: 6px;
    selection-background-color: rgba(99, 163, 255, 0.26);
}
QPushButton {
    background-color: rgba(82, 108, 182, 0.22);
    border: 1px solid rgba(118, 146, 212, 0.35);
    border-radius: 12px;
    color: #f0f4ff;
    padding: 10px 20px;
    font-weight: 600;
    min-height: 38px;
}
QPushButton:hover {
    background-color: rgba(99, 163, 255, 0.24);
    border: 1px solid rgba(99, 163, 255, 0.6);
}
QPushButton:pressed {
    background-color: rgba(37, 99, 235, 0.7);
}
QPushButton:disabled {
    background-color: rgba(91, 112, 165, 0.08);
    border: 1px solid rgba(118, 146, 212, 0.18);
    color: rgba(230, 234, 245, 0.4);
}
QPushButton#primaryActionButton {
    background-color: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 0,
        stop: 0 #2563eb,
        stop: 1 #6366f1
    );
    border: none;
    color: #f8fbff;
    padding: 12px 30px;
    font-size: 15px;
    border-radius: 14px;
    min-height: 44px;
}
QPushButton#primaryActionButton:hover {
    background-color: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 0,
        stop: 0 #1d4ed8,
        stop: 1 #4f46e5
    );
}
QPushButton#primaryActionButton:pressed {
    background-color: #1e3a8a;
}
QDialogButtonBox {
    border: none;
    padding: 0;
}
QDialogButtonBox QPushButton {
    min-width: 108px;
}
QListWidget {
    border-radius: 14px;
    padding: 10px;
}
QListWidget::item {
    border-radius: 10px;
    padding: 8px;
}
QListWidget::item:selected {
    background-color: rgba(99, 163, 255, 0.28);
}
QTabWidget::pane {
    border: 1px solid rgba(148, 178, 219, 0.22);
    border-radius: 14px;
    margin-top: 6px;
}
QTabBar::tab {
    background-color: rgba(19, 31, 55, 0.9);
    border: 1px solid rgba(148, 178, 219, 0.28);
    border-bottom: none;
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
    padding: 8px 18px;
    margin-right: 6px;
    color: #c9d5f5;
}
QTabBar::tab:selected {
    background-color: rgba(37, 55, 90, 0.96);
    color: #f8fbff;
}
QTabBar::tab:hover {
    background-color: rgba(99, 163, 255, 0.24);
}
QDockWidget {
    background-color: rgba(11, 20, 36, 0.96);
    border: 1px solid rgba(148, 178, 219, 0.28);
    border-radius: 14px;
}
QDockWidget QWidget {
    background-color: transparent;
}
QDockWidget::title {
    text-align: left;
    padding: 8px 16px;
    background-color: rgba(19, 31, 55, 0.92);
    border-bottom: 1px solid rgba(148, 178, 219, 0.2);
}
QMenuBar {
    background: transparent;
}
QMenuBar::item {
    padding: 8px 14px;
    color: #c9d5f5;
    border-radius: 8px;
}
QMenuBar::item:selected {
    background-color: rgba(99, 163, 255, 0.18);
}
QMenu {
    background-color: rgba(11, 20, 36, 0.98);
    border: 1px solid rgba(148, 178, 219, 0.32);
    border-radius: 12px;
}
QMenu::item {
    padding: 8px 20px;
    color: #eef2ff;
}
QMenu::item:selected {
    background-color: rgba(99, 163, 255, 0.22);
}
QToolTip {
    color: #0b1220;
    background-color: #f1f5ff;
    border: 1px solid rgba(77, 99, 143, 0.3);
    padding: 8px 12px;
    border-radius: 10px;
}
QScrollBar:horizontal, QScrollBar:vertical {
    background: transparent;
    border: none;
    margin: 8px;
}
QScrollBar::handle:horizontal, QScrollBar::handle:vertical {
    background: rgba(148, 178, 219, 0.4);
    border-radius: 6px;
    min-height: 24px;
}
QScrollBar::handle:horizontal:hover, QScrollBar::handle:vertical:hover {
    background: rgba(99, 163, 255, 0.6);
}
QScrollBar::add-line, QScrollBar::sub-line {
    background: none;
}
QProgressBar {
    background-color: rgba(13, 23, 42, 0.92);
    border: 1px solid rgba(148, 178, 219, 0.28);
    border-radius: 12px;
    text-align: center;
    color: #f0f4ff;
    min-height: 16px;
}
QProgressBar::chunk {
    background-color: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 0,
        stop: 0 #2563eb,
        stop: 1 #6366f1
    );
    border-radius: 10px;
}
"""


START_WINDOW_STYLE = """
QWidget#startRoot {
    background: qradialgradient(
        cx: 0.3, cy: 0.08, radius: 1.2,
        fx: 0.32, fy: 0.12,
        stop: 0 #1f2a3f,
        stop: 0.55 #111a31,
        stop: 1 #040b18
    );
}
QFrame#startCard {
    border-radius: 20px;
    border: 1px solid rgba(148, 178, 219, 0.28);
}
QLabel#startTitle {
    font-size: 24px;
    font-weight: 700;
    letter-spacing: 0.6px;
    color: #f8fbff;
}
QLabel#startDescription {
    color: #b0bddd;
    font-size: 13px;
}
"""


def apply_base_style(widget: QWidget, extra: str | None = None) -> None:
    """ウィジェットに共通スタイルを適用する。"""

    stylesheet = BASE_STYLE_SHEET
    if extra:
        stylesheet = f"{stylesheet}\n{extra}"
    widget.setStyleSheet(stylesheet)
