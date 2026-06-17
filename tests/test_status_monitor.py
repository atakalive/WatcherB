"""Tests for LLM provider status monitoring (Issue #36)."""

from unittest.mock import MagicMock

import pytest
from PySide6.QtGui import QCloseEvent

import config
from discord_client import DiscordThread
from issue_browser.gitlab_client import GitLabThread
from status_monitor import (
    StatusMonitorThread,
    _gcp_details,
    _normalize_gcp,
    _normalize_statuspage,
    _statuspage_details,
)
from watcher import MainWindow, _build_status_tooltip, _status_page_links


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

    def test_statuspage_details_and_page_propagated(self):
        thread = StatusMonitorThread()
        resp = MagicMock()
        resp.json.return_value = {
            "status": {"indicator": "major", "description": "x"},
            "components": [{"name": "API", "status": "major_outage"}],
        }
        resp.raise_for_status.return_value = None
        thread._session.get = MagicMock(return_value=resp)
        provider = {"key": "github", "name": "GitHub", "type": "statuspage", "url": "http://x"}
        result = thread._fetch_one(provider)
        assert result["details"] == [{"what": "API", "how": "Major Outage"}]
        assert result["page"] == "http://x"


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


def _status(key, name, level, description="", page="", details=None):
    return {
        "key": key, "name": name, "level": level, "description": description,
        "page": page, "details": details if details is not None else [],
    }


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


# ---------------------------------------------------------------------------
# F. _statuspage_details (pure function)
# ---------------------------------------------------------------------------
class TestStatuspageDetails:
    def test_non_operational_components(self):
        data = {"components": [
            {"name": "API", "status": "partial_outage"},
            {"name": "DB", "status": "degraded_performance"},
        ]}
        assert _statuspage_details(data) == [
            {"what": "API", "how": "Partial Outage"},
            {"what": "DB", "how": "Degraded Performance"},
        ]

    def test_operational_and_maintenance_excluded(self):
        data = {"components": [
            {"name": "A", "status": "operational"},
            {"name": "B", "status": "under_maintenance"},
            {"name": "C", "status": "major_outage"},
        ]}
        assert _statuspage_details(data) == [{"what": "C", "how": "Major Outage"}]

    def test_unknown_status_excluded(self):
        data = {"components": [{"name": "A", "status": "frobnicated"}]}
        assert _statuspage_details(data) == []

    def test_group_container_excluded(self):
        data = {"components": [
            {"name": "Parent", "status": "major_outage", "group": True},
            {"name": "Child", "status": "major_outage"},
        ]}
        assert _statuspage_details(data) == [{"what": "Child", "how": "Major Outage"}]

    def test_incident_fallback(self):
        data = {
            "components": [{"name": "A", "status": "operational"}],
            "incidents": [{"name": "Elevated errors", "impact": "major"}],
        }
        assert _statuspage_details(data) == [{"what": "Elevated errors", "how": "Major"}]

    def test_incident_impact_missing_or_unknown(self):
        data = {"incidents": [
            {"name": "X"},
            {"name": "Y", "impact": "weird"},
        ]}
        assert _statuspage_details(data) == [
            {"what": "X", "how": "Incident"},
            {"what": "Y", "how": "Incident"},
        ]

    def test_resolved_incident_excluded(self):
        data = {"incidents": [
            {"name": "Old", "impact": "major", "status": "resolved"},
            {"name": "Old2", "impact": "major", "status": "Postmortem"},
            {"name": "Live", "impact": "minor", "status": "investigating"},
        ]}
        assert _statuspage_details(data) == [{"what": "Live", "how": "Minor"}]

    def test_component_type_guards(self):
        data = {"components": [
            "not-a-dict",
            {"name": 123, "status": "major_outage"},
            {"name": "OK", "status": "major_outage"},
        ]}
        assert _statuspage_details(data) == [{"what": "OK", "how": "Major Outage"}]

    def test_non_dict_and_empty(self):
        assert _statuspage_details("nope") == []
        assert _statuspage_details({}) == []


# ---------------------------------------------------------------------------
# G. _gcp_details (pure function)
# ---------------------------------------------------------------------------
class TestGcpDetails:
    def test_ongoing_matched_incident(self):
        incidents = [{
            "end": None,
            "external_desc": "Gemini is slow",
            "affected_products": [{"title": "Gemini API"}, {"title": "Other"}],
        }]
        assert _gcp_details(incidents, ["Gemini"]) == [
            {"what": "Gemini API", "how": "Gemini is slow"},
        ]

    def test_resolved_incident_excluded(self):
        incidents = [{
            "end": "2026-01-01T00:00:00Z",
            "external_desc": "done",
            "affected_products": [{"title": "Gemini"}],
        }]
        assert _gcp_details(incidents, ["Gemini"]) == []

    def test_non_matching_product(self):
        incidents = [{"end": None, "affected_products": [{"title": "BigQuery"}]}]
        assert _gcp_details(incidents, ["Gemini"]) == []

    def test_type_guards(self):
        assert _gcp_details("nope", ["Gemini"]) == []
        incidents = [{
            "end": None,
            "affected_products": [123, {"title": 5}, {"title": "Gemini"}],
        }]
        assert _gcp_details(incidents, ["Gemini"]) == [{"what": "Gemini", "how": ""}]

    def test_multiple_matching_titles_joined(self):
        incidents = [{
            "end": None,
            "external_desc": "x",
            "affected_products": [{"title": "Gemini API"}, {"title": "Gemini Studio"}],
        }]
        assert _gcp_details(incidents, ["Gemini"]) == [
            {"what": "Gemini API, Gemini Studio", "how": "x"},
        ]

    def test_whitespace_spanning_match_word(self):
        incidents = [{
            "end": None,
            "external_desc": "x",
            "affected_products": [{"title": "Vertex"}, {"title": "AI Platform"}],
        }]
        # joined "vertex ai platform" matches "vertex ai"; no single title contains it,
        # so what falls back to all titles joined.
        assert _gcp_details(incidents, ["Vertex AI"]) == [
            {"what": "Vertex, AI Platform", "how": "x"},
        ]


# ---------------------------------------------------------------------------
# H. _build_status_tooltip / _status_page_links (pure functions)
# ---------------------------------------------------------------------------
class TestBuildStatusTooltip:
    def test_renders_what_how_rows(self):
        down = [_status("a", "Claude", "minor", details=[
            {"what": "API", "how": "Partial Outage"},
        ])]
        tip = _build_status_tooltip(down)
        assert "<b>Claude</b>" in tip
        assert "API: Partial Outage" in tip

    def test_empty_how_renders_what_only(self):
        down = [_status("a", "Claude", "minor", details=[{"what": "API", "how": ""}])]
        tip = _build_status_tooltip(down)
        assert "API" in tip
        assert "API:" not in tip

    def test_description_fallback(self):
        down = [_status("a", "Claude", "minor", description="something broke")]
        tip = _build_status_tooltip(down)
        assert "something broke" in tip

    def test_level_generic_fallback(self):
        minor = _build_status_tooltip([_status("a", "Claude", "minor")])
        major = _build_status_tooltip([_status("b", "OpenAI", "major")])
        assert "Degraded" in minor
        assert "Outage" in major

    def test_long_how_truncated(self):
        down = [_status("a", "Claude", "minor", details=[
            {"what": "API", "how": "y" * 120},
        ])]
        tip = _build_status_tooltip(down)
        assert "y" * 100 + "…" in tip
        assert "y" * 101 not in tip

    def test_long_fallback_description_truncated(self):
        down = [_status("a", "Claude", "major", description="z" * 120)]
        tip = _build_status_tooltip(down)
        assert "z" * 100 + "…" in tip
        assert "z" * 101 not in tip


class TestStatusPageLinks:
    def test_returns_only_providers_with_page(self):
        down = [
            _status("a", "Claude", "minor", page="https://claude.example"),
            _status("b", "OpenAI", "major"),
            _status("c", "GitHub", "minor", page=""),
        ]
        assert _status_page_links(down) == [("Claude", "https://claude.example")]


class TestLlmDownCache:
    def test_populated_on_down_poll(self, window):
        down = [_status("a", "Claude", "minor", "x")]
        window._on_statuses_updated(list(down))
        assert window._llm_down == down

    def test_reset_on_all_ok(self, window):
        window._on_statuses_updated([_status("a", "Claude", "minor", "x")])
        window._on_statuses_updated([_status("a", "Claude", "ok")])
        assert window._llm_down == []

    def test_reset_on_all_unknown(self, window):
        window._on_statuses_updated([_status("a", "Claude", "minor", "x")])
        window._on_statuses_updated([_status("a", "Claude", "unknown")])
        assert window._llm_down == []
