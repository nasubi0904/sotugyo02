"""GUI 全体で共有するスタイル定義。"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget


# 共通で用いるダークトーンのスタイルシート。スタート画面の印象を
# 維持しつつ、ダイアログやドックウィジェットでも同様のトーンを
# 再現する。
BASE_STYLE_SHEET = """
* {
    font-family: "Yu Gothic UI", "Meiryo", "Segoe UI", sans-serif;
}
QWidget {
    background-color: #020617;
    color: #e2e8f0;
}
QMainWindow, QDialog {
    background-color: transparent;
}
QDialog#appDialog {
    background: qradialgradient(
        cx: 0.3, cy: 0.1, radius: 1.1,
        fx: 0.3, fy: 0.1,
        stop: 0 #1f2937,
        stop: 0.6 #0f172a,
        stop: 1 #020617
    );
}
QFrame#startCard,
QFrame#dialogCard,
QFrame#panelCard,
QFrame#inspectorSection {
    background-color: rgba(15, 23, 42, 0.92);
    border: 1px solid rgba(148, 163, 184, 0.35);
    border-radius: 18px;
}
QLabel {
    color: #e2e8f0;
}
QLabel[hint="secondary"] {
    color: #cbd5f5;
}
QLabel#panelTitle {
    font-weight: 600;
    font-size: 14px;
}
QLabel#formLabel {
    color: #cbd5f5;
    font-weight: 500;
}
QLabel#projectInfoLabel {
    color: #e2e8f0;
    background-color: rgba(30, 41, 59, 0.65);
    border: 1px solid rgba(148, 163, 184, 0.25);
    border-radius: 12px;
    padding: 12px 14px;
}
QLabel#structureStatusLabel,
QLabel#structureWarningLabel {
    background-color: transparent;
    border-radius: 10px;
    border: none;
    padding: 0;
}
QLabel#structureStatusLabel[status="ok"],
QLabel#structureWarningLabel[status="ok"] {
    color: #34d399;
    background-color: rgba(34, 197, 94, 0.12);
    border: 1px solid rgba(34, 197, 94, 0.4);
    padding: 10px 12px;
}
QLabel#structureStatusLabel[status="error"],
QLabel#structureWarningLabel[status="error"] {
    color: #fca5a5;
    background-color: rgba(248, 113, 113, 0.12);
    border: 1px solid rgba(248, 113, 113, 0.4);
    padding: 10px 12px;
}
QLabel#structureStatusLabel[status="warning"],
QLabel#structureWarningLabel[status="warning"] {
    color: #fbbf24;
    background-color: rgba(251, 191, 36, 0.12);
    border: 1px solid rgba(251, 191, 36, 0.4);
    padding: 10px 12px;
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
    background-color: rgba(15, 23, 42, 0.9);
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
    border: 1px solid rgba(148, 163, 184, 0.35);
    border-radius: 10px;
    padding: 8px 12px;
    selection-background-color: rgba(96, 165, 250, 0.3);
    selection-color: #f8fafc;
}
QLineEdit:focus,
QPlainTextEdit:focus,
QTextEdit:focus,
QComboBox:focus,
QSpinBox:focus,
QDoubleSpinBox:focus,
QAbstractSpinBox:focus {
    border: 1px solid rgba(96, 165, 250, 0.7);
    background-color: rgba(30, 58, 138, 0.85);
}
QComboBox QAbstractItemView {
    background-color: rgba(15, 23, 42, 0.94);
    border: 1px solid rgba(148, 163, 184, 0.35);
    border-radius: 10px;
    padding: 4px;
}
QPushButton {
    background-color: rgba(148, 163, 184, 0.12);
    border: 1px solid rgba(148, 163, 184, 0.35);
    border-radius: 10px;
    color: #e2e8f0;
    padding: 8px 18px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: rgba(96, 165, 250, 0.18);
    border: 1px solid rgba(96, 165, 250, 0.5);
}
QPushButton:pressed {
    background-color: rgba(30, 64, 175, 0.7);
}
QPushButton:disabled {
    background-color: rgba(148, 163, 184, 0.05);
    border: 1px solid rgba(148, 163, 184, 0.2);
    color: rgba(226, 232, 240, 0.4);
}
QPushButton#primaryActionButton {
    background-color: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 0,
        stop: 0 #2563eb,
        stop: 1 #7c3aed
    );
    border: none;
    color: #f8fafc;
    padding: 10px 24px;
    font-size: 14px;
}
QPushButton#primaryActionButton:hover {
    background-color: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 0,
        stop: 0 #1d4ed8,
        stop: 1 #6d28d9
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
    min-width: 96px;
}
QListWidget {
    border-radius: 12px;
    padding: 8px;
}
QListWidget::item {
    border-radius: 10px;
    padding: 6px;
}
QListWidget::item:selected {
    background-color: rgba(96, 165, 250, 0.25);
}
QTabWidget::pane {
    border: 1px solid rgba(148, 163, 184, 0.25);
    border-radius: 12px;
    margin-top: 6px;
}
QTabBar::tab {
    background-color: rgba(30, 41, 59, 0.85);
    border: 1px solid rgba(148, 163, 184, 0.3);
    border-bottom: none;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    padding: 8px 16px;
    margin-right: 6px;
    color: #cbd5f5;
}
QTabBar::tab:selected {
    background-color: rgba(51, 65, 85, 0.95);
    color: #f8fafc;
}
QTabBar::tab:hover {
    background-color: rgba(96, 165, 250, 0.22);
}
QDockWidget {
    background-color: rgba(15, 23, 42, 0.94);
    border: 1px solid rgba(148, 163, 184, 0.35);
}
QDockWidget::title {
    text-align: left;
    padding: 6px 12px;
    background-color: rgba(30, 41, 59, 0.85);
    border-bottom: 1px solid rgba(148, 163, 184, 0.25);
}
QMenuBar {
    background: transparent;
}
QMenuBar::item {
    padding: 6px 12px;
    color: #cbd5f5;
}
QMenuBar::item:selected {
    background-color: rgba(96, 165, 250, 0.18);
    border-radius: 6px;
}
QMenu {
    background-color: rgba(15, 23, 42, 0.94);
    border: 1px solid rgba(148, 163, 184, 0.35);
}
QMenu::item {
    padding: 6px 18px;
    color: #e2e8f0;
}
QMenu::item:selected {
    background-color: rgba(96, 165, 250, 0.25);
}
QToolTip {
    color: #0f172a;
    background-color: #e2e8f0;
    border: 1px solid rgba(51, 65, 85, 0.35);
    padding: 6px 10px;
    border-radius: 8px;
}
"""


START_WINDOW_STYLE = """
QWidget#startRoot {
    background: qradialgradient(
        cx: 0.3, cy: 0.1, radius: 1.1,
        fx: 0.3, fy: 0.1,
        stop: 0 #1f2937,
        stop: 0.6 #0f172a,
        stop: 1 #020617
    );
}
QFrame#startCard {
    border-radius: 18px;
}
QLabel#startTitle {
    font-size: 22px;
    font-weight: 600;
    color: #f8fafc;
}
QLabel#startDescription {
    color: #cbd5f5;
    font-size: 13px;
}
"""


def apply_base_style(widget: QWidget, extra: str | None = None) -> None:
    """ウィジェットに共通スタイルを適用する。"""

    stylesheet = BASE_STYLE_SHEET
    if extra:
        stylesheet = f"{stylesheet}\n{extra}"
    widget.setStyleSheet(stylesheet)

