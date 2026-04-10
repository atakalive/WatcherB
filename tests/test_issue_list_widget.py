"""Tests for IssueListWidget (Issue #20)."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

import config
from issue_browser.widgets import IssueListWidget


class TestPopulate:
    def test_populate_shows_all_items(self, qtbot):
        w = IssueListWidget()
        qtbot.addWidget(w)
        issues = [
            {"iid": 1, "title": "First", "labels": []},
            {"iid": 2, "title": "Second", "labels": ["bug"]},
        ]
        w.populate(issues)
        assert w._list.count() == 2

    def test_populate_with_labels(self, qtbot):
        w = IssueListWidget()
        qtbot.addWidget(w)
        issues = [{"iid": 1, "title": "Test", "labels": ["bug", "urgent"]}]
        w.populate(issues)
        text = w._list.item(0).text()
        assert "[bug, urgent]" in text

    def test_populate_stores_iid_in_user_role(self, qtbot):
        w = IssueListWidget()
        qtbot.addWidget(w)
        issues = [{"iid": 42, "title": "Test", "labels": []}]
        w.populate(issues)
        iid = w._list.item(0).data(Qt.ItemDataRole.UserRole)
        assert iid == 42

    def test_populate_truncated(self, qtbot):
        w = IssueListWidget()
        qtbot.addWidget(w)
        issues = [{"iid": i, "title": f"Issue {i}", "labels": []} for i in range(5)]
        w.populate(issues, truncated=True)
        assert w._list.count() == 6  # 5 + warning
        warn = w._list.item(5)
        assert "truncated" in warn.text().lower()
        assert str(config.MAX_PAGES * 100) in warn.text()
        assert warn.flags() == Qt.NoItemFlags

    def test_populate_no_truncation(self, qtbot):
        w = IssueListWidget()
        qtbot.addWidget(w)
        issues = [{"iid": 1, "title": "Test", "labels": []}]
        w.populate(issues, truncated=False)
        assert w._list.count() == 1

    def test_populate_empty_list(self, qtbot):
        w = IssueListWidget()
        qtbot.addWidget(w)
        w.populate([])
        assert w._list.count() == 1
        item = w._list.item(0)
        assert "No issues found" in item.text()
        assert item.flags() == Qt.NoItemFlags

    def test_populate_does_not_emit_signals(self, qtbot):
        """populate() should not emit issue_selected during list rebuild."""
        w = IssueListWidget()
        qtbot.addWidget(w)
        emissions = []
        w.issue_selected.connect(lambda iid: emissions.append(iid))
        issues = [{"iid": 1, "title": "Test", "labels": []}]
        w.populate(issues)
        assert emissions == []


class TestShowLoading:
    def test_show_loading(self, qtbot):
        w = IssueListWidget()
        qtbot.addWidget(w)
        w.show_loading()
        assert w._list.count() == 1
        item = w._list.item(0)
        assert "Loading" in item.text()
        assert item.flags() == Qt.NoItemFlags

    def test_show_loading_does_not_emit(self, qtbot):
        w = IssueListWidget()
        qtbot.addWidget(w)
        emissions = []
        w.issue_selected.connect(lambda iid: emissions.append(iid))
        w.show_loading()
        assert emissions == []


class TestShowError:
    def test_show_error(self, qtbot):
        w = IssueListWidget()
        qtbot.addWidget(w)
        w.show_error("Network error")
        assert w._list.count() == 1
        item = w._list.item(0)
        assert "Error: Network error" in item.text()
        assert item.flags() == Qt.NoItemFlags

    def test_show_error_does_not_emit(self, qtbot):
        w = IssueListWidget()
        qtbot.addWidget(w)
        emissions = []
        w.issue_selected.connect(lambda iid: emissions.append(iid))
        w.show_error("fail")
        assert emissions == []


class TestFilterChanged:
    def test_filter_changed_emits_api_value(self, qtbot):
        w = IssueListWidget()
        qtbot.addWidget(w)
        emissions = []
        w.filter_changed.connect(lambda v: emissions.append(v))
        w._filter_combo.setCurrentIndex(1)  # "Closed" -> "closed"
        assert emissions == ["closed"]

    def test_filter_all(self, qtbot):
        w = IssueListWidget()
        qtbot.addWidget(w)
        emissions = []
        w.filter_changed.connect(lambda v: emissions.append(v))
        w._filter_combo.setCurrentIndex(2)  # "All" -> "all"
        assert emissions == ["all"]


class TestReloadRequested:
    def test_reload_signal(self, qtbot):
        w = IssueListWidget()
        qtbot.addWidget(w)
        with qtbot.waitSignal(w.reload_requested, timeout=1000):
            w._reload_btn.click()


class TestIssueSelected:
    def test_item_selection_emits_iid(self, qtbot):
        w = IssueListWidget()
        qtbot.addWidget(w)
        issues = [
            {"iid": 10, "title": "A", "labels": []},
            {"iid": 20, "title": "B", "labels": []},
        ]
        w.populate(issues)
        emissions = []
        w.issue_selected.connect(lambda iid: emissions.append(iid))
        w._list.setCurrentRow(0)
        assert emissions == [10]

    def test_disabled_item_no_emit(self, qtbot):
        w = IssueListWidget()
        qtbot.addWidget(w)
        w.show_loading()
        emissions = []
        w.issue_selected.connect(lambda iid: emissions.append(iid))
        # Try to select the disabled "Loading..." item
        w._list.setCurrentRow(0)
        # disabled items can't be selected, so no emission
        assert emissions == []


class TestCurrentFilter:
    def test_default_filter(self, qtbot):
        w = IssueListWidget()
        qtbot.addWidget(w)
        assert w.current_filter() == "opened"

    def test_after_change(self, qtbot):
        w = IssueListWidget()
        qtbot.addWidget(w)
        w._filter_combo.setCurrentIndex(2)
        assert w.current_filter() == "all"
