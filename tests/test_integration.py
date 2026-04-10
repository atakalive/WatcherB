"""Integration tests for Issue Browser + Pipeline view non-regression (Issue #24)."""

from datetime import datetime, timezone
from unittest.mock import create_autospec

import pytest
from PySide6.QtGui import QCloseEvent

import config
from discord_client import DiscordThread
from issue_browser.gitlab_client import GitLabThread
from issue_browser.widgets import IssueListWidget
from watcher import MainWindow


@pytest.fixture
def window(qtbot, monkeypatch):
    monkeypatch.setattr(DiscordThread, "start", lambda self: None)
    monkeypatch.setattr(GitLabThread, "start", lambda self: None)
    w = MainWindow()
    qtbot.addWidget(w)
    yield w


class TestPipelineViewNonRegression:
    def test_message_log_receives_messages_during_issue_mode(self, window):
        window._on_project_clicked("group/proj")
        assert window._right_stack.currentIndex() == 1

        window._on_message_received(
            {"content": "test msg", "created_at": datetime.now(tz=timezone.utc)}
        )
        assert "test msg" in window._message_log.toPlainText()

    def test_project_card_updates_during_issue_mode(self, window):
        window._project_panel.update_project(
            "testpj", "IDLE", datetime.now(tz=timezone.utc)
        )
        window._on_project_clicked("group/proj")

        window._on_message_received(
            {
                "content": "[testpj] IDLE → IMPLEMENTATION",
                "created_at": datetime.now(tz=timezone.utc),
            }
        )
        assert window._project_panel._dynamic_cards["testpj"].state == "IMPLEMENTATION"


class TestModeTransitionCycle:
    def test_full_cycle_normal_issue_pipeline_esc_normal(self, window):
        # Initial: Normal Mode
        assert window._tab_bar.isHidden() is True
        assert window._right_stack.currentIndex() == 0
        assert window._selected_project is None

        # Enter Issue Mode
        window._on_project_clicked("group/proj")
        assert window._tab_bar.isHidden() is False
        assert window._tab_bar.currentIndex() == 1
        assert window._right_stack.currentIndex() == 1

        # Switch to Pipeline tab
        window._tab_bar.setCurrentIndex(0)
        assert window._right_stack.currentIndex() == 0

        # Switch back to Issues tab
        window._tab_bar.setCurrentIndex(1)
        assert window._right_stack.currentIndex() == 1

        # Escape → Normal Mode
        window._on_escape()
        assert window._tab_bar.isHidden() is True
        assert window._right_stack.currentIndex() == 0
        assert window._selected_project is None

    def test_project_switch_forces_issues_tab(self, window):
        window._on_project_clicked("group/projA")
        window._tab_bar.setCurrentIndex(0)  # Pipeline tab

        window._on_project_clicked("group/projB")
        assert window._tab_bar.currentIndex() == 1
        assert window._right_stack.currentIndex() == 1
        assert window._selected_project == "group/projB"


class TestShutdown:
    def test_force_quit_calls_gitlab_shutdown(self, window):
        mock_gitlab = create_autospec(GitLabThread, instance=True)
        window._gitlab_thread = mock_gitlab

        mock_discord = create_autospec(DiscordThread, instance=True)
        window._discord_thread = mock_discord
        mock_discord.isRunning.return_value = False

        window._force_quit = True
        event = QCloseEvent()
        window.closeEvent(event)

        mock_gitlab.shutdown.assert_called_once()
        mock_gitlab.wait.assert_called_once_with(5000)
        assert event.isAccepted() is True

    def test_tray_minimize_does_not_stop_gitlab(self, window):
        mock_gitlab = create_autospec(GitLabThread, instance=True)
        window._gitlab_thread = mock_gitlab

        window._force_quit = False
        event = QCloseEvent()
        window.closeEvent(event)

        mock_gitlab.shutdown.assert_not_called()
        assert event.isAccepted() is False


class TestEdgeCases:
    def test_empty_gitlab_projects_no_path_cards(self, qtbot, monkeypatch):
        monkeypatch.setattr(DiscordThread, "start", lambda self: None)
        monkeypatch.setattr(GitLabThread, "start", lambda self: None)
        monkeypatch.setattr(config, "GITLAB_PROJECTS", [])

        w = MainWindow()
        qtbot.addWidget(w)

        assert w._project_panel._path_cards == {}
        assert w._tab_bar.isHidden() is True

    def test_list_error_displays_on_matching_context(self, window):
        window._issue_list = create_autospec(IssueListWidget, instance=True)
        window._selected_project = "group/proj"
        window._current_state_filter = "opened"
        window._current_list_request_id = 42

        # Matching context → show_error called
        window._on_list_error("group/proj", "opened", 42, "Connection timeout")
        window._issue_list.show_error.assert_called_once_with("Connection timeout")

        # Stale rid → ignored
        window._on_list_error("group/proj", "opened", 99, "Other error")
        assert window._issue_list.show_error.call_count == 1

        # Wrong project → ignored
        window._on_list_error("other/proj", "opened", 42, "Wrong project")
        assert window._issue_list.show_error.call_count == 1

        # Wrong state → ignored
        window._on_list_error("group/proj", "closed", 42, "Wrong state")
        assert window._issue_list.show_error.call_count == 1
