"""WatcherB custom widgets — Phase 2.

- ProjectCard: per-project status display with progress bar
- ProjectPanel: scrollable panel of ProjectCards
- WatcherTrayIcon: system tray integration
"""

from datetime import datetime
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
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

    def __init__(self, project_name: str, parent=None):
        super().__init__(parent)
        self._project_name = project_name
        self._state = "IDLE"
        self._progress_value = 0
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            config.CARD_PADDING, config.CARD_PADDING,
            config.CARD_PADDING, config.CARD_PADDING,
        )
        layout.setSpacing(4)

        # Project name label
        self._name_label = QLabel(self._project_name)
        self._name_label.setStyleSheet(
            f"font-size: {config.FONT_SIZE_PROJECT_NAME}px; "
            f"font-weight: bold; "
            f"color: {config.COLORS['text']}; "
            f"background: transparent;"
        )
        layout.addWidget(self._name_label)

        # State label
        initial_color = config.STATE_COLORS.get("IDLE", config.COLORS["subtext"])
        self._state_label = QLabel("IDLE")
        self._state_label.setStyleSheet(
            f"font-size: {config.FONT_SIZE_STATE_LABEL}px; "
            f"color: {initial_color}; "
            f"background: transparent;"
        )
        layout.addWidget(self._state_label)

        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(config.PROGRESS_BAR_HEIGHT)
        layout.addWidget(self._progress_bar)

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

    @property
    def project_name(self) -> str:
        return self._project_name

    @property
    def state(self) -> str:
        return self._state


class ProjectPanel(QScrollArea):
    """Scrollable panel that arranges ProjectCards vertically."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards: dict[str, ProjectCard] = {}

        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._layout.setSpacing(config.CARD_SPACING)
        self._layout.addStretch()  # Top-align cards

        self.setWidget(self._container)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    def update_project(self, project_name: str, new_state: str,
                       timestamp: datetime):
        """Update project state (unknown projects are auto-added)."""
        if project_name not in self._cards:
            card = ProjectCard(project_name)
            self._cards[project_name] = card
            # Insert before stretch
            self._layout.insertWidget(self._layout.count() - 1, card)

        card = self._cards[project_name]
        card.update_state(new_state, timestamp)

    def get_state(self, project_name: str) -> Optional[str]:
        """Return the current state of the specified project."""
        card = self._cards.get(project_name)
        return card.state if card else None


class WatcherTrayIcon(QSystemTrayIcon):
    """System tray icon."""

    show_requested = Signal()
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

        menu.addSeparator()

        exit_action = QAction("Exit", menu)
        exit_action.triggered.connect(self.exit_requested.emit)
        menu.addAction(exit_action)

        self.setContextMenu(menu)

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_requested.emit()

