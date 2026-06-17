"""Tests for MessageLog record management + in-place update (Issue #37)."""

from datetime import datetime, timezone

import pytest

import config
from watcher import MessageLog

_NOW = datetime.now(tz=timezone.utc)


@pytest.fixture
def log(qtbot):
    w = MessageLog()
    qtbot.addWidget(w)
    return w


def test_append_registers_record(log):
    log.append_message("hello", _NOW, "info", message_id=10)
    assert 10 in log._records
    assert "hello" in log.toPlainText()


def test_update_message_in_place(log):
    log.append_message("v1", _NOW, "progress", message_id=10)
    before = len(log._records)
    log.update_message(10, "v2", "progress")
    assert len(log._records) == before   # no new row
    txt = log.toPlainText()
    assert "v2" in txt
    assert "v1" not in txt


def test_update_keeps_created_at(log):
    log.append_message("v1", _NOW, "progress", message_id=10)
    other = datetime(2000, 1, 1, tzinfo=timezone.utc)
    log.update_message(10, "v2", "progress", created_at=other)
    assert log._records[10]["created_at"] == _NOW


def test_update_unknown_id_appends(log):
    log.append_message("a", _NOW, "info", message_id=1)
    before = len(log._records)
    log.update_message(999, "new", "progress", created_at=_NOW)
    assert len(log._records) == before + 1
    assert "new" in log.toPlainText()


def test_keyless_append_displayed_and_registered(log):
    log.append_message("noid", _NOW, "info", message_id=None)
    assert "noid" in log.toPlainText()
    # registered under a negative synthetic key
    assert any(k < 0 for k in log._records)


def test_eviction_no_duplicate_with_small_cap(log, monkeypatch):
    monkeypatch.setattr(config, "LOG_RECORD_LIMIT", 5)
    monkeypatch.setattr(config, "HISTORY_LIMIT", 5)
    log.append_message("p1", _NOW, "progress", message_id=100)
    log.append_message("n1", _NOW, "info", message_id=101)
    log.append_message("n2", _NOW, "info", message_id=102)
    log.update_message(100, "p2", "progress")
    txt = log.toPlainText()
    assert "p2" in txt
    assert "p1" not in txt
    assert len(log._records) == 3


def test_eviction_caps_records(log, monkeypatch):
    monkeypatch.setattr(config, "LOG_RECORD_LIMIT", 5)
    monkeypatch.setattr(config, "HISTORY_LIMIT", 20)  # effective cap = 20
    for i in range(25):
        log.append_message(f"m{i}", _NOW, "info", message_id=i)
    assert len(log._records) == 20


def test_progress_survives_history_limit_burst(log, monkeypatch):
    # default LOG_RECORD_LIMIT (200) > HISTORY_LIMIT: progress survives a HISTORY_LIMIT burst
    monkeypatch.setattr(config, "LOG_RECORD_LIMIT", 200)
    monkeypatch.setattr(config, "HISTORY_LIMIT", 20)
    log.append_message("prog", _NOW, "progress", message_id=500)
    for i in range(25):  # more than HISTORY_LIMIT new messages
        log.append_message(f"m{i}", _NOW, "info", message_id=i)
    log.update_message(500, "prog2", "progress")
    txt = log.toPlainText()
    assert "prog2" in txt
    assert "prog" not in txt.replace("prog2", "")  # original gone, only updated present


def test_reset_log(log):
    log.append_message("a", _NOW, "info", message_id=1)
    log.reset_log()
    assert len(log._records) == 0
    assert log.toPlainText().strip() == ""


def test_created_at_none_no_crash(log):
    log.append_message("noat", None, "info", message_id=1)
    assert "noat" in log.toPlainText()


def test_append_history_bulk(log, monkeypatch):
    monkeypatch.setattr(config, "LOG_RECORD_LIMIT", 200)
    monkeypatch.setattr(config, "HISTORY_LIMIT", 20)
    records = [(f"h{i}", _NOW, "info", i) for i in range(10)]
    log.append_history(records)
    assert len(log._records) == 10
    assert "h9" in log.toPlainText()


def test_reload_invariant_history_above_log_cap(log, monkeypatch):
    # Simulate config.reload() raising HISTORY_LIMIT above LOG_RECORD_LIMIT.
    monkeypatch.setattr(config, "HISTORY_LIMIT", 300)
    monkeypatch.setattr(config, "LOG_RECORD_LIMIT", 200)
    records = [(f"h{i}", _NOW, "info", i) for i in range(300)]
    log.append_history(records)
    assert len(log._records) == 300   # effective cap = max(300, 200) = 300; nothing evicted


def test_reload_invariant_small_log_cap(log, monkeypatch):
    monkeypatch.setattr(config, "HISTORY_LIMIT", 20)
    monkeypatch.setattr(config, "LOG_RECORD_LIMIT", 5)
    for i in range(25):
        log.append_message(f"m{i}", _NOW, "info", message_id=i)
    assert len(log._records) == 20   # effective cap = max(20, 5) = 20
