"""WatcherB custom widgets — Phase 2.

- ProjectCard: per-project status display with progress bar
- ProjectPanel: scrollable panel of ProjectCards
- WatcherTrayIcon: system tray integration
"""

from datetime import datetime
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMenu,
    QProgressBar,
    QScrollArea,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

import config


class ProjectCard(QWidget):
    """Status card for a single project."""

    clicked = Signal(str)  # project_path を emit

    def __init__(self, display_name: str, project_path: str | None = None, parent=None):
        super().__init__(parent)
        self._display_name = display_name
        self._project_path = project_path
        self._state: str | None = None
        self._selected = False
        self._progress_value = 0
        self._setup_ui()
        if self._project_path is not None:
            self.setCursor(Qt.PointingHandCursor)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            config.CARD_PADDING, config.CARD_PADDING,
            config.CARD_PADDING, config.CARD_PADDING,
        )
        layout.setSpacing(4)

        # Project name label
        self._name_label = QLabel(self._display_name)
        self._name_label.setStyleSheet(
            f"font-size: {config.FONT_SIZE_PROJECT_NAME}px; "
            f"font-weight: bold; "
            f"color: {config.COLORS['text']}; "
            f"background: transparent;"
        )
        layout.addWidget(self._name_label)

        # State label
        self._state_label = QLabel("")
        layout.addWidget(self._state_label)

        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(config.PROGRESS_BAR_HEIGHT)
        layout.addWidget(self._progress_bar)

        # Issue label (clickable links to GitLab)
        self._issue_label = QLabel("")
        self._issue_label.setStyleSheet(
            f"font-size: {config.FONT_SIZE_UPDATE_TIME}px; "
            f"color: {config.COLORS['accent']}; "
            f"background: transparent;"
        )
        self._issue_label.setOpenExternalLinks(True)
        self._issue_label.setTextFormat(Qt.RichText)
        self._issue_label.hide()
        layout.addWidget(self._issue_label)

        # Last update time label
        self._time_label = QLabel("")
        self._time_label.setStyleSheet(
            f"font-size: {config.FONT_SIZE_UPDATE_TIME}px; "
            f"color: {config.COLORS['subtext']}; "
            f"background: transparent;"
        )
        layout.addWidget(self._time_label)

        # Card background
        self.setStyleSheet(
            f"ProjectCard {{ "
            f"  background-color: {config.COLORS['surface']}; "
            f"  border-radius: {config.CARD_BORDER_RADIUS}px; "
            f"}}"
        )

        # State label initial value
        if self._state is None:
            self._state_label.setText("─")
            self._state_label.setStyleSheet(
                f"font-size: {config.FONT_SIZE_STATE_LABEL}px; "
                f"color: {config.COLORS['subtext']}; background: transparent;"
            )
            self._progress_bar.setValue(0)
        else:
            color = config.STATE_COLORS.get(self._state, config.COLORS["subtext"])
            self._state_label.setText(self._state)
            self._state_label.setStyleSheet(
                f"font-size: {config.FONT_SIZE_STATE_LABEL}px; "
                f"color: {color}; background: transparent;"
            )

    def update_state(self, new_state: str, timestamp: datetime):
        """Update state and refresh display."""
        self._state = new_state
        color = config.STATE_COLORS.get(new_state, config.COLORS["subtext"])

        self._state_label.setText(new_state)
        self._state_label.setStyleSheet(
            f"font-size: {config.FONT_SIZE_STATE_LABEL}px; "
            f"font-weight: bold; "
            f"color: {color}; "
            f"background: transparent;"
        )

        progress = config.STATE_PROGRESS.get(new_state, 0)
        if progress == -1:
            # BLOCKED: freeze at current value, change chunk to red
            self._progress_bar.setStyleSheet(
                f"QProgressBar::chunk {{ background-color: {config.COLORS['red']}; }}"
            )
        else:
            self._progress_value = progress
            self._progress_bar.setValue(progress)
            self._progress_bar.setStyleSheet(
                f"QProgressBar::chunk {{ background-color: {config.COLORS['accent']}; }}"
            )

        local_time = timestamp.astimezone()
        self._time_label.setText(f"Updated: {local_time.strftime('%H:%M')}")

        if new_state in ("IDLE", "DONE"):
            self.update_issues([])

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._project_path is not None:
            self.clicked.emit(self._project_path)
        super().mousePressEvent(event)

    def set_selected(self, selected: bool):
        self._selected = selected
        if selected:
            self.setStyleSheet(
                f"ProjectCard {{ background-color: {config.COLORS['surface']}; "
                f"border-radius: {config.CARD_BORDER_RADIUS}px; "
                f"border-left: 3px solid {config.COLORS['accent']}; }}"
            )
        else:
            self.setStyleSheet(
                f"ProjectCard {{ background-color: {config.COLORS['surface']}; "
                f"border-radius: {config.CARD_BORDER_RADIUS}px; }}"
            )

    def update_issues(self, issues: list[int]) -> None:
        """Update displayed Issue numbers. Empty list hides the label."""
        if not issues:
            self._issue_label.hide()
            return
        if self._state in ("IDLE", "DONE"):
            return
        base = config.GITLAB_BASE_URL.rstrip("/")
        pj = self._project_path if self._project_path is not None else self._display_name
        links = ", ".join(
            f'<a href="{base}/{pj}/-/issues/{n}" style="color: {config.COLORS["accent"]};">#{n}</a>'
            for n in issues
        )
        self._issue_label.setText(f"Issue: {links}")
        self._issue_label.show()

    def set_display_name(self, name: str) -> None:
        """collision 状態変化で display name が切り替わる場合に呼ぶ。
        同じ name での反復呼出は冪等（QLabel.setText は no-op 扱い）。"""
        self._display_name = name
        self._name_label.setText(name)

    @property
    def project_path(self) -> str | None:
        return self._project_path

    @property
    def display_name(self) -> str:
        return self._display_name

    @property
    def state(self) -> str | None:
        return self._state


class ProjectPanel(QScrollArea):
    """Scrollable panel that arranges ProjectCards vertically."""

    project_clicked = Signal(str)  # project_path をリレー

    def __init__(self, parent=None):
        super().__init__(parent)
        self._path_cards: dict[str, ProjectCard] = {}     # キー: project_path
        self._dynamic_cards: dict[str, ProjectCard] = {}   # キー: discord_name
        self._name_to_path: dict[str, str] = {}            # Discord短縮名 → フルパス
        self._collided_names: set[str] = set()
        self._selected_card: ProjectCard | None = None

        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._layout.setSpacing(config.CARD_SPACING)
        self._layout.addStretch()  # Top-align cards

        self.setWidget(self._container)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._prepopulate()

    def _prepopulate(self):
        """起動時に GITLAB_PROJECTS の全エントリに対して ProjectCard を生成。"""
        self._rebuild_name_resolution(config.GITLAB_PROJECTS)

        for path in config.GITLAB_PROJECTS:
            short = path.rsplit("/", 1)[-1]
            display = path if short in self._collided_names else short
            card = ProjectCard(display_name=display, project_path=path)
            card.clicked.connect(self._on_card_clicked)
            self._path_cards[path] = card
            self._layout.insertWidget(self._layout.count() - 1, card)

        if self._collided_names:
            import logging
            logger = logging.getLogger(__name__)
            for short in sorted(self._collided_names):
                logger.warning("Display name collision for '%s' — using full paths", short)

    def _rebuild_name_resolution(self, paths: list[str]) -> None:
        short_to_paths: dict[str, list[str]] = {}
        for path in paths:
            short = path.rsplit("/", 1)[-1]
            short_to_paths.setdefault(short, []).append(path)
        self._name_to_path = {
            short: plist[0] for short, plist in short_to_paths.items() if len(plist) == 1
        }
        self._collided_names = {
            short for short, plist in short_to_paths.items() if len(plist) > 1
        }

    def refresh_projects(self) -> set[str]:
        """現在の config.GITLAB_PROJECTS と _path_cards を同期する。

        Returns:
            今回の refresh で _path_cards から削除された project_path の集合。
        """
        new_paths = list(config.GITLAB_PROJECTS)
        removed = set(self._path_cards) - set(new_paths)

        for path in removed:
            card = self._path_cards.pop(path)
            if self._selected_card is card:
                self._selected_card = None
            self._layout.removeWidget(card)
            card.deleteLater()

        for card in self._path_cards.values():
            self._layout.removeWidget(card)

        self._rebuild_name_resolution(new_paths)

        for i, path in enumerate(new_paths):
            short = path.rsplit("/", 1)[-1]
            display = path if short in self._collided_names else short
            if path in self._path_cards:
                card = self._path_cards[path]
                card.set_display_name(display)
            else:
                card = ProjectCard(display_name=display, project_path=path)
                card.clicked.connect(self._on_card_clicked)
                self._path_cards[path] = card
            self._layout.insertWidget(i, card)

        return removed

    def _on_card_clicked(self, project_path: str):
        self.project_clicked.emit(project_path)

    def select_project(self, project_path: str | None):
        """指定プロジェクトを選択表示。None で選択解除。"""
        if self._selected_card is not None:
            self._selected_card.set_selected(False)
            self._selected_card = None
        if project_path is not None:
            card = self._path_cards.get(project_path)
            if card is not None:
                card.set_selected(True)
                self._selected_card = card

    def update_project(self, discord_name: str, new_state: str,
                       timestamp: datetime):
        """プロジェクト状態を更新。Discord名から名前解決を試みる。"""
        project_path = self._name_to_path.get(discord_name)
        if project_path is not None:
            card = self._path_cards.get(project_path)
            if card is not None:
                card.update_state(new_state, timestamp)
                return

        if discord_name in self._collided_names:
            import logging
            logging.getLogger(__name__).debug(
                "Ambiguous Discord name '%s' (collides with multiple projects) — skipped",
                discord_name,
            )
            return

        if discord_name not in self._dynamic_cards:
            card = ProjectCard(display_name=discord_name, project_path=None)
            card.clicked.connect(self._on_card_clicked)
            self._dynamic_cards[discord_name] = card
            self._layout.insertWidget(self._layout.count() - 1, card)

        self._dynamic_cards[discord_name].update_state(new_state, timestamp)

    def update_issues(self, discord_name: str, issues: list[int]) -> None:
        """Issue 番号を更新。discord_name から名前解決し、該当カードを更新。"""
        project_path = self._name_to_path.get(discord_name)
        if project_path is not None:
            card = self._path_cards.get(project_path)
            if card is not None:
                card.update_issues(issues)
                return

        if discord_name in self._collided_names:
            return

        card = self._dynamic_cards.get(discord_name)
        if card is not None:
            card.update_issues(issues)

    def get_state(self, discord_name: str) -> Optional[str]:
        """プロジェクトの現在の状態を返す。名前解決を経由して検索。"""
        project_path = self._name_to_path.get(discord_name)
        if project_path is not None:
            card = self._path_cards.get(project_path)
            if card is not None:
                return card.state

        if discord_name in self._collided_names:
            return None

        card = self._dynamic_cards.get(discord_name)
        return card.state if card is not None else None


class WatcherTrayIcon(QSystemTrayIcon):
    """System tray icon."""

    show_requested = Signal()
    reload_requested = Signal()
    exit_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_icon()
        self._setup_menu()
        self.setToolTip(config.TRAY_TOOLTIP)
        self.activated.connect(self._on_activated)

    def _setup_icon(self):
        """Set icon.jpg as the tray icon."""
        icon_path = str(config.ICON_PATH)
        self.setIcon(QIcon(icon_path))

    def _setup_menu(self):
        menu = QMenu()

        show_action = QAction("Show", menu)
        show_action.triggered.connect(self.show_requested.emit)
        menu.addAction(show_action)

        reload_action = QAction("Reload", menu)
        reload_action.triggered.connect(self.reload_requested.emit)
        menu.addAction(reload_action)

        menu.addSeparator()

        exit_action = QAction("Exit", menu)
        exit_action.triggered.connect(self.exit_requested.emit)
        menu.addAction(exit_action)

        self.setContextMenu(menu)

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_requested.emit()


class SplashScreen(QWidget):
    """Startup splash screen with progress indicator."""

    def __init__(self):
        super().__init__()
        self._drag_pos = None
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(config.SPLASH_WIDTH, config.SPLASH_HEIGHT)
        self._setup_ui()
        self._center_on_screen()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        # App name label
        self._title_label = QLabel("WatcherB")
        self._title_label.setStyleSheet(
            f"font-size: {config.FONT_SIZE_PROJECT_NAME + 4}px; "
            f"font-weight: bold; "
            f"color: {config.COLORS['text']}; "
            f"background: transparent;"
        )
        self._title_label.setAlignment(Qt.AlignHCenter)
        layout.addWidget(self._title_label, alignment=Qt.AlignHCenter)

        # Status label
        self._status_label = QLabel("Initializing...")
        self._status_label.setStyleSheet(
            f"font-size: {config.FONT_SIZE_STATE_LABEL}px; "
            f"color: {config.COLORS['subtext']}; "
            f"background: transparent;"
        )
        self._status_label.setAlignment(Qt.AlignHCenter)
        layout.addWidget(self._status_label, alignment=Qt.AlignHCenter)

        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(config.PROGRESS_BAR_HEIGHT)
        layout.addWidget(self._progress_bar)

    def _center_on_screen(self):
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(config.COLORS["surface"]))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.rect(), 12, 12)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self._drag_pos is not None:
            new_pos = event.globalPosition().toPoint() - self._drag_pos
            screen = QApplication.primaryScreen().availableGeometry()
            clamped_x = max(screen.left(), min(new_pos.x(), screen.right() - self.width()))
            clamped_y = max(screen.top(), min(new_pos.y(), screen.bottom() - self.height()))
            self.move(clamped_x, clamped_y)
            event.accept()

    def set_progress(self, value: int, status: str) -> None:
        """Update progress value (0-100) and status message."""
        self._progress_bar.setValue(value)
        self._status_label.setText(status)
        QApplication.processEvents()

