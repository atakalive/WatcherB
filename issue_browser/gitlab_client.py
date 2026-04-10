"""GitLab API client thread with persistent queue and cooperative shutdown."""

import logging
import re
import urllib.parse
from collections import deque

import requests
from PySide6.QtCore import QMutex, QMutexLocker, QThread, QWaitCondition, Signal

import config

_logger = logging.getLogger(__name__)

_LINK_NEXT_RE = re.compile(r'<([^>]+)>;\s*rel="next"')

_REQUEST_TIMEOUT = 4


class _ShutdownInterrupt(Exception):
    """shutdown 検出時に raise。run() で catch して clean return。"""
    pass


class GitLabThread(QThread):
    # Signals
    issues_loaded = Signal(str, str, int, bool, list)      # (project, state_filter, request_id, truncated, issues)
    issue_detail_loaded = Signal(str, int, int, dict)       # (project, iid, request_id, detail_dict)
    list_error = Signal(str, str, int, str)                 # (project, state_filter, request_id, message)
    detail_error = Signal(str, int, int, str)               # (project, iid, request_id, message)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mutex = QMutex()
        self._condition = QWaitCondition()
        self._pending_requests: deque[dict] = deque()
        self._next_request_id = 1
        self._shutdown = False

        self._session = requests.Session()
        self._session.headers["User-Agent"] = "WatcherB"
        if config.GITLAB_TOKEN:
            self._session.headers["PRIVATE-TOKEN"] = config.GITLAB_TOKEN

    def fetch_issues(self, project: str, state: str) -> int:
        """Issue リスト取得をキューに追加。request_id を返す。"""
        with QMutexLocker(self._mutex):
            rid = self._next_request_id
            self._next_request_id += 1
            self._pending_requests.append({
                "type": "list", "project": project, "state": state, "request_id": rid
            })
            self._condition.wakeOne()
        return rid

    def fetch_issue_detail(self, project: str, iid: int) -> int:
        """Issue 詳細取得をキューに追加。request_id を返す。"""
        with QMutexLocker(self._mutex):
            rid = self._next_request_id
            self._next_request_id += 1
            self._pending_requests.append({
                "type": "detail", "project": project, "iid": iid, "request_id": rid
            })
            self._condition.wakeOne()
        return rid

    def shutdown(self):
        """協調的シャットダウン。"""
        with QMutexLocker(self._mutex):
            self._shutdown = True
            self._condition.wakeOne()
        self._session.close()

    def run(self):
        while True:
            self._mutex.lock()
            while not self._pending_requests and not self._shutdown:
                self._condition.wait(self._mutex)
            if self._shutdown:
                self._mutex.unlock()
                return
            request = self._pending_requests.popleft()
            self._mutex.unlock()

            try:
                if request["type"] == "list":
                    self._process_list_request(
                        request["project"], request["state"], request["request_id"]
                    )
                elif request["type"] == "detail":
                    self._process_detail_request(
                        request["project"], request["iid"], request["request_id"]
                    )
            except _ShutdownInterrupt:
                return
            except Exception:
                _logger.exception("Unexpected error processing request")

    def _fetch_all_pages(self, url: str, params: dict) -> tuple[list[dict], bool]:
        """ページネーション付きで全ページ取得。(items, truncated) を返す。"""
        all_items = []
        next_url = url
        current_params = dict(params)
        page_count = 0
        truncated = False

        while next_url is not None:
            if self._shutdown:
                raise _ShutdownInterrupt()

            if page_count >= config.MAX_PAGES:
                next_url = None
                truncated = True
                break

            try:
                resp = self._session.get(next_url, params=current_params, timeout=_REQUEST_TIMEOUT)
                resp.raise_for_status()
            except requests.RequestException:
                if self._shutdown:
                    raise _ShutdownInterrupt()
                raise

            if self._shutdown:
                raise _ShutdownInterrupt()

            all_items.extend(resp.json())
            page_count += 1

            next_url = None
            current_params = {}
            link_header = resp.headers.get("Link", "")
            match = _LINK_NEXT_RE.search(link_header)
            if match:
                next_url = match.group(1)

        return all_items, truncated

    def _process_list_request(self, project: str, state: str, request_id: int):
        encoded = urllib.parse.quote(project, safe="")
        url = f"{config.GITLAB_URL}/api/v4/projects/{encoded}/issues"
        params = {"state": state, "per_page": "100", "order_by": "updated_at"}
        try:
            issues, truncated = self._fetch_all_pages(url, params)
            self.issues_loaded.emit(project, state, request_id, truncated, issues)
        except _ShutdownInterrupt:
            raise
        except Exception as e:
            self.list_error.emit(project, state, request_id, str(e))

    def _process_detail_request(self, project: str, iid: int, request_id: int):
        encoded = urllib.parse.quote(project, safe="")
        try:
            if self._shutdown:
                raise _ShutdownInterrupt()

            detail_url = f"{config.GITLAB_URL}/api/v4/projects/{encoded}/issues/{iid}"
            try:
                resp = self._session.get(detail_url, timeout=_REQUEST_TIMEOUT)
                resp.raise_for_status()
            except requests.RequestException:
                if self._shutdown:
                    raise _ShutdownInterrupt()
                raise

            if self._shutdown:
                raise _ShutdownInterrupt()

            detail = resp.json()

            notes_url = f"{config.GITLAB_URL}/api/v4/projects/{encoded}/issues/{iid}/notes"
            notes_params = {"order_by": "created_at", "sort": "asc", "per_page": "100"}
            notes, notes_truncated = self._fetch_all_pages(notes_url, notes_params)

            detail["_notes"] = [n for n in notes if not n.get("system", False)]
            detail["_notes_truncated"] = notes_truncated

            self.issue_detail_loaded.emit(project, iid, request_id, detail)
        except _ShutdownInterrupt:
            raise
        except Exception as e:
            self.detail_error.emit(project, iid, request_id, str(e))
