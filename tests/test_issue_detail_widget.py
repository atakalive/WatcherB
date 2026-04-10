"""Tests for IssueDetailWidget (Issue #21)."""

import pytest

from issue_browser.widgets import IssueDetailWidget


@pytest.fixture
def widget(qtbot):
    w = IssueDetailWidget()
    qtbot.addWidget(w)
    return w


def _make_detail(**overrides):
    base = {
        "iid": 1,
        "title": "Test",
        "state": "opened",
        "labels": [],
        "description": "",
        "_notes": [],
        "_notes_truncated": False,
    }
    base.update(overrides)
    return base


class TestShowDetail:
    def test_show_detail_renders_title(self, widget):
        widget.show_detail(_make_detail(iid=42, title="Fix bug", description="body text"))
        text = widget.toPlainText()
        assert "#42" in text
        assert "Fix bug" in text

    def test_show_detail_renders_comments(self, widget):
        notes = [
            {"author": {"name": "Alice"}, "created_at": "2024-01-01T00:00:00Z", "body": "First comment"},
            {"author": {"name": "Bob"}, "created_at": "2024-01-02T00:00:00Z", "body": "Second comment"},
        ]
        widget.show_detail(_make_detail(_notes=notes))
        text = widget.toPlainText()
        assert "Alice" in text
        assert "First comment" in text
        assert "Bob" in text
        assert "Second comment" in text

    def test_notes_truncated_warning(self, widget):
        notes = [
            {"author": {"name": f"User{i}"}, "created_at": "2024-01-01", "body": f"note {i}"}
            for i in range(3)
        ]
        widget.show_detail(_make_detail(_notes=notes, _notes_truncated=True))
        text = widget.toPlainText()
        assert "Showing first 3 comments" in text

    def test_notes_not_truncated_no_warning(self, widget):
        widget.show_detail(_make_detail(_notes=[], _notes_truncated=False))
        text = widget.toPlainText()
        assert "Showing first" not in text


class TestStates:
    def test_show_blank(self, widget):
        widget.show_blank()
        assert widget.toPlainText() == ""

    def test_show_error(self, widget):
        widget.show_error("timeout")
        text = widget.toPlainText()
        assert "Error: timeout" in text

    def test_show_loading(self, widget):
        widget.show_loading()
        text = widget.toPlainText()
        assert "Loading..." in text


class TestXSS:
    def test_xss_in_title(self, widget):
        widget.show_detail(_make_detail(title="<script>alert(1)</script>"))
        assert "<script>alert(1)</script>" in widget.toPlainText()
        assert "<script" not in widget.toHtml().lower().replace("&lt;script", "")

    def test_xss_in_description(self, widget):
        widget.show_detail(_make_detail(description="<img onerror=alert(1)>"))
        assert "<img onerror=alert(1)>" in widget.toPlainText()
        html_out = widget.toHtml()
        assert "<img" not in html_out.lower().replace("&lt;img", "")

    def test_xss_in_labels(self, widget):
        widget.show_detail(_make_detail(labels=["<script>alert(1)</script>"]))
        assert "<script>alert(1)</script>" in widget.toPlainText()
        assert "<script" not in widget.toHtml().lower().replace("&lt;script", "")


class TestEdgeCases:
    def test_author_none_handling(self, widget):
        notes = [
            {"author": None, "created_at": "2024-01-01T00:00:00Z", "body": "orphan note"},
        ]
        widget.show_detail(_make_detail(_notes=notes))
        text = widget.toPlainText()
        assert "unknown" in text
        assert "orphan note" in text
