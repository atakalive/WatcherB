"""Issue browser widgets for GitLab issue list and detail display."""

import html

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

import config
from issue_browser.markdown import md_to_html


class IssueListWidget(QWidget):
    """Issue list display with filter and reload controls."""

    issue_selected = Signal(int)  # iid
    reload_requested = Signal()
    filter_changed = Signal(str)  # API value ("opened" / "closed" / "all")

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

    def reset_filter(self) -> None:
        """フィルタ combo を "Open" (index 0) にリセット。signal は発火しない。"""
        self._filter_combo.blockSignals(True)
        try:
            self._filter_combo.setCurrentIndex(0)
        finally:
            self._filter_combo.blockSignals(False)

    def select_by_iid(self, iid: int) -> bool:
        """指定 iid のアイテムを選択状態にする。見つからなければ False を返す。
        選択成功時は issue_selected signal が発火する（blockSignals しない）。"""
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == iid:
                self._list.setCurrentItem(item)
                return True
        return False

    def selected_iid(self) -> int | None:
        """現在選択中の issue iid を返す。未選択なら None。"""
        current = self._list.currentItem()
        if current is None:
            return None
        return current.data(Qt.ItemDataRole.UserRole)

    def current_filter(self) -> str:
        """現在のフィルタの API 値を返す。"""
        return self._filter_combo.currentData()


class IssueDetailWidget(QTextBrowser):
    """Issue 詳細表示ウィジェット。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setOpenExternalLinks(True)

    def show_detail(self, detail_dict: dict) -> None:
        """Issue 詳細を HTML で描画する。"""
        c = config.COLORS
        iid = detail_dict["iid"]
        title = html.escape(detail_dict.get("title", ""))
        state = html.escape(detail_dict.get("state", "")).upper()
        labels = detail_dict.get("labels", [])
        labels_str = ", ".join(html.escape(label) for label in labels)
        body = detail_dict.get("description", "") or ""
        body_html = md_to_html(body)
        notes = detail_dict.get("_notes", [])
        notes_truncated = detail_dict.get("_notes_truncated", False)

        parts = []
        parts.append(f"<h3>#{iid} {title}</h3>")
        parts.append(
            f'<div><span style="color: {c["accent"]};">{state}</span> {labels_str}</div>'
        )
        parts.append(f"<div>{body_html}</div>")
        parts.append("<hr>")
        parts.append(f"<div><b>--- Comments ({len(notes)}) ---</b></div>")

        for note in notes:
            author_obj = note.get("author")
            name = (
                author_obj.get("name", "unknown")
                if isinstance(author_obj, dict)
                else "unknown"
            )
            name = html.escape(name)
            date = note.get("created_at", "")[:10]
            note_body_html = md_to_html(note.get("body", ""))
            parts.append(
                f'<div><span style="color: {c["accent"]};">{name}</span> '
                f'<span style="color: {c["subtext"]}; font-size: small;">{date}</span></div>'
            )
            parts.append(f"<div>{note_body_html}</div>")

        if notes_truncated:
            parts.append(
                f'<div style="color: {c["subtext"]};">Showing first {len(notes)} '
                f"comments (list may be incomplete)</div>"
            )

        self.setHtml("\n".join(parts))

    def show_blank(self) -> None:
        """空白表示。"""
        self.clear()

    def show_loading(self) -> None:
        """Loading 状態を表示。"""
        self.setHtml(
            f'<p align="center" style="color: {config.COLORS["subtext"]};">Loading...</p>'
        )

    def show_error(self, message: str) -> None:
        """エラー状態を表示。"""
        escaped = html.escape(message)
        self.setHtml(f'<p style="color: {config.COLORS["red"]};">Error: {escaped}</p>')
