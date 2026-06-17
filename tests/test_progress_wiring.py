"""Wiring tests for progress edit buffering and in-place update (Issue #37)."""

from datetime import datetime, timezone

import pytest

import config
from discord_client import DiscordThread
from issue_browser.gitlab_client import GitLabThread
from watcher import MainWindow

_NOW = datetime.now(tz=timezone.utc)


@pytest.fixture
def window(qtbot, monkeypatch):
    monkeypatch.setattr(DiscordThread, "start", lambda self: None)
    monkeypatch.setattr(GitLabThread, "start", lambda self: None)
    monkeypatch.setattr(config, "STATUS_POLL_ENABLED", False)
    w = MainWindow()
    qtbot.addWidget(w)
    return w


_INPROG = "[proj] 🔧 RUN in progress — 3 tool calls"
_FINAL = "[proj] ✅ RUN — 9 tool calls"


def test_edit_buffered_until_history(window):
    # not loaded yet -> edit goes into pending buffer
    window._history_loaded = False
    window._on_message_edited({"message_id": 7, "content": _INPROG, "created_at": _NOW})
    assert "RUN" not in window._message_log.toPlainText()
    assert len(window._pending_edits) == 1

    # history including that id -> buffer reapplied, single row
    window._on_history_loaded(
        [{"content": "[proj] old", "created_at": _NOW, "message_id": 7}]
    )
    txt = window._message_log.toPlainText()
    assert "3 tool calls" in txt
    assert len(window._message_log._records) == 1


def test_reconnect_race_finalized_not_lost(window):
    window._history_loaded = True
    window._on_history_loading()   # simulate reconnect start
    assert window._history_loaded is False
    window._on_message_edited({"message_id": 8, "content": _FINAL, "created_at": _NOW})
    assert len(window._pending_edits) == 1

    window._on_history_loaded(
        [{"content": _INPROG, "created_at": _NOW, "message_id": 8}]
    )
    txt = window._message_log.toPlainText()
    assert "9 tool calls" in txt   # finalized content wins
    assert len(window._message_log._records) == 1


def test_reconnect_no_duplicate(window):
    msgs = [{"content": "[proj] hi", "created_at": _NOW, "message_id": 5}]
    window._on_history_loaded(msgs)
    window._on_history_loaded(msgs)
    assert len(window._message_log._records) == 1


def test_non_progress_edit_ignored(window):
    window._history_loaded = True
    window._on_history_loaded(
        [{"content": "[p] A → B", "created_at": _NOW, "message_id": 3}]
    )
    before = window._message_log.toPlainText()
    window._on_message_edited({"message_id": 3, "content": "[p] A → C", "created_at": _NOW})
    assert window._message_log.toPlainText() == before
