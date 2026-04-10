"""Issue browser widgets for GitLab issue list display."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import config


class IssueListWidget(QWidget):
    """Issue list display with filter and reload controls."""

    issue_selected = Signal(int)        # iid
    reload_requested = Signal()
    filter_changed = Signal(str)        # API value ("opened" / "closed" / "all")

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 上段: フィルタ + リロード
        top_row = QHBoxLayout()
        self._filter_combo = QComboBox()
        self._filter_combo.addItem("Open", "opened")
        self._filter_combo.addItem("Closed", "closed")
        self._filter_combo.addItem("All", "all")
        top_row.addWidget(self._filter_combo)

        self._reload_btn = QPushButton("Reload")
        top_row.addWidget(self._reload_btn)
        layout.addLayout(top_row)

        # リスト
        self._list = QListWidget()
        layout.addWidget(self._list)

        # シグナル接続
        self._filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        self._reload_btn.clicked.connect(self.reload_requested.emit)
        self._list.currentItemChanged.connect(self._on_item_changed)

    def populate(self, issues: list[dict], truncated: bool = False):
        """Issue リストを表示。truncated=True なら末尾に警告アイテム追加。"""
        self._list.blockSignals(True)
        try:
            self._list.clear()

            if not issues:
                item = QListWidgetItem("No issues found")
                item.setFlags(Qt.NoItemFlags)
                item.setForeground(QColor(config.COLORS["subtext"]))
                self._list.addItem(item)
                return

            for issue in issues:
                iid = issue["iid"]
                title = issue.get("title", "")
                labels = issue.get("labels", [])

                text = f"#{iid}  {title}"
                if labels:
                    text += f"  [{', '.join(labels)}]"

                item = QListWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, iid)
                self._list.addItem(item)

            if truncated:
                n = len(issues)
                warn_item = QListWidgetItem(
                    f"Showing first {n} of {config.MAX_PAGES * 100}+ issues (truncated)"
                )
                warn_item.setFlags(Qt.NoItemFlags)
                warn_item.setForeground(QColor(config.COLORS["subtext"]))
                self._list.addItem(warn_item)
        finally:
            self._list.blockSignals(False)

    def show_loading(self):
        """Loading 状態を表示。"""
        self._list.blockSignals(True)
        try:
            self._list.clear()
            item = QListWidgetItem("Loading...")
            item.setFlags(Qt.NoItemFlags)
            item.setForeground(QColor(config.COLORS["subtext"]))
            self._list.addItem(item)
        finally:
            self._list.blockSignals(False)

    def show_error(self, message: str):
        """エラー状態を表示。"""
        self._list.blockSignals(True)
        try:
            self._list.clear()
            item = QListWidgetItem(f"Error: {message}")
            item.setFlags(Qt.NoItemFlags)
            item.setForeground(QColor(config.COLORS["red"]))
            self._list.addItem(item)
        finally:
            self._list.blockSignals(False)

    def _on_item_changed(self, current, previous):
        """リストアイテム選択時に iid を emit。選択解除時は emit しない。"""
        if current is None:
            return
        iid = current.data(Qt.ItemDataRole.UserRole)
        if iid is not None:
            self.issue_selected.emit(iid)

    def _on_filter_changed(self):
        """フィルタ変更時に API 値を emit。"""
        api_value = self._filter_combo.currentData()
        self.filter_changed.emit(api_value)

    def current_filter(self) -> str:
        """現在のフィルタの API 値を返す。"""
        return self._filter_combo.currentData()
