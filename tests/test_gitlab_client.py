"""Tests for GitLabThread (Issue #17, #18)."""

from unittest.mock import MagicMock

import pytest
import requests

import config
from issue_browser.gitlab_client import (
    GitLabThread,
    _LINK_NEXT_RE,
    _REQUEST_TIMEOUT,
    _ShutdownInterrupt,
)


@pytest.fixture
def thread(qtbot):
    t = GitLabThread()
    yield t
    t.shutdown()
    t.wait(2000)


class TestRequestId:
    def test_fetch_issues_returns_positive_int(self, thread):
        rid = thread.fetch_issues("group/proj", "opened")
        assert rid >= 1

    def test_fetch_issues_increments(self, thread):
        rid1 = thread.fetch_issues("group/proj", "opened")
        rid2 = thread.fetch_issues("group/proj", "closed")
        assert rid2 == rid1 + 1

    def test_fetch_issue_detail_returns_positive_int(self, thread):
        rid = thread.fetch_issue_detail("group/proj", 42)
        assert rid >= 1


class TestShutdown:
    def test_shutdown_stops_thread(self, qtbot):
        thread = GitLabThread()
        thread.start()
        thread.shutdown()
        assert thread.wait(5000)

    def test_shutdown_before_start(self, qtbot):
        thread = GitLabThread()
        thread.shutdown()


class TestLinkHeaderParsing:
    def test_link_next_regex(self):
        header = '<https://gitlab.com/api/v4/projects/1/issues?page=2>; rel="next", <https://gitlab.com/api/v4/projects/1/issues?page=5>; rel="last"'
        match = _LINK_NEXT_RE.search(header)
        assert match is not None
        assert match.group(1) == "https://gitlab.com/api/v4/projects/1/issues?page=2"

    def test_link_no_next(self):
        header = '<https://gitlab.com/api/v4/projects/1/issues?page=5>; rel="last"'
        match = _LINK_NEXT_RE.search(header)
        assert match is None

    def test_link_empty(self):
        match = _LINK_NEXT_RE.search("")
        assert match is None


class TestFetchAllPages:
    def test_truncated_at_max_pages(self, thread, monkeypatch):
        monkeypatch.setattr(config, "MAX_PAGES", 2)

        call_count = 0
        def mock_get(url, params=None, timeout=None):
            nonlocal call_count
            call_count += 1
            resp = MagicMock()
            resp.json.return_value = [{"iid": call_count}]
            resp.headers = {"Link": f'<http://next/{call_count+1}>; rel="next"'}
            resp.raise_for_status = MagicMock()
            return resp

        thread._session.get = mock_get
        items, truncated = thread._fetch_all_pages("http://test", {})
        assert truncated is True
        assert len(items) == 2

    def test_no_truncation(self, thread):
        def mock_get(url, params=None, timeout=None):
            resp = MagicMock()
            resp.json.return_value = [{"iid": 1}]
            resp.headers = {}
            resp.raise_for_status = MagicMock()
            return resp

        thread._session.get = mock_get
        items, truncated = thread._fetch_all_pages("http://test", {})
        assert truncated is False
        assert len(items) == 1

    def test_shutdown_during_fetch_raises(self, thread):
        thread._shutdown = True
        with pytest.raises(_ShutdownInterrupt):
            thread._fetch_all_pages("http://test", {})

    def test_multi_page_concatenation(self, thread):
        call_count = 0
        pages = [
            [{"iid": 1}, {"iid": 2}],
            [{"iid": 3}],
            [{"iid": 4}, {"iid": 5}],
        ]

        def mock_get(url, params=None, timeout=None):
            nonlocal call_count
            idx = call_count
            call_count += 1
            resp = MagicMock()
            resp.json.return_value = pages[idx]
            resp.raise_for_status = MagicMock()
            if idx < 2:
                resp.headers = {"Link": f'<http://next/page{idx+2}>; rel="next"'}
            else:
                resp.headers = {}
            return resp

        thread._session.get = mock_get
        items, truncated = thread._fetch_all_pages("http://test", {"per_page": "100"})
        assert truncated is False
        assert len(items) == 5
        assert [i["iid"] for i in items] == [1, 2, 3, 4, 5]

    def test_params_cleared_after_first_page(self, thread):
        calls = []

        def mock_get(url, params=None, timeout=None):
            calls.append({"url": url, "params": params})
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            resp.json.return_value = [{"iid": len(calls)}]
            if len(calls) == 1:
                resp.headers = {"Link": '<http://next/page2>; rel="next"'}
            else:
                resp.headers = {}
            return resp

        thread._session.get = mock_get
        thread._fetch_all_pages("http://test", {"state": "opened", "per_page": "100"})
        assert len(calls) == 2
        assert calls[1]["params"] == {}

    def test_http_error_discards_partial(self, thread):
        call_count = 0

        def mock_get(url, params=None, timeout=None):
            nonlocal call_count
            call_count += 1
            resp = MagicMock()
            if call_count == 1:
                resp.json.return_value = [{"iid": 1}]
                resp.headers = {"Link": '<http://next/page2>; rel="next"'}
                resp.raise_for_status = MagicMock()
            else:
                resp.raise_for_status.side_effect = requests.HTTPError("500 Server Error")
            return resp

        thread._session.get = mock_get
        with pytest.raises(requests.HTTPError):
            thread._fetch_all_pages("http://test", {})


class TestProcessDetailRequest:
    def test_system_notes_excluded(self, thread):
        call_count = 0
        def mock_get(url, params=None, timeout=None):
            nonlocal call_count
            call_count += 1
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            resp.headers = {}
            if call_count == 1:
                resp.json.return_value = {"iid": 1, "title": "test"}
            else:
                resp.json.return_value = [
                    {"id": 1, "body": "user note", "system": False},
                    {"id": 2, "body": "system note", "system": True},
                    {"id": 3, "body": "another user note"},
                ]
            return resp

        thread._session.get = mock_get
        results = []
        thread.issue_detail_loaded.connect(lambda *args: results.append(args))
        thread._process_detail_request("group/proj", 1, 1)
        assert len(results) == 1
        detail = results[0][3]
        assert len(detail["_notes"]) == 2
        assert all(not n.get("system", False) for n in detail["_notes"])

    def test_shutdown_before_request(self, thread):
        thread._shutdown = True
        with pytest.raises(_ShutdownInterrupt):
            thread._process_detail_request("group/proj", 1, 1)


class TestProcessListRequest:
    def test_list_error_signal(self, thread):
        def mock_get(url, params=None, timeout=None):
            raise ConnectionError("Network error")

        thread._session.get = mock_get
        errors = []
        thread.list_error.connect(lambda *args: errors.append(args))
        thread._process_list_request("group/proj", "opened", 1)
        assert len(errors) == 1
        assert "Network error" in errors[0][3]

    def test_url_encoding_subgroup(self, thread):
        calls = []

        def mock_get(url, params=None, timeout=None):
            calls.append(url)
            resp = MagicMock()
            resp.json.return_value = []
            resp.headers = {}
            resp.raise_for_status = MagicMock()
            return resp

        thread._session.get = mock_get
        thread._process_list_request("group/sub/proj", "opened", 1)
        assert len(calls) == 1
        assert f"{config.GITLAB_URL}/api/v4/projects/group%2Fsub%2Fproj/issues" == calls[0]

    def test_issues_loaded_signal_params(self, thread):
        def mock_get(url, params=None, timeout=None):
            resp = MagicMock()
            resp.json.return_value = [{"iid": 10, "title": "test"}]
            resp.headers = {}
            resp.raise_for_status = MagicMock()
            return resp

        thread._session.get = mock_get
        results = []
        thread.issues_loaded.connect(lambda *args: results.append(args))
        thread._process_list_request("group/proj", "opened", 42)
        assert len(results) == 1
        project, state, request_id, truncated, issues = results[0]
        assert project == "group/proj"
        assert state == "opened"
        assert request_id == 42
        assert truncated is False
        assert isinstance(issues, list)
        assert len(issues) == 1
        assert issues[0]["iid"] == 10

    def test_private_token_header(self, qtbot, monkeypatch):
        monkeypatch.setattr(config, "GITLAB_TOKEN", "test-token-123")
        t = GitLabThread()
        try:
            assert t._session.headers["PRIVATE-TOKEN"] == "test-token-123"
        finally:
            t.shutdown()
            t.wait(2000)


class TestRunLoopResilience:
    def test_unknown_exception_doesnt_crash(self, qtbot):
        """run() should catch unknown exceptions and continue."""
        thread = GitLabThread()
        thread.fetch_issues("group/proj", "opened")
        thread.fetch_issues("group/proj2", "opened")

        call_count = 0
        original_process = thread._process_list_request

        def mock_process(*args):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("unexpected")
            thread.shutdown()

        thread._process_list_request = mock_process
        thread.start()
        assert thread.wait(5000)
        assert call_count == 2
