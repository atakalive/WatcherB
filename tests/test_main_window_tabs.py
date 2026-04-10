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


class TestQSSRules:
    def test_qlistwidget_selected_item_style(self):
        qss = _build_global_qss()
        match = re.search(r"QListWidget::item:selected\s*\{[^}]*\}", qss)
        assert match is not None, "QListWidget::item:selected rule not found"
        block = match.group(0)
        assert f'background-color: {config.COLORS["accent"]};' in block
        assert f'color: {config.COLORS["bg"]};' in block
