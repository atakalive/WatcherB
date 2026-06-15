"""Tests for LLM provider status monitoring (Issue #36)."""

from unittest.mock import MagicMock

import pytest
from PySide6.QtGui import QCloseEvent

import config
from discord_client import DiscordThread
from issue_browser.gitlab_client import GitLabThread
from status_monitor import (
    StatusMonitorThread,
    _normalize_gcp,
    _normalize_statuspage,
)
from watcher import MainWindow


# ---------------------------------------------------------------------------
# A. _normalize_statuspage (pure function)
# ---------------------------------------------------------------------------
class TestNormalizeStatuspage:
    def test_none_is_ok_with_description(self):
        level, desc = _normalize_statuspage(
            {"status": {"indicator": "none", "description": "All Systems Operational"}}
        )
        assert level == "ok"
        assert desc == "All Systems Operational"

    def test_maintenance_is_ok(self):
        level, _ = _normalize_statuspage(
            {"status": {"indicator": "maintenance", "description": "Scheduled maintenance"}}
        )
        assert level == "ok"

    def test_minor(self):
        level, desc = _normalize_statuspage(
            {"status": {"indicator": "minor", "description": "Minor outage"}}
        )
        assert level == "minor"
        assert desc == "Minor outage"

    def test_major(self):
        level, _ = _normalize_statuspage({"status": {"indicator": "major", "description": "x"}})
        assert level == "major"

    def test_critical_folds_to_major(self):
        level, _ = _normalize_statuspage({"status": {"indicator": "critical", "description": "x"}})
        assert level == "major"

    def test_missing_indicator_is_unknown(self):
        level, _ = _normalize_statuspage({"status": {"description": "x"}})
        assert level == "unknown"

    def test_unknown_indicator_value_is_unknown(self):
        level, _ = _normalize_statuspage({"status": {"indicator": "weird"}})
        assert level == "unknown"

    def test_missing_status_key_is_unknown(self):
        assert _normalize_statuspage({"foo": "bar"}) == ("unknown", "")

    def test_non_dict_is_unknown(self):
        assert _normalize_statuspage(["not", "a", "dict"]) == ("unknown", "")

    def test_missing_description_is_empty_string(self):
        _, desc = _normalize_statuspage({"status": {"indicator": "none"}})
        assert desc == ""


# ---------------------------------------------------------------------------
# B. _normalize_gcp (pure function)
# ---------------------------------------------------------------------------
MATCH = ["Gemini", "Vertex"]


class TestNormalizeGcp:
    def test_ongoing_high_gemini_is_major(self):
        incidents = [
            {
                "severity": "high",
                "external_desc": "Gemini is down",
                "affected_products": [{"title": "Gemini API"}],
            }
        ]
        assert _normalize_gcp(incidents, MATCH) == ("major", "Gemini is down")

    def test_ongoing_medium_vertex_is_minor(self):
        incidents = [
            {
                "end": None,
                "severity": "medium",
                "external_desc": "Vertex degraded",
                "affected_products": [{"title": "Vertex AI"}],
            }
        ]
        assert _normalize_gcp(incidents, MATCH) == ("minor", "Vertex degraded")

    def test_empty_string_end_is_ongoing(self):
        incidents = [
            {
                "end": "",
                "severity": "medium",
                "external_desc": "ongoing",
                "affected_products": [{"title": "Gemini"}],
            }
        ]
        level, desc = _normalize_gcp(incidents, MATCH)
        assert level == "minor"
        assert desc == "ongoing"

    def test_resolved_incident_ignored(self):
        incidents = [
            {
                "end": "2026-06-15T00:00:00Z",
                "severity": "high",
                "external_desc": "resolved",
                "affected_products": [{"title": "Gemini"}],
            }
        ]
        assert _normalize_gcp(incidents, MATCH) == ("ok", "")

    def test_non_matching_product_is_ok(self):
        incidents = [
            {
                "severity": "high",
                "external_desc": "other",
                "affected_products": [{"title": "Compute Engine"}],
            }
        ]
        assert _normalize_gcp(incidents, MATCH) == ("ok", "")

    def test_multiple_matches_picks_highest_severity(self):
        incidents = [
            {
                "severity": "medium",
                "external_desc": "minor one",
                "affected_products": [{"title": "Gemini"}],
            },
            {
                "severity": "high",
                "external_desc": "high one",
                "affected_products": [{"title": "Vertex"}],
            },
        ]
        assert _normalize_gcp(incidents, MATCH) == ("major", "high one")

    def test_case_insensitive_match(self):
        incidents = [
            {
                "severity": "medium",
                "external_desc": "x",
                "affected_products": [{"title": "gemini api"}],
            }
        ]
        level, _ = _normalize_gcp(incidents, MATCH)
        assert level == "minor"

    def test_non_list_is_unknown(self):
        assert _normalize_gcp({"not": "list"}, MATCH) == ("unknown", "")

    def test_missing_affected_products(self):
        incidents = [{"severity": "high", "external_desc": "x"}]
        assert _normalize_gcp(incidents, MATCH) == ("ok", "")

    def test_non_dict_product_skipped(self):
        incidents = [
            {
                "severity": "high",
                "external_desc": "x",
                "affected_products": ["not a dict", {"title": "Gemini"}],
            }
        ]
        level, _ = _normalize_gcp(incidents, MATCH)
        assert level == "major"

    def test_non_string_title_skipped_no_typeerror(self):
        incidents = [
            {
                "severity": "high",
                "external_desc": "found via str title",
                "affected_products": [
                    {"title": 123},
                    {"title": None},
                    {"title": "Gemini API"},
                ],
            }
        ]
        # Must not raise TypeError; still matches via the str title product.
        assert _normalize_gcp(incidents, MATCH) == ("major", "found via str title")


# ---------------------------------------------------------------------------
# C. _fetch_one (mock requests.Session.get)
# ---------------------------------------------------------------------------
class TestFetchOne:
    def test_get_raises_returns_unknown(self):
        thread = StatusMonitorThread()
        thread._session.get = MagicMock(side_effect=RuntimeError("boom"))
        provider = {"key": "anthropic", "name": "Claude", "type": "statuspage", "url": "http://x"}
        result = thread._fetch_one(provider)
        assert result["level"] == "unknown"
        assert result["key"] == "anthropic"
        assert result["name"] == "Claude"

    def test_raise_for_status_returns_unknown(self):
        thread = StatusMonitorThread()
        resp = MagicMock()
        resp.raise_for_status.side_effect = RuntimeError("http 500")
        thread._session.get = MagicMock(return_value=resp)
        provider = {"key": "openai", "name": "OpenAI", "type": "statuspage", "url": "http://x"}
        result = thread._fetch_one(provider)
        assert result["level"] == "unknown"
        assert result["name"] == "OpenAI"

    def test_missing_name_falls_back_to_key(self):
        thread = StatusMonitorThread()
        thread._session.get = MagicMock(side_effect=RuntimeError("boom"))
        provider = {"key": "moonshot", "type": "statuspage", "url": "http://x"}
        result = thread._fetch_one(provider)
        assert result["name"] == "moonshot"
        assert result["level"] == "unknown"

    def test_statuspage_success_wired(self):
        thread = StatusMonitorThread()
        resp = MagicMock()
        resp.json.return_value = {"status": {"indicator": "major", "description": "down"}}
        resp.raise_for_status.return_value = None
        thread._session.get = MagicMock(return_value=resp)
        provider = {"key": "github", "name": "GitHub", "type": "statuspage", "url": "http://x"}
        result = thread._fetch_one(provider)
        assert result["level"] == "major"
        assert result["description"] == "down"


# ---------------------------------------------------------------------------
# D & E1. MainWindow slot + closeEvent wiring
# ---------------------------------------------------------------------------
@pytest.fixture
def window(qtbot, monkeypatch):
    monkeypatch.setattr(DiscordThread, "start", lambda self: None)
    monkeypatch.setattr(GitLabThread, "start", lambda self: None)
    monkeypatch.setattr(config, "STATUS_POLL_ENABLED", False)
    w = MainWindow()
    qtbot.addWidget(w)
    yield w


def _status(key, name, level, description=""):
    return {"key": key, "name": name, "level": level, "description": description}


class TestOnStatusesUpdated:
    def test_all_ok_hidden(self, window):
        window._on_statuses_updated(
            [_status("a", "Claude", "ok"), _status("b", "OpenAI", "ok")]
        )
        assert window._llm_status_label.isHidden() is True

    def test_minor_visible_yellow(self, window):
        window._on_statuses_updated(
            [_status("a", "Claude", "minor", "x"), _status("b", "OpenAI", "ok")]
        )
        assert window._llm_status_label.isHidden() is False
        assert "Claude" in window._llm_status_label.text()
        assert config.COLORS["yellow"] in window._llm_status_label.styleSheet()

    def test_major_visible_red(self, window):
        window._on_statuses_updated(
            [_status("a", "Gemini", "major", "x"), _status("b", "OpenAI", "ok")]
        )
        assert config.COLORS["red"] in window._llm_status_label.styleSheet()
        assert "Gemini" in window._llm_status_label.text()

    def test_tooltip_only_down_providers(self, window):
        window._on_statuses_updated(
            [
                _status("a", "Claude", "minor", "claude desc"),
                _status("b", "OpenAI", "ok", "openai desc"),
                _status("c", "GitHub", "unknown", "github desc"),
            ]
        )
        tip = window._llm_status_label.toolTip()
        assert "Claude" in tip
        assert "OpenAI" not in tip
        assert "GitHub" not in tip

    def test_tooltip_truncates_long_description(self, window):
        long_desc = "x" * 120
        window._on_statuses_updated([_status("a", "Claude", "major", long_desc)])
        tip = window._llm_status_label.toolTip()
        assert "x" * 100 + "…" in tip
        assert "x" * 101 not in tip

    def test_consecutive_all_unknown_streak(self, window):
        unknowns = [_status("a", "Claude", "unknown"), _status("b", "OpenAI", "unknown")]
        for _ in range(config.STATUS_POLL_UNKNOWN_STREAK_ALERT - 1):
            window._on_statuses_updated(list(unknowns))
            assert window._llm_status_label.isHidden() is True
        window._on_statuses_updated(list(unknowns))
        assert window._llm_status_label.isHidden() is False
        assert "status check unavailable" in window._llm_status_label.text()
        assert config.COLORS["subtext"] in window._llm_status_label.styleSheet()

    def test_minor_resets_unknown_streak(self, window):
        unknowns = [_status("a", "Claude", "unknown"), _status("b", "OpenAI", "unknown")]
        for _ in range(config.STATUS_POLL_UNKNOWN_STREAK_ALERT):
            window._on_statuses_updated(list(unknowns))
        assert window._llm_status_label.isHidden() is False
        # A minor incident resets the streak.
        window._on_statuses_updated([_status("a", "Claude", "minor", "x")])
        # One more all-unknown poll must not re-trigger the unavailable banner.
        window._on_statuses_updated(list(unknowns))
        assert window._llm_status_label.isHidden() is True


class TestCloseEventWiring:
    def test_timeout_triggers_terminate(self, window):
        fake = MagicMock()
        fake.wait.return_value = False  # timeout
        window._status_thread = fake
        window._force_quit = True
        window.closeEvent(QCloseEvent())
        fake.shutdown.assert_called_once()
        fake.terminate.assert_called_once()
        # wait called twice: wait(5000) then wait(2000)
        assert fake.wait.call_count == 2

    def test_clean_stop_no_terminate(self, window):
        fake = MagicMock()
        fake.wait.return_value = True  # stops cleanly
        window._status_thread = fake
        window._force_quit = True
        window.closeEvent(QCloseEvent())
        fake.shutdown.assert_called_once()
        fake.terminate.assert_not_called()

    def test_none_thread_no_crash(self, window):
        window._status_thread = None
        window._force_quit = True
        window.closeEvent(QCloseEvent())  # must not raise


# ---------------------------------------------------------------------------
# E2. run() provider-loop shutdown / emit suppression
# ---------------------------------------------------------------------------
class TestRunShutdown:
    def test_no_emit_when_shutdown_after_fetch(self, monkeypatch):
        thread = StatusMonitorThread()
        emitted = []
        thread.statuses_updated.connect(lambda s: emitted.append(s))
        thread._fetch_one = lambda provider: {
            "key": provider.get("key", "?"), "name": "x", "level": "ok", "description": ""
        }
        # _is_shutdown: False during provider loop, True at the post-fetch check.
        calls = {"n": 0}
        n_providers = len(config.STATUS_PROVIDERS)

        def fake_is_shutdown():
            calls["n"] += 1
            # First call (loop top) + one per-provider check = 1 + n_providers Falses,
            # then True at the post-loop emit guard.
            return calls["n"] > 1 + n_providers

        thread._is_shutdown = fake_is_shutdown
        thread.run()
        assert emitted == []

    def test_remaining_providers_not_fetched(self, monkeypatch):
        thread = StatusMonitorThread()
        fetched = []

        def fake_fetch(provider):
            fetched.append(provider["key"])
            return {"key": provider["key"], "name": "x", "level": "ok", "description": ""}

        thread._fetch_one = fake_fetch
        # Shutdown becomes True after the first provider is fetched.
        seen = {"n": 0}

        def fake_is_shutdown():
            seen["n"] += 1
            # loop-top False, first per-provider False, then True afterwards.
            return seen["n"] > 2

        thread._is_shutdown = fake_is_shutdown
        thread.run()
        assert len(fetched) == 1


# ---------------------------------------------------------------------------
# E3. _track_provider_unknown WARNING
# ---------------------------------------------------------------------------
class TestTrackProviderUnknown:
    def test_warning_once_at_threshold(self, caplog):
        thread = StatusMonitorThread()
        result = {"key": "anthropic", "name": "Claude", "level": "unknown", "description": ""}
        with caplog.at_level("WARNING"):
            for _ in range(config.STATUS_POLL_PROVIDER_UNKNOWN_WARN):
                thread._track_provider_unknown(result)
            warnings = [r for r in caplog.records if r.levelname == "WARNING"]
            assert len(warnings) == 1
            # Further calls do not emit again.
            thread._track_provider_unknown(result)
            thread._track_provider_unknown(result)
            warnings = [r for r in caplog.records if r.levelname == "WARNING"]
            assert len(warnings) == 1

    def test_ok_resets_streak(self, caplog):
        thread = StatusMonitorThread()
        unknown = {"key": "anthropic", "name": "Claude", "level": "unknown", "description": ""}
        ok = {"key": "anthropic", "name": "Claude", "level": "ok", "description": ""}
        with caplog.at_level("WARNING"):
            for _ in range(config.STATUS_POLL_PROVIDER_UNKNOWN_WARN - 1):
                thread._track_provider_unknown(unknown)
            thread._track_provider_unknown(ok)  # reset
            for _ in range(config.STATUS_POLL_PROVIDER_UNKNOWN_WARN - 1):
                thread._track_provider_unknown(unknown)
            warnings = [r for r in caplog.records if r.levelname == "WARNING"]
            assert len(warnings) == 0


class TestSleepInterruptible:
    """_sleep_interruptible は停止契約の中核ヘルパ（dijkstra code R1 P2-2）。"""

    def test_returns_true_immediately_when_shutdown(self, monkeypatch):
        thread = StatusMonitorThread()
        monkeypatch.setattr(thread, "_is_shutdown", lambda: True)
        sleep_calls: list[float] = []
        monkeypatch.setattr("status_monitor.time.sleep", lambda s: sleep_calls.append(s))
        # shutdown 中はループ先頭で即 True、一度も sleep しない
        assert thread._sleep_interruptible(10.0) is True
        assert sleep_calls == []

    def test_total_sleep_matches_seconds(self, monkeypatch):
        thread = StatusMonitorThread()
        monkeypatch.setattr(thread, "_is_shutdown", lambda: False)
        sleep_calls: list[float] = []
        monkeypatch.setattr("status_monitor.time.sleep", lambda s: sleep_calls.append(s))
        # shutdown でなければ累計 sleep は seconds 相当、各チャンクは step(0.2) 以下
        assert thread._sleep_interruptible(1.0) is False
        assert sum(sleep_calls) == pytest.approx(1.0)
        assert all(s <= 0.2 + 1e-9 for s in sleep_calls)

    def test_stops_midway_when_shutdown_set(self, monkeypatch):
        thread = StatusMonitorThread()
        checks = {"n": 0}

        def fake_is_shutdown():
            checks["n"] += 1
            return checks["n"] > 3  # 4 回目のチェックで True

        monkeypatch.setattr(thread, "_is_shutdown", fake_is_shutdown)
        sleep_calls: list[float] = []
        monkeypatch.setattr("status_monitor.time.sleep", lambda s: sleep_calls.append(s))
        # 途中で shutdown が立つと True を返し、それ以降は sleep しない
        assert thread._sleep_interruptible(100.0) is True
        assert len(sleep_calls) == 3
