"""WatcherB — Discord #gokrax real-time monitoring GUI."""

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
    QStackedWidget,
    QStatusBar,
    QSystemTrayIcon,
    QTabBar,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

import config
from discord_client import DiscordThread
from issue_browser.gitlab_client import GitLabThread
from issue_browser.widgets import IssueDetailWidget, IssueListWidget
from message_parser import classify, extract_project, parse_message
from widgets import ProjectPanel, SplashScreen, WatcherTrayIcon


# Alternation order: longer patterns before shorter ones (longest-match-first).
# e.g. DESIGN_REVIEW_NPASS before DESIGN_REVIEW to avoid partial match.
_STATE_RE = re.compile(
    r"((?:IDLE|INITIALIZE|DESIGN_PLAN|DESIGN_REVIEW_NPASS|DESIGN_REVIEW|DESIGN_REVISE|DESIGN_APPROVED|"
    r"ASSESSMENT|IMPLEMENTATION|CODE_REVIEW_NPASS|CODE_REVIEW|CODE_REVISE|CODE_APPROVED|"
    r"MERGE_SUMMARY_SENT|DONE|BLOCKED|None))"
)
_ARROW_RE = re.compile(r"(→)")
_ISSUE_REF_RE = re.compile(r"(?<![\w#])#(\d+)")


def _markdown_to_html(text: str) -> str:
    """Convert Discord Markdown bold to HTML <b>.

    Call on text already processed by html.escape().
    Converts `**text**` to `<b>text</b>`.
    Nested or multi-line cases are not handled.
    """
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)


def _linkify_issues(text: str, project: str) -> str:
    """Replace #N with clickable GitLab Issue links.

    Call on text already processed by html.escape() but BEFORE
    _highlight_states() (to avoid matching color codes like #89b4fa).
    ``project`` is the repository name extracted from [PJ] prefix.
    """
    base = config.GITLAB_BASE_URL.rstrip("/")
    safe_project = html.escape(project, quote=True)

    def _replace(m: re.Match) -> str:
        num = m.group(1)
        url = f"{base}/{safe_project}/-/issues/{num}"
        return f'<a href="{url}" style="color: {config.COLORS["accent"]};">#{num}</a>'

    return _ISSUE_REF_RE.sub(_replace, text)


def _highlight_states(text: str) -> str:
    """Highlight state names and arrows with accent color."""
    c = config.COLORS
    accent = c["accent"]
    subtext = c["subtext"]
    text = _STATE_RE.sub(
        lambda m: (
            f'<span style="color: {accent}; font-weight: bold;">{m.group(1)}</span>'
        ),
        text,
    )
    text = _ARROW_RE.sub(
        lambda m: f'<span style="color: {subtext};">{m.group(1)}</span>',
        text,
    )
    return text


class MessageLog(QTextBrowser):
    """Message log display widget (color-coded + auto-scroll)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setOpenExternalLinks(True)
        self._auto_scroll = True
        self.verticalScrollBar().valueChanged.connect(self._on_scroll_value_changed)
        self.verticalScrollBar().rangeChanged.connect(self._on_range_changed)

    def append_message(self, content: str, created_at, msg_type: str):
        """Append a color-coded message entry to the log."""
        local_time = created_at.astimezone()
        time_str = local_time.strftime("%H:%M")

        subtext = config.COLORS["subtext"]
        text_color = config.COLORS["text"]

        project = extract_project(content)

        lines = content.split("\n")

        rows = ""
        for i, line in enumerate(lines):
            esc = html.escape(line)
            if project:
                esc = _linkify_issues(esc, project)
            esc = _highlight_states(esc)
            esc = _markdown_to_html(esc)
            if i == 0:
                rows += (
                    f"<tr>"
                    f'<td width="{config.TIMESTAMP_WIDTH}" valign="top"><font color="{subtext}" size="{config.FONT_SIZE_TIMESTAMP}">{time_str}</font></td>'
                    f'<td valign="top"><font color="{text_color}">{esc}</font></td>'
                    f"</tr>"
                )
            else:
                rows += (
                    f"<tr>"
                    f"<td></td>"
                    f'<td><font color="{text_color}">{esc}</font></td>'
                    f"</tr>"
                )

        html_block = (
            f'<table cellpadding="0" cellspacing="0" width="100%">{rows}</table>'
        )
        self.append(html_block)

    def _on_scroll_value_changed(self, value: int):
        """Disable auto-scroll when user scrolls away from bottom."""
        scrollbar = self.verticalScrollBar()
        self._auto_scroll = (scrollbar.maximum() - value) <= 10

    def _on_range_changed(self, _min: int, maximum: int):
        """Scroll to bottom on new content if auto-scroll is enabled."""
        if self._auto_scroll:
            self.verticalScrollBar().setValue(maximum)


class MainWindow(QMainWindow):
    """Application main window."""

    def __init__(self, splash: SplashScreen | None = None):
        super().__init__()
        self._force_quit = False
        self._selected_project: str | None = None
        self._setup_ui()
        self._setup_shortcuts()
        self._setup_tray()

        self._gitlab_thread = GitLabThread(parent=self)
        self._issue_cache: dict[tuple[str, str], tuple[list[dict], bool]] = {}
        self._current_list_request_id: int = -1
        self._current_detail_request_id: int = -1
        self._current_state_filter: str = "opened"
        self._reload_selected_iid: int | None = None  # reload 時の再選択用

        # GitLabThread signals（start() の前に接続）
        self._gitlab_thread.issues_loaded.connect(self._on_issues_loaded)
        self._gitlab_thread.issue_detail_loaded.connect(self._on_issue_detail_loaded)
        self._gitlab_thread.list_error.connect(self._on_list_error)
        self._gitlab_thread.detail_error.connect(self._on_detail_error)
        self._gitlab_thread.start()

        if splash is not None:
            splash.set_progress(50, "Connecting to Discord...")

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

        # QSplitter: left=ProjectPanel, right=right_container(MessageLog + QLineEdit)
        self._splitter = QSplitter(Qt.Horizontal)
        self._project_panel = ProjectPanel()
        self._message_log = MessageLog()

        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 4)
        right_layout.setSpacing(4)

        # Tab bar (Normal Mode では非表示)
        self._tab_bar = QTabBar()
        self._tab_bar.addTab("Pipeline")
        self._tab_bar.addTab("Issues")
        self._tab_bar.hide()
        right_layout.addWidget(self._tab_bar)

        # QStackedWidget: idx 0 = MessageLog, idx 1 = Issue splitter
        self._right_stack = QStackedWidget()
        self._right_stack.addWidget(self._message_log)  # index 0

        self._issue_list = IssueListWidget()
        self._issue_list.reload_requested.connect(self._on_reload_requested)
        self._issue_list.filter_changed.connect(self._on_filter_changed)
        self._issue_list.issue_selected.connect(self._on_issue_selected)
        self._issue_detail = IssueDetailWidget()
        self._issue_splitter = QSplitter(Qt.Horizontal)
        self._issue_splitter.addWidget(self._issue_list)
        self._issue_splitter.addWidget(self._issue_detail)
        detail_width = max(
            100, config.WINDOW_WIDTH - config.LEFT_PANEL_WIDTH - config.ISSUE_LIST_WIDTH
        )
        self._issue_splitter.setSizes([config.ISSUE_LIST_WIDTH, detail_width])
        self._right_stack.addWidget(self._issue_splitter)  # index 1

        right_layout.addWidget(self._right_stack)

        if config.SEND_ENABLED:
            self._send_input = QLineEdit()
            self._send_input.setPlaceholderText("Send command to #gokrax...")
            self._send_input.returnPressed.connect(self._on_send)
            right_layout.addWidget(self._send_input)
        else:
            self._send_input = None

        self._splitter.addWidget(self._project_panel)
        self._splitter.addWidget(right_container)
        self._splitter.setSizes(
            [
                config.LEFT_PANEL_WIDTH,
                config.WINDOW_WIDTH - config.LEFT_PANEL_WIDTH,
            ]
        )
        layout.addWidget(self._splitter)

        self._status_label = QLabel("Disconnected")
        self._last_msg_label = QLabel("")
        status_bar = QStatusBar()
        status_bar.addWidget(self._status_label)
        status_bar.addPermanentWidget(self._last_msg_label)
        self.setStatusBar(status_bar)

        # Signal connections (after tab bar hidden + all tabs added — §6.3)
        self._tab_bar.currentChanged.connect(self._on_tab_changed)
        self._project_panel.project_clicked.connect(self._on_project_clicked)

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+="), self, self._zoom_in)
        QShortcut(QKeySequence("Ctrl++"), self, self._zoom_in)
        QShortcut(QKeySequence("Ctrl+-"), self, self._zoom_out)
        QShortcut(QKeySequence("Ctrl+0"), self, self._zoom_reset)
        QShortcut(QKeySequence(Qt.Key_Escape), self, self._on_escape)

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
            f"font-family: {config.FONT_FAMILY};"
            f"font-size: {config.FONT_SIZE}px;"
            f"line-height: {config.LINE_HEIGHT};"
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

    def _update_project_from_message(self, content: str, created_at, msg_type: str):
        """Update project panel from state transition and info messages."""
        parsed = parse_message(content, created_at)

        # Issue 番号の更新（info メッセージ内の Target Issues）
        if parsed.project and parsed.extra.get("issues"):
            self._project_panel.update_issues(parsed.project, parsed.extra["issues"])

        # 状態遷移の更新（既存ロジック）
        if msg_type not in ("transition", "blocked", "done"):
            return
        if parsed.project and parsed.extra.get("to_state"):
            to_state = parsed.extra["to_state"]
            self._project_panel.update_project(parsed.project, to_state, created_at)
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

    def _on_project_clicked(self, project_path: str):
        if self._selected_project == project_path:
            # 同じ PJ 再クリック → Normal Mode
            self._exit_issue_mode()
            return

        # Issue Mode 遷移（新規 or 異なる PJ）
        self._selected_project = project_path
        self._current_state_filter = "opened"  # PJ 切替時はフィルタリセット
        self._reload_selected_iid = None  # §7.5: PJ 切替は reload 再選択を無効化
        self._issue_list.reset_filter()  # combo 表示も同期（signal 不発火）
        self._project_panel.select_project(project_path)
        self._right_stack.setCurrentIndex(1)
        self._tab_bar.setCurrentIndex(1)  # Issues tab 強制アクティブ
        self._tab_bar.show()

        # §7.5: detail pane 無条件リセット
        self._issue_detail.show_blank()
        self._current_detail_request_id = -1

        # §9.6/§9.7: cache チェック
        cached = self._issue_cache.get((project_path, self._current_state_filter))
        if cached is not None:
            # cache hit → request_id 無効化 + 即座に表示
            self._current_list_request_id = -1
            issues, truncated = cached
            self._issue_list.populate(issues, truncated=truncated)
            return

        # cache miss → Loading 表示 + fetch
        self._issue_list.show_loading()
        rid = self._gitlab_thread.fetch_issues(project_path, self._current_state_filter)
        self._current_list_request_id = rid

    def _on_tab_changed(self, index: int):
        if self._selected_project is None:
            return  # §6.3: 初期化中の spurious signal を無視
        if index == 0:  # Pipeline tab → MessageLog
            self._right_stack.setCurrentIndex(0)
        elif index == 1:  # Issues tab → Issue splitter
            self._right_stack.setCurrentIndex(1)

    def _exit_issue_mode(self):
        self._selected_project = None
        self._current_list_request_id = -1
        self._current_detail_request_id = -1
        self._reload_selected_iid = (
            None  # §7.5: Normal Mode 遷移は reload 再選択を無効化
        )
        self._project_panel.select_project(None)
        # §6.2: setCurrentIndex(0) を tab bar 非表示の前に呼ぶ
        self._right_stack.setCurrentIndex(0)
        self._tab_bar.hide()

    def _on_escape(self):
        if self._selected_project is not None:
            self._exit_issue_mode()

    def _on_send(self) -> None:
        """Called on Enter key press in the text input. Send content to the channel."""
        if self._send_input is None:
            return
        text = self._send_input.text().strip()
        if not text:
            return
        self._discord_thread.send_message(text)
        self._send_input.clear()

    def _on_issues_loaded(
        self, project: str, state: str, request_id: int, truncated: bool, issues: list
    ):
        # §9.7: stale response filtering（request_id ガード）
        if request_id != self._current_list_request_id:
            return
        # §9.7 v6: 二次ガード — project/state が現在のコンテキストと一致するか
        # ※ cache 更新の前に配置。不一致の response は cache にも格納しない
        if project != self._selected_project or state != self._current_state_filter:
            return
        # cache 更新
        self._issue_cache[(project, state)] = (issues, truncated)
        # UI 更新
        self._issue_list.populate(issues, truncated=truncated)

        # reload 時の再選択（§7.5）
        if self._reload_selected_iid is not None:
            target_iid = self._reload_selected_iid
            self._reload_selected_iid = None
            # select_by_iid が True なら issue_selected signal 発火 → detail fetch 自動トリガー
            self._issue_list.select_by_iid(target_iid)

    def _on_issue_detail_loaded(
        self, project: str, iid: int, request_id: int, detail: dict
    ):
        if request_id != self._current_detail_request_id:
            return
        self._issue_detail.show_detail(detail)

    def _on_list_error(self, project: str, state: str, request_id: int, message: str):
        if request_id != self._current_list_request_id:
            return
        if project != self._selected_project or state != self._current_state_filter:
            return
        self._issue_list.show_error(message)

    def _on_detail_error(self, project: str, iid: int, request_id: int, message: str):
        if request_id != self._current_detail_request_id:
            return
        self._issue_detail.show_error(message)

    def _on_filter_changed(self, api_value: str):
        if self._selected_project is None:
            return
        self._current_state_filter = api_value
        self._reload_selected_iid = None  # §7.5: filter 変更は reload 再選択を無効化

        # §7.5: detail pane リセット + selection クリア
        self._issue_detail.show_blank()
        self._current_detail_request_id = -1

        # cache チェック
        cached = self._issue_cache.get((self._selected_project, api_value))
        if cached is not None:
            self._current_list_request_id = -1
            issues, truncated = cached
            self._issue_list.populate(issues, truncated=truncated)
            return

        # cache miss → fetch
        self._issue_list.show_loading()
        rid = self._gitlab_thread.fetch_issues(self._selected_project, api_value)
        self._current_list_request_id = rid

    def _on_reload_requested(self):
        if self._selected_project is None:
            return

        # §7.5: reload 時は再選択のため現在の iid を保存
        self._reload_selected_iid = self._issue_list.selected_iid()

        # §9.6: 当該 PJ の全フィルタ cache 無効化
        keys_to_delete = [
            k for k in self._issue_cache if k[0] == self._selected_project
        ]
        for k in keys_to_delete:
            del self._issue_cache[k]

        # §7.5: detail pane リセット
        self._issue_detail.show_blank()
        self._current_detail_request_id = -1

        # Loading 表示 + fetch
        self._issue_list.show_loading()
        rid = self._gitlab_thread.fetch_issues(
            self._selected_project, self._current_state_filter
        )
        self._current_list_request_id = rid

    def _on_issue_selected(self, iid: int):
        if self._selected_project is None:
            return
        self._issue_detail.show_loading()
        rid = self._gitlab_thread.fetch_issue_detail(self._selected_project, iid)
        self._current_detail_request_id = rid

    def closeEvent(self, event):
        """On window close: minimize to tray or fully exit."""
        if self._force_quit:
            # Exit from tray menu "Exit"
            self._gitlab_thread.shutdown()
            self._gitlab_thread.wait(5000)
            if self._discord_thread.isRunning():
                self._discord_thread.request_stop()
                if not self._discord_thread.wait(5000):
                    self._discord_thread.terminate()
                    self._discord_thread.wait(2000)
            if self._tray:
                self._tray.hide()
            event.accept()
        else:
            # Minimize to tray
            event.ignore()
            self.hide()


def _build_global_qss() -> str:
    """Generate application-wide QSS from config.COLORS."""
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
        QTabBar {{
            background-color: {c["surface"]};
            border: none;
        }}
        QTabBar::tab {{
            background-color: {c["surface"]};
            color: {c["subtext"]};
            padding: 8px 16px;
            border: none;
            border-bottom: 2px solid transparent;
        }}
        QTabBar::tab:selected {{
            color: {c["text"]};
            border-bottom: 2px solid {c["accent"]};
        }}
        QComboBox {{
            background-color: {c["surface"]};
            color: {c["text"]};
            border: 1px solid {c["subtext"]};
            border-radius: 4px;
            padding: 4px 8px;
        }}
        QPushButton {{
            background-color: {c["surface"]};
            color: {c["text"]};
            border: none;
            border-radius: 4px;
            padding: 6px 12px;
        }}
        QPushButton:hover {{
            background-color: {c["bg"]};
        }}
        QListWidget::item:selected {{
            background-color: {c["accent"]};
            color: {c["bg"]};
        }}
    """


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(_build_global_qss())

    splash = SplashScreen()
    splash.show()
    splash.set_progress(0, "Initializing...")

    window = MainWindow(splash=splash)
    window.show()
    splash.close()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
