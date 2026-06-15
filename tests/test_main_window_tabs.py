"""Tests for MainWindow QTabBar + QStackedWidget (Issue #16)."""

import re

import pytest

import config
from discord_client import DiscordThread
from issue_browser.gitlab_client import GitLabThread
from watcher import MainWindow, _build_global_qss


@pytest.fixture
def window(qtbot, monkeypatch):
    monkeypatch.setattr(DiscordThread, "start", lambda self: None)
    monkeypatch.setattr(GitLabThread, "start", lambda self: None)
    monkeypatch.setattr(config, "STATUS_POLL_ENABLED", False)
    w = MainWindow()
    qtbot.addWidget(w)
    yield w


class TestNormalMode:
    def test_initial_state(self, window):
        assert window._tab_bar.isHidden() is True
        assert window._right_stack.currentIndex() == 0


class TestIssueMode:
    def test_project_click_enters_issue_mode(self, window):
        path = "group/proj"
        window._on_project_clicked(path)
        assert window._tab_bar.isHidden() is False
        assert window._tab_bar.currentIndex() == 1
        assert window._right_stack.currentIndex() == 1
        assert window._selected_project == path

    def test_same_project_reclick_exits(self, window):
        path = "group/proj"
        window._on_project_clicked(path)
        window._on_project_clicked(path)
        assert window._tab_bar.isHidden() is True
        assert window._right_stack.currentIndex() == 0
        assert window._selected_project is None


class TestEscape:
    def test_escape_exits_issue_mode(self, window):
        window._on_project_clicked("group/proj")
        window._on_escape()
        assert window._tab_bar.isHidden() is True
        assert window._right_stack.currentIndex() == 0
        assert window._selected_project is None

    def test_escape_noop_in_normal_mode(self, window):
        window._on_escape()
        assert window._tab_bar.isHidden() is True
        assert window._right_stack.currentIndex() == 0

    def test_escape_from_pipeline_tab_shows_messagelog(self, window):
        """§6.2 regression: Pipeline tab → Esc → MessageLog visible."""
        window._on_project_clicked("group/proj")
        window._tab_bar.setCurrentIndex(0)  # Switch to Pipeline tab
        window._on_escape()
        assert window._right_stack.currentIndex() == 0
        assert window._right_stack.currentWidget().isHidden() is False

    def test_same_project_reclick_from_issues_tab_shows_messagelog(self, window):
        """Issue Mode Issues tab → same PJ click → MessageLog visible."""
        path = "group/proj"
        window._on_project_clicked(path)
        assert window._right_stack.currentIndex() == 1
        window._on_project_clicked(path)
        assert window._right_stack.currentIndex() == 0
        assert window._right_stack.currentWidget().isHidden() is False


class TestProjectSwitch:
    def test_switch_project(self, window):
        window._on_project_clicked("group/projA")
        window._on_project_clicked("group/projB")
        assert window._selected_project == "group/projB"
        assert window._tab_bar.currentIndex() == 1

    def test_switch_from_pipeline_tab(self, window):
        """Pipeline tab selected → different PJ → Issues tab forced."""
        window._on_project_clicked("group/projA")
        window._tab_bar.setCurrentIndex(0)
        window._on_project_clicked("group/projB")
        assert window._tab_bar.currentIndex() == 1


class TestNullProjectCard:
    def test_none_project_path_card_does_not_trigger_issue_mode(self, window):
        """project_path=None dynamic card in ProjectPanel → no mode transition."""
        from datetime import datetime, timezone

        from PySide6.QtCore import QEvent, QPointF, Qt
        from PySide6.QtGui import QMouseEvent

        # Create a dynamic card (project_path=None) inside the actual ProjectPanel
        panel = window._project_panel
        panel.update_project("dynamic_pj", "IDLE", datetime.now(tz=timezone.utc))
        card = panel._dynamic_cards["dynamic_pj"]
        assert card.project_path is None

        # Track signals on the panel relay (the path MainWindow listens to)
        relay_signals = []
        panel.project_clicked.connect(lambda p: relay_signals.append(p))

        event = QMouseEvent(
            QEvent.Type.MouseButtonPress,
            QPointF(5, 5),
            QPointF(5, 5),
            Qt.LeftButton,
            Qt.LeftButton,
            Qt.NoModifier,
        )
        card.mousePressEvent(event)

        # Neither the relay signal nor MainWindow state should change
        assert relay_signals == []
        assert window._selected_project is None
        assert window._tab_bar.isHidden() is True


class TestLeftPanelFixed:
    def test_left_panel_fixed_width_after_resize(self, window, qtbot):
        from PySide6.QtWidgets import QApplication

        window.resize(config.WINDOW_WIDTH + 200, config.WINDOW_HEIGHT)
        QApplication.processEvents()
        assert window._project_panel.width() == config.LEFT_PANEL_WIDTH

    def test_left_panel_min_max_width(self, window):
        assert window._project_panel.minimumWidth() == config.LEFT_PANEL_WIDTH
        assert window._project_panel.maximumWidth() == config.LEFT_PANEL_WIDTH

    def test_left_panel_not_collapsible(self, window):
        assert window._splitter.isCollapsible(0) is False


class TestZoomQSS:
    def test_build_global_qss_contains_font_for_all_widgets(self):
        qss = _build_global_qss()
        for selector in [
            "QTextBrowser",
            "QLineEdit",
            "QListWidget",
            "QComboBox",
            "QPushButton",
        ]:
            pattern = re.compile(
                rf"(?<!\S){re.escape(selector)}\s*\{{[^}}]*font-size[^}}]*\}}",
                re.DOTALL,
            )
            assert pattern.search(qss), f"{selector} block missing font-size"
        # QComboBox QAbstractItemView
        pattern = re.compile(
            r"QComboBox\s+QAbstractItemView\s*\{[^}]*font-size[^}]*\}",
            re.DOTALL,
        )
        assert pattern.search(qss), "QComboBox QAbstractItemView block missing font-size"

    def test_zoom_in_updates_global_qss(self, window, monkeypatch):
        from PySide6.QtWidgets import QApplication

        original = config.FONT_SIZE
        monkeypatch.setattr(config, "FONT_SIZE", original)
        window._zoom_in()
        assert config.FONT_SIZE == original + 1
        qss = QApplication.instance().styleSheet()
        assert f"font-size: {config.FONT_SIZE}px" in qss
        # restore
        config.FONT_SIZE = original

    def test_zoom_reset_restores_default(self, window, monkeypatch):
        from PySide6.QtWidgets import QApplication

        monkeypatch.setattr(config, "FONT_SIZE", 20)
        window._zoom_reset()
        assert config.FONT_SIZE == 13
        qss = QApplication.instance().styleSheet()
        assert "font-size: 13px" in qss


class TestQSSRules:
    def test_qlistwidget_selected_item_style(self):
        qss = _build_global_qss()
        match = re.search(r"QListWidget::item:selected\s*\{[^}]*\}", qss)
        assert match is not None, "QListWidget::item:selected rule not found"
        block = match.group(0)
        assert f'background-color: {config.COLORS["accent"]};' in block
        assert f'color: {config.COLORS["bg"]};' in block
