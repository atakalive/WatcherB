"""Tests for the "progress" message type (Issue #37)."""

from datetime import datetime, timezone

from message_parser import classify, extract_project, parse_message

_NOW = datetime.now(tz=timezone.utc)


# In-progress format (single and Queue-prefixed)
_INPROGRESS = "[myproj] 🔧 DESIGN_PLAN in progress — 7 tool calls · avg 3.5/min · now 5.0/min · ⏱ 2m10s"
_INPROGRESS_QUEUE = "[Queue][myproj] 🔧 DESIGN_PLAN in progress — 7 tool calls · avg 3.5/min · now 5.0/min · ⏱ 2m10s"
# Finalized format
_FINALIZED = "[myproj] ✅ DESIGN_PLAN — 12 tool calls"
_FINALIZED_QUEUE = "[Queue][myproj] ✅ DESIGN_PLAN — 12 tool calls"


class TestClassifyProgress:
    def test_inprogress_is_progress(self):
        assert classify(_INPROGRESS) == "progress"

    def test_finalized_is_progress(self):
        assert classify(_FINALIZED) == "progress"

    def test_queue_prefix_inprogress(self):
        assert classify(_INPROGRESS_QUEUE) == "progress"
        assert extract_project(_INPROGRESS_QUEUE) == "myproj"

    def test_queue_prefix_finalized(self):
        assert classify(_FINALIZED_QUEUE) == "progress"
        assert extract_project(_FINALIZED_QUEUE) == "myproj"

    def test_project_extracted(self):
        assert extract_project(_INPROGRESS) == "myproj"

    def test_transition_with_tool_calls_is_transition(self):
        # A real transition that happens to contain "tool calls" must NOT become progress.
        content = "[proj] CODE_REVISE → CODE_REVIEW (5 tool calls)"
        assert classify(content) == "transition"

    def test_normal_transition_not_progress(self):
        assert classify("[PJ] A → B") == "transition"

    def test_blocked_not_progress(self):
        assert classify("[PJ] A → BLOCKED") == "blocked"

    def test_done_not_progress(self):
        assert classify("[PJ] A → DONE") == "done"

    def test_info_not_progress(self):
        assert classify("just some info") == "info"


class TestParseProgress:
    def test_inprogress_fields(self):
        p = parse_message(_INPROGRESS, _NOW)
        assert p.msg_type == "progress"
        assert p.project == "myproj"
        assert p.extra["tool_calls"] == 7
        assert isinstance(p.extra["tool_calls"], int)
        assert p.extra["avg"] == 3.5
        assert isinstance(p.extra["avg"], float)
        assert p.extra["now"] == 5.0
        assert isinstance(p.extra["now"], float)
        assert p.extra["elapsed"] == "2m10s"
        assert isinstance(p.extra["elapsed"], str)
        assert p.extra["finalized"] is False

    def test_finalized_fields(self):
        p = parse_message(_FINALIZED, _NOW)
        assert p.msg_type == "progress"
        assert p.extra["tool_calls"] == 12
        assert p.extra["finalized"] is True
        # avg/now/elapsed absent in finalized form
        assert "avg" not in p.extra
        assert "now" not in p.extra
        assert "elapsed" not in p.extra

    def test_finalized_with_in_progress_in_project(self):
        # (1) project literally named "in progress"
        assert parse_message("[in progress] ✅ X — 5 tool calls", _NOW).extra["finalized"] is True
        # (2) project containing "in progress —" (separator dash included)
        assert parse_message(
            "[in progress — weird proj] ✅ X — 5 tool calls", _NOW
        ).extra["finalized"] is True
        # (3) genuine in-progress line -> False
        assert parse_message(
            "[proj] 🔧 RUN in progress — 3 tool calls", _NOW
        ).extra["finalized"] is False

    def test_malformed_numbers_do_not_crash(self):
        content = "[proj] 🔧 RUN in progress — 4 tool calls · avg ./min · now ./min · ⏱ 1s"
        p = parse_message(content, _NOW)
        assert p.extra["tool_calls"] == 4
        assert "avg" not in p.extra
        assert "now" not in p.extra

    def test_vs16_elapsed(self):
        # ⏱ with VS16 (U+23F1 U+FE0F); built with escapes, no raw VS16 in source.
        content = "[proj] 🔧 RUN in progress — 2 tool calls · \u23f1\ufe0f 2m10s"
        p = parse_message(content, _NOW)
        assert p.extra["elapsed"] == "2m10s"
