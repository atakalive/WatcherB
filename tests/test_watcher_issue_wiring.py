"""Tests for MainWindow issue browser wiring (Issue #22)."""

from unittest.mock import create_autospec

import pytest

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QLineEdit

import config
from discord_client import DiscordThread
from issue_browser.gitlab_client import GitLabThread
from issue_browser.widgets import IssueDetailWidget, IssueListWidget
from watcher import MainWindow


@pytest.fixture
def window(qtbot, monkeypatch):
    monkeypatch.setattr(DiscordThread, "start", lambda self: None)
    monkeypatch.setattr(GitLabThread, "start", lambda self: None)

    w = MainWindow()
    qtbot.addWidget(w)

    # Replace real widgets/thread with mocks for verification
    w._gitlab_thread = create_autospec(GitLabThread, instance=True)
    w._issue_list = create_autospec(IssueListWidget, instance=True)
    w._issue_detail = create_autospec(IssueDetailWidget, instance=True)

    # Default: fetch_issues returns incrementing request_ids
    w._gitlab_thread.fetch_issues.side_effect = iter(range(1, 100))
    w._gitlab_thread.fetch_issue_detail.side_effect = iter(range(101, 200))

    yield w


class TestProjectClickCacheMiss:
    def test_project_click_cache_miss(self, window):
        """PJ クリック（cache なし）→ show_loading + fetch_issues + rid 更新。"""
        window._on_project_clicked("group/proj")

        window._issue_list.show_loading.assert_called_once()
        window._gitlab_thread.fetch_issues.assert_called_once_with(
            "group/proj", "opened"
        )
        assert window._current_list_request_id == 1


class TestProjectClickCacheHit:
    def test_project_click_cache_hit(self, window):
        """cache 事前設定 → PJ クリック → populate 即座 + rid == -1 + fetch 未呼び出し。"""
        issues = [{"iid": 1, "title": "t"}]
        window._issue_cache[("group/proj", "opened")] = (issues, False)

        window._on_project_clicked("group/proj")

        window._issue_list.populate.assert_called_once_with(issues, truncated=False)
        assert window._current_list_request_id == -1
        window._gitlab_thread.fetch_issues.assert_not_called()


class TestProjectClickDetailReset:
    def test_project_click_detail_reset(self, window):
        """PJ クリック → show_blank (detail) + detail rid == -1。"""
        window._on_project_clicked("group/proj")

        window._issue_detail.show_blank.assert_called_once()
        assert window._current_detail_request_id == -1


class TestProjectClickResetsFilter:
    def test_project_click_resets_filter(self, window):
        """PJ-A で closed 設定後、PJ-B クリック → reset_filter + state == opened。"""
        window._current_state_filter = "closed"
        window._on_project_clicked("group/projB")

        window._issue_list.reset_filter.assert_called_once()
        assert window._current_state_filter == "opened"


class TestStaleListResponseDiscarded:
    def test_stale_list_response_discarded(self, window):
        """A(rid=1) → B(rid=2) → on_issues_loaded(A, rid=1) → populate 未呼び出し。"""
        window._on_project_clicked("group/projA")  # rid=1
        window._on_project_clicked("group/projB")  # rid=2

        window._issue_list.populate.reset_mock()
        window._on_issues_loaded("group/projA", "opened", 1, False, [])

        window._issue_list.populate.assert_not_called()


class TestStaleListResponseProjectMismatch:
    def test_stale_list_response_project_mismatch(self, window):
        """rid 一致だが project 不一致 → 破棄（cache にも格納されない）。"""
        window._on_project_clicked("group/projA")  # rid=1
        rid = window._current_list_request_id

        # Simulate: project doesn't match current (manually set different project)
        window._selected_project = "group/projB"

        window._issue_list.populate.reset_mock()
        window._on_issues_loaded("group/projA", "opened", rid, False, [{"iid": 1}])

        window._issue_list.populate.assert_not_called()
        assert ("group/projA", "opened") not in window._issue_cache


class TestStaleDetailResponseDiscarded:
    def test_stale_detail_response_discarded(self, window):
        """detail rid 不一致 → show_detail 未呼び出し。"""
        window._current_detail_request_id = 10
        window._on_issue_detail_loaded("group/proj", 5, 9, {"iid": 5})

        window._issue_detail.show_detail.assert_not_called()


class TestIssuesLoadedUpdatesCache:
    def test_issues_loaded_updates_cache(self, window):
        """_on_issues_loaded → cache に格納。"""
        window._selected_project = "group/proj"
        window._current_state_filter = "opened"
        window._current_list_request_id = 42

        issues = [{"iid": 1}, {"iid": 2}]
        window._on_issues_loaded("group/proj", "opened", 42, True, issues)

        assert window._issue_cache[("group/proj", "opened")] == (issues, True)


class TestFilterChangeCacheMiss:
    def test_filter_change_cache_miss(self, window):
        """filter 変更（cache なし）→ show_loading + fetch + detail リセット。"""
        window._selected_project = "group/proj"

        window._on_filter_changed("closed")

        window._issue_list.show_loading.assert_called_once()
        window._gitlab_thread.fetch_issues.assert_called_once_with(
            "group/proj", "closed"
        )
        window._issue_detail.show_blank.assert_called_once()
        assert window._current_detail_request_id == -1


class TestFilterChangeCacheHit:
    def test_filter_change_cache_hit(self, window):
        """filter 変更（cache あり）→ populate 即座 + rid == -1。"""
        window._selected_project = "group/proj"
        issues = [{"iid": 3}]
        window._issue_cache[("group/proj", "closed")] = (issues, False)

        window._on_filter_changed("closed")

        window._issue_list.populate.assert_called_once_with(issues, truncated=False)
        assert window._current_list_request_id == -1


class TestReloadInvalidatesCache:
    def test_reload_invalidates_cache(self, window):
        """cache に opened/closed 設定 → reload → 両方削除 + fetch。"""
        window._selected_project = "group/proj"
        window._current_state_filter = "opened"
        window._issue_cache[("group/proj", "opened")] = ([], False)
        window._issue_cache[("group/proj", "closed")] = ([], False)

        window._on_reload_requested()

        assert ("group/proj", "opened") not in window._issue_cache
        assert ("group/proj", "closed") not in window._issue_cache
        window._gitlab_thread.fetch_issues.assert_called_once_with(
            "group/proj", "opened"
        )


class TestReloadReselectsIid:
    def test_reload_reselects_iid(self, window):
        """selected_iid=5 → reload → on_issues_loaded → select_by_iid(5)。"""
        window._selected_project = "group/proj"
        window._current_state_filter = "opened"
        window._issue_list.selected_iid.return_value = 5

        window._on_reload_requested()
        rid = window._current_list_request_id

        issues = [{"iid": 5}, {"iid": 6}]
        window._on_issues_loaded("group/proj", "opened", rid, False, issues)

        window._issue_list.select_by_iid.assert_called_once_with(5)


class TestReloadReselectIidNotInNewList:
    def test_reload_reselect_iid_not_in_new_list(self, window):
        """reload 後、select_by_iid(5) は呼ばれるが False を返す。"""
        window._selected_project = "group/proj"
        window._current_state_filter = "opened"
        window._issue_list.selected_iid.return_value = 5
        window._issue_list.select_by_iid.return_value = False

        window._on_reload_requested()
        rid = window._current_list_request_id

        issues = [{"iid": 10}]
        window._on_issues_loaded("group/proj", "opened", rid, False, issues)

        window._issue_list.select_by_iid.assert_called_once_with(5)


class TestExitIssueModeInvalidatesRequestIds:
    def test_exit_issue_mode_invalidates_request_ids(self, window):
        """_exit_issue_mode → rid == -1 (both)。"""
        window._current_list_request_id = 10
        window._current_detail_request_id = 20

        window._exit_issue_mode()

        assert window._current_list_request_id == -1
        assert window._current_detail_request_id == -1


class TestListErrorShown:
    def test_list_error_shown(self, window):
        """matching rid → show_error(message)。"""
        window._selected_project = "group/proj"
        window._current_state_filter = "opened"
        window._current_list_request_id = 7

        window._on_list_error("group/proj", "opened", 7, "timeout")

        window._issue_list.show_error.assert_called_once_with("timeout")


class TestListErrorStaleDiscarded:
    def test_list_error_stale_discarded(self, window):
        """non-matching rid → show_error 未呼び出し。"""
        window._current_list_request_id = 7

        window._on_list_error("group/proj", "opened", 6, "timeout")

        window._issue_list.show_error.assert_not_called()


class TestDetailErrorShown:
    def test_detail_error_shown(self, window):
        """matching rid → show_error (detail)。"""
        window._current_detail_request_id = 15

        window._on_detail_error("group/proj", 5, 15, "not found")

        window._issue_detail.show_error.assert_called_once_with("not found")


class TestIssueSelectedFetchesDetail:
    def test_issue_selected_fetches_detail(self, window):
        """_on_issue_selected(5) → show_loading + fetch_issue_detail + rid 更新。"""
        window._selected_project = "group/proj"

        window._on_issue_selected(5)

        window._issue_detail.show_loading.assert_called_once()
        window._gitlab_thread.fetch_issue_detail.assert_called_once_with(
            "group/proj", 5
        )
        assert window._current_detail_request_id == 101


class TestCacheHitInvalidatesInflight:
    def test_cache_hit_invalidates_inflight(self, window):
        """cache hit → rid == -1 → 古い stale response は破棄。"""
        issues = [{"iid": 1}]
        window._issue_cache[("group/proj", "opened")] = (issues, False)

        window._on_project_clicked("group/proj")
        assert window._current_list_request_id == -1

        # Stale response arrives with some old rid
        window._issue_list.populate.reset_mock()
        window._on_issues_loaded("group/proj", "opened", 5, False, [{"iid": 99}])
        window._issue_list.populate.assert_not_called()


class TestReloadThenProjectSwitchClearsReselect:
    def test_reload_then_project_switch_clears_reselect(self, window):
        """reload(iid=5) → PJ 切替 → _reload_selected_iid == None。"""
        window._selected_project = "group/projA"
        window._current_state_filter = "opened"
        window._issue_list.selected_iid.return_value = 5

        window._on_reload_requested()
        assert window._reload_selected_iid == 5

        reload_rid = window._current_list_request_id

        # PJ switch clears reselect
        window._on_project_clicked("group/projB")
        assert window._reload_selected_iid is None

        # Late response from reload should not trigger select_by_iid
        window._issue_list.select_by_iid.reset_mock()
        window._on_issues_loaded(
            "group/projA", "opened", reload_rid, False, [{"iid": 5}]
        )
        window._issue_list.select_by_iid.assert_not_called()


class TestReloadThenFilterChangeClearsReselect:
    def test_reload_then_filter_change_clears_reselect(self, window):
        """reload(iid=5) → filter 変更 → _reload_selected_iid == None。"""
        window._selected_project = "group/proj"
        window._current_state_filter = "opened"
        window._issue_list.selected_iid.return_value = 5

        window._on_reload_requested()
        assert window._reload_selected_iid == 5

        reload_rid = window._current_list_request_id

        # Filter change clears reselect
        window._on_filter_changed("closed")
        assert window._reload_selected_iid is None

        # Late response from reload should not trigger select_by_iid
        window._issue_list.select_by_iid.reset_mock()
        window._on_issues_loaded(
            "group/proj", "opened", reload_rid, False, [{"iid": 5}]
        )
        window._issue_list.select_by_iid.assert_not_called()


class TestOpenIssueInBrowser:
    def test_open_issue_in_browser_url(self, window, monkeypatch):
        """_open_issue_in_browser builds correct URL and calls QDesktopServices.openUrl."""
        opened_urls = []
        monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened_urls.append(url))

        window._selected_project = "user/repo"
        window._open_issue_in_browser(42)

        assert len(opened_urls) == 1
        assert opened_urls[0] == QUrl(f"{config.GITLAB_URL}/user/repo/-/issues/42")

    def test_open_issue_in_browser_wiring(self, qtbot, monkeypatch):
        """Integration: open_in_browser signal → QDesktopServices.openUrl."""
        monkeypatch.setattr(DiscordThread, "start", lambda self: None)
        monkeypatch.setattr(GitLabThread, "start", lambda self: None)

        opened_urls = []
        monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened_urls.append(url))

        w = MainWindow()
        qtbot.addWidget(w)
        w._selected_project = "group/proj"

        w._issue_list.open_in_browser.emit(42)

        assert len(opened_urls) == 1
        assert opened_urls[0] == QUrl(f"{config.GITLAB_URL}/group/proj/-/issues/42")


class TestOpenIssuesPageInBrowser:
    def test_open_issues_page_in_browser_url(self, window, monkeypatch):
        """_open_issues_page_in_browser builds correct URL and calls QDesktopServices.openUrl."""
        opened_urls: list[QUrl] = []
        monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened_urls.append(url))

        window._open_issues_page_in_browser("user/repo")

        expected = (
            f"{config.GITLAB_URL}/user/repo/-/work_items"
            f"?sort=created_date&state=all&first_page_size=100"
        )
        assert len(opened_urls) == 1
        assert opened_urls[0] == QUrl(expected)

    def test_open_issues_page_in_browser_wiring(self, qtbot, monkeypatch):
        """Integration: project_panel.open_issues_page_requested signal → QDesktopServices.openUrl."""
        monkeypatch.setattr(DiscordThread, "start", lambda self: None)
        monkeypatch.setattr(GitLabThread, "start", lambda self: None)

        opened_urls: list[QUrl] = []
        monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened_urls.append(url))

        w = MainWindow()
        qtbot.addWidget(w)

        w._project_panel.open_issues_page_requested.emit("group/proj")

        expected = (
            f"{config.GITLAB_URL}/group/proj/-/work_items"
            f"?sort=created_date&state=all&first_page_size=100"
        )
        assert len(opened_urls) == 1
        assert opened_urls[0] == QUrl(expected)


class TestDoubleClickQadd:
    def test_double_click_sets_qadd_text(self, window, monkeypatch):
        """_on_issue_double_clicked sets qadd text and calls setFocus."""
        line_edit = QLineEdit()
        focus_calls = []
        monkeypatch.setattr(line_edit, "setFocus", lambda: focus_calls.append(True))
        window._send_input = line_edit
        window._selected_project = "user/myrepo"

        window._on_issue_double_clicked(42)

        assert window._send_input.text() == "qadd myrepo 42 "
        assert focus_calls == [True], "setFocus() should be called"

    def test_double_click_send_disabled(self, window):
        """_on_issue_double_clicked with _send_input=None does not crash."""
        window._send_input = None
        window._selected_project = "user/repo"

        window._on_issue_double_clicked(42)  # should not raise

    def test_double_click_wiring(self, qtbot, monkeypatch):
        """Integration: issue_double_clicked signal → _send_input gets qadd text."""
        monkeypatch.setattr(DiscordThread, "start", lambda self: None)
        monkeypatch.setattr(GitLabThread, "start", lambda self: None)
        monkeypatch.setattr(config, "SEND_ENABLED", True)

        w = MainWindow()
        qtbot.addWidget(w)

        assert w._send_input is not None
        w._selected_project = "group/proj"

        w._issue_list.issue_double_clicked.emit(10)

        assert w._send_input.text() == "qadd proj 10 "
