"""WatcherB — Discord #dev-bar リアルタイム監視 GUI."""

import html
import re
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QStatusBar,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

import config
from discord_client import DiscordThread
from message_parser import classify


_STATE_RE = re.compile(
    r"((?:IDLE|DESIGN_PLAN|DESIGN_REVIEW|DESIGN_REVISE|DESIGN_APPROVED|"
    r"IMPLEMENTATION|CODE_REVIEW|CODE_REVISE|CODE_APPROVED|"
    r"MERGE_SUMMARY_SENT|DONE|BLOCKED|None))"
)
_ARROW_RE = re.compile(r"(→)")


def _highlight_states(text: str) -> str:
    """状態名とアローをアクセントカラーでハイライト."""
    c = config.COLORS
    accent = c["accent"]
    subtext = c["subtext"]
    text = _STATE_RE.sub(
        lambda m: f'<span style="color: {accent}; font-weight: bold;">{m.group(1)}</span>',
        text,
    )
    text = _ARROW_RE.sub(
        lambda m: f'<span style="color: {subtext};">{m.group(1)}</span>',
        text,
    )
    return text

class MessageLog(QTextBrowser):
    """メッセージログ表示ウィジェット（色分け + 自動スクロール）."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setOpenExternalLinks(False)
        self._auto_scroll = True
        self.verticalScrollBar().valueChanged.connect(self._on_scroll_value_changed)
        self.verticalScrollBar().rangeChanged.connect(self._on_range_changed)

    def append_message(self, content: str, created_at, msg_type: str):
        """色分けされたメッセージエントリをログに追加."""
        local_time = created_at.astimezone()
        time_str = local_time.strftime("%H:%M")

        subtext = config.COLORS["subtext"]
        text_color = config.COLORS["text"]

        lines = content.split("\n")

        rows = ""
        for i, line in enumerate(lines):
            esc = _highlight_states(html.escape(line))
            if i == 0:
                rows += (
                    f'<tr>'
                    f'<td width="{config.TIMESTAMP_WIDTH}" valign="middle"><font color="{subtext}" size="2">{time_str}</font></td>'
                    f'<td valign="top"><font color="{text_color}">{esc}</font></td>'
                    f'</tr>'
                )
            else:
                rows += (
                    f'<tr>'
                    f'<td></td>'
                    f'<td><font color="{text_color}">{esc}</font></td>'
                    f'</tr>'
                )

        html_block = f'<table cellpadding="0" cellspacing="0" width="100%">{rows}</table>'
        self.append(html_block)

    def _on_scroll_value_changed(self, value: int):
        """ユーザーが底部から離れたら自動スクロールを無効化."""
        scrollbar = self.verticalScrollBar()
        self._auto_scroll = (scrollbar.maximum() - value) <= 10

    def _on_range_changed(self, _min: int, maximum: int):
        """コンテンツ追加時、自動スクロールが有効なら底部へ移動."""
        if self._auto_scroll:
            self.verticalScrollBar().setValue(maximum)


class MainWindow(QMainWindow):
    """アプリケーションメインウィンドウ."""

    def __init__(self):
        super().__init__()
        self._setup_ui()
        self._setup_shortcuts()
        self._setup_discord()

    def _setup_ui(self):
        self.setWindowTitle(config.WINDOW_TITLE)
        self.resize(config.WINDOW_WIDTH, config.WINDOW_HEIGHT)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        self._message_log = MessageLog()
        layout.addWidget(self._message_log)

        self._status_label = QLabel("Disconnected")
        self._last_msg_label = QLabel("")
        status_bar = QStatusBar()
        status_bar.addWidget(self._status_label)
        status_bar.addPermanentWidget(self._last_msg_label)
        self.setStatusBar(status_bar)

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+="), self, self._zoom_in)
        QShortcut(QKeySequence("Ctrl++"), self, self._zoom_in)
        QShortcut(QKeySequence("Ctrl+-"), self, self._zoom_out)
        QShortcut(QKeySequence("Ctrl+0"), self, self._zoom_reset)

    def _zoom_in(self):
        config.FONT_SIZE = min(config.FONT_SIZE + 1, 30)
        self._apply_zoom()

    def _zoom_out(self):
        config.FONT_SIZE = max(config.FONT_SIZE - 1, 8)
        self._apply_zoom()

    def _zoom_reset(self):
        config.FONT_SIZE = 13
        self._apply_zoom()

    def _apply_zoom(self):
        self._message_log.setStyleSheet(
            f'font-family: {config.FONT_FAMILY};'
            f'font-size: {config.FONT_SIZE}px;'
            f'line-height: {config.LINE_HEIGHT};'
        )
        self.statusBar().showMessage(f"Font size: {config.FONT_SIZE}px", 2000)

    def _setup_discord(self):
        self._discord_thread = DiscordThread(parent=self)
        self._discord_thread.message_received.connect(self._on_message_received)
        self._discord_thread.history_loaded.connect(self._on_history_loaded)
        self._discord_thread.connection_changed.connect(self._on_connection_changed)
        self._discord_thread.start()

    def _on_message_received(self, msg_dict: dict):
        msg_type = classify(msg_dict["content"])
        self._message_log.append_message(
            msg_dict["content"], msg_dict["created_at"], msg_type
        )
        local_time = msg_dict["created_at"].astimezone()
        self._last_msg_label.setText(f"Last msg: {local_time.strftime('%H:%M')}")

    def _on_history_loaded(self, messages: list):
        for msg_dict in messages:
            msg_type = classify(msg_dict["content"])
            self._message_log.append_message(
                msg_dict["content"], msg_dict["created_at"], msg_type
            )
        if messages:
            local_time = messages[-1]["created_at"].astimezone()
            self._last_msg_label.setText(f"Last msg: {local_time.strftime('%H:%M')}")

    def _on_connection_changed(self, state: str):
        display_map = {
            "connected": ("Connected", config.COLORS["green"]),
            "disconnected": ("Disconnected", config.COLORS["red"]),
            "reconnecting": ("Reconnecting...", config.COLORS["yellow"]),
        }
        text, color = display_map.get(state, ("Unknown", config.COLORS["subtext"]))
        self._status_label.setText(text)
        self._status_label.setStyleSheet(f"color: {color};")

    def closeEvent(self, event):
        """ウィンドウ閉じ時に Discord client を安全に停止."""
        if self._discord_thread.isRunning():
            self._discord_thread.request_stop()
            if not self._discord_thread.wait(5000):
                self._discord_thread.terminate()
                self._discord_thread.wait(2000)
        event.accept()


def _build_global_qss() -> str:
    """config.COLORS からアプリ全体の QSS を生成."""
    c = config.COLORS
    return f"""
        QMainWindow {{
            background-color: {c["bg"]};
        }}
        QWidget {{
            background-color: {c["bg"]};
            color: {c["text"]};
        }}
        QTextBrowser {{
            background-color: {c["bg"]};
            color: {c["text"]};
            border: none;
            font-family: {config.FONT_FAMILY};
            font-size: {config.FONT_SIZE}px;
            line-height: {config.LINE_HEIGHT};
            padding: 8px;
        }}
        QStatusBar {{
            background-color: {c["surface"]};
            color: {c["subtext"]};
            font-size: {config.FONT_SIZE_STATUS}px;
            padding: 2px 8px;
        }}
        QStatusBar QLabel {{
            color: {c["subtext"]};
        }}
        QScrollBar:vertical {{
            background-color: {c["bg"]};
            width: 10px;
        }}
        QScrollBar::handle:vertical {{
            background-color: {c["surface"]};
            border-radius: 5px;
            min-height: 30px;
        }}
        QScrollBar::handle:vertical:hover {{
            background-color: {c["subtext"]};
        }}
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        QScrollBar::add-page:vertical,
        QScrollBar::sub-page:vertical {{
            background: none;
        }}
    """


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(_build_global_qss())
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
