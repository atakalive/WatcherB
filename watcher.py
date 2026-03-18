"""WatcherB — Discord #gokrax リアルタイム監視 GUI."""

import html
import re
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QLineEdit,
    QMainWindow,
    QSplitter,
    QStatusBar,
    QSystemTrayIcon,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

import config
from discord_client import DiscordThread
from message_parser import classify, parse_message
from widgets import ProjectPanel, WatcherTrayIcon


_STATE_RE = re.compile(
    r"((?:IDLE|DESIGN_PLAN|DESIGN_REVIEW|DESIGN_REVISE|DESIGN_APPROVED|"
    r"IMPLEMENTATION|CODE_REVIEW|CODE_REVISE|CODE_APPROVED|"
    r"MERGE_SUMMARY_SENT|DONE|BLOCKED|None))"
)
_ARROW_RE = re.compile(r"(→)")


def _markdown_to_html(text: str) -> str:
    """Discord Markdown の太字を HTML <b> に変換する.

    html.escape() 済みのテキストに対して呼ぶこと。
    `**text**` → `<b>text</b>` に変換する。
    ネストや改行をまたぐケースは対象外。
    """
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)


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
            esc = _markdown_to_html(_highlight_states(html.escape(line)))
            if i == 0:
                rows += (
                    f'<tr>'
                    f'<td width="{config.TIMESTAMP_WIDTH}" valign="top"><font color="{subtext}" size="{config.FONT_SIZE_TIMESTAMP}">{time_str}</font></td>'
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
        self._force_quit = False
        self._setup_ui()
        self._setup_shortcuts()
        self._setup_tray()
        self._setup_discord()

    def _setup_ui(self):
        self.setWindowTitle(config.WINDOW_TITLE)
        self.setWindowIcon(QIcon(str(config.ICON_PATH)))
        self.setWindowFlags(self.windowFlags() | Qt.Tool)
        self.resize(config.WINDOW_WIDTH, config.WINDOW_HEIGHT)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        # QSplitter: 左=ProjectPanel, 右=right_container(MessageLog + QLineEdit)
        self._splitter = QSplitter(Qt.Horizontal)
        self._project_panel = ProjectPanel()
        self._message_log = MessageLog()

        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 4)
        right_layout.setSpacing(4)
        right_layout.addWidget(self._message_log)

        if config.SEND_ENABLED:
            self._send_input = QLineEdit()
            self._send_input.setPlaceholderText("Send command to #gokrax...")
            self._send_input.returnPressed.connect(self._on_send)
            right_layout.addWidget(self._send_input)
        else:
            self._send_input = None

        self._splitter.addWidget(self._project_panel)
        self._splitter.addWidget(right_container)
        self._splitter.setSizes([
            config.LEFT_PANEL_WIDTH,
            config.WINDOW_WIDTH - config.LEFT_PANEL_WIDTH,
        ])
        layout.addWidget(self._splitter)

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

    def _setup_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self._tray = None
            return
        self._tray = WatcherTrayIcon(self)
        self._tray.show_requested.connect(self._toggle_window)
        self._tray.exit_requested.connect(self._exit_app)
        self._tray.show()

    def _toggle_window(self):
        if self.isVisible():
            self.hide()
        else:
            self.showNormal()
            self.activateWindow()

    def _exit_app(self):
        if self._tray:
            self._tray.hide()
        self._force_quit = True
        self.close()

    def _setup_discord(self):
        self._discord_thread = DiscordThread(parent=self)
        self._discord_thread.message_received.connect(self._on_message_received)
        self._discord_thread.history_loaded.connect(self._on_history_loaded)
        self._discord_thread.connection_changed.connect(self._on_connection_changed)
        self._discord_thread.start()

    def _on_message_received(self, msg_dict: dict):
        content = msg_dict["content"]
        created_at = msg_dict["created_at"]
        msg_type = classify(content)

        self._message_log.append_message(content, created_at, msg_type)
        self._update_project_from_message(content, created_at, msg_type)

        local_time = created_at.astimezone()
        self._last_msg_label.setText(f"Last msg: {local_time.strftime('%H:%M')}")

    def _on_history_loaded(self, messages: list):
        for msg_dict in messages:
            content = msg_dict["content"]
            created_at = msg_dict["created_at"]
            msg_type = classify(content)

            self._message_log.append_message(content, created_at, msg_type)
            self._update_project_from_message(content, created_at, msg_type)

        if messages:
            local_time = messages[-1]["created_at"].astimezone()
            self._last_msg_label.setText(f"Last msg: {local_time.strftime('%H:%M')}")

    def _update_project_from_message(self, content: str, created_at,
                                     msg_type: str):
        """状態遷移メッセージからプロジェクトパネルを更新."""
        if msg_type not in ("transition", "blocked", "done"):
            return
        parsed = parse_message(content, created_at)
        if parsed.project and parsed.extra.get("to_state"):
            to_state = parsed.extra["to_state"]
            self._project_panel.update_project(
                parsed.project, to_state, created_at
            )
            if to_state == "BLOCKED" and self._tray:
                self._tray.showMessage(
                    parsed.project,
                    f"{parsed.extra.get('from_state', '?')} → BLOCKED",
                    QSystemTrayIcon.MessageIcon.Warning,
                    5000,
                )

    def _on_connection_changed(self, state: str):
        display_map = {
            "connected": ("Connected", config.COLORS["green"]),
            "disconnected": ("Disconnected", config.COLORS["red"]),
            "reconnecting": ("Reconnecting...", config.COLORS["yellow"]),
        }
        text, color = display_map.get(state, ("Unknown", config.COLORS["subtext"]))
        self._status_label.setText(text)
        self._status_label.setStyleSheet(f"color: {color};")

    def _on_send(self) -> None:
        """テキスト入力欄の Enter キー押下で呼ばれる。入力内容をチャンネルに送信する。"""
        if self._send_input is None:
            return
        text = self._send_input.text().strip()
        if not text:
            return
        self._discord_thread.send_message(text)
        self._send_input.clear()

    def closeEvent(self, event):
        """ウィンドウ閉じ時: トレイに最小化 or 完全終了."""
        if self._force_quit:
            # トレイメニューの "Exit" からの終了
            if self._discord_thread.isRunning():
                self._discord_thread.request_stop()
                if not self._discord_thread.wait(5000):
                    self._discord_thread.terminate()
                    self._discord_thread.wait(2000)
            if self._tray:
                self._tray.hide()
            event.accept()
        else:
            # トレイに最小化
            event.ignore()
            self.hide()


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
        QSplitter::handle {{
            background-color: {c["surface"]};
            width: 2px;
        }}
        QScrollArea {{
            background-color: {c["bg"]};
            border: none;
        }}
        QProgressBar {{
            background-color: {c["bg"]};
            border: none;
            border-radius: 4px;
        }}
        QProgressBar::chunk {{
            background-color: {c["accent"]};
            border-radius: 4px;
        }}
        QLineEdit {{
            background-color: {c["surface"]};
            color: {c["text"]};
            border: 1px solid {c["subtext"]};
            border-radius: 4px;
            padding: 6px 8px;
            font-family: {config.FONT_FAMILY};
            font-size: {config.FONT_SIZE}px;
        }}
        QLineEdit:focus {{
            border-color: {c["accent"]};
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
