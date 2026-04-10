"""Tests for ProjectCard and ProjectPanel (Issue #15)."""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from PySide6.QtCore import Qt

import config
from widgets import ProjectCard, ProjectPanel


class TestProjectCardInit:
    def test_initial_state_is_none(self, qtbot):
        card = ProjectCard(display_name="foo")
        qtbot.addWidget(card)
        assert card.state is None

    def test_display_name(self, qtbot):
        card = ProjectCard(display_name="myproject")
        qtbot.addWidget(card)
        assert card.display_name == "myproject"

    def test_project_path_default_none(self, qtbot):
        card = ProjectCard(display_name="foo")
        qtbot.addWidget(card)
        assert card.project_path is None

    def test_project_path_set(self, qtbot):
        card = ProjectCard(display_name="foo", project_path="group/foo")
        qtbot.addWidget(card)
        assert card.project_path == "group/foo"

    def test_initial_state_label_shows_dash(self, qtbot):
        card = ProjectCard(display_name="foo")
        qtbot.addWidget(card)
        assert card._state_label.text() == "─"

    def test_progress_bar_initial_zero(self, qtbot):
        card = ProjectCard(display_name="foo")
        qtbot.addWidget(card)
        assert card._progress_bar.value() == 0

    def test_cursor_set_when_project_path(self, qtbot):
        card = ProjectCard(display_name="foo", project_path="group/foo")
        qtbot.addWidget(card)
        assert card.cursor().shape() == Qt.PointingHandCursor

    def test_no_cursor_when_no_project_path(self, qtbot):
        card = ProjectCard(display_name="foo")
        qtbot.addWidget(card)
        assert card.cursor().shape() != Qt.PointingHandCursor


class TestProjectCardClick:
    def test_click_emits_project_path(self, qtbot):
        card = ProjectCard(display_name="foo", project_path="group/foo")
        qtbot.addWidget(card)
        with qtbot.waitSignal(card.clicked, timeout=1000) as blocker:
            qtbot.mouseClick(card, Qt.LeftButton)
        assert blocker.args == ["group/foo"]

    def test_click_no_emit_when_no_path(self, qtbot):
        card = ProjectCard(display_name="foo", project_path=None)
        qtbot.addWidget(card)
        with qtbot.assertNotEmitted(card.clicked):
            qtbot.mouseClick(card, Qt.LeftButton)


class TestProjectCardUpdateState:
    def test_state_transition_from_none(self, qtbot):
        card = ProjectCard(display_name="foo")
        qtbot.addWidget(card)
        ts = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
        card.update_state("INITIALIZE", ts)
        assert card.state == "INITIALIZE"
        assert card._state_label.text() == "INITIALIZE"

    def test_update_state_sets_progress(self, qtbot):
        card = ProjectCard(display_name="foo")
        qtbot.addWidget(card)
        ts = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
        card.update_state("IMPLEMENTATION", ts)
        assert card._progress_bar.value() == config.STATE_PROGRESS["IMPLEMENTATION"]


class TestProjectCardSelection:
    def test_set_selected(self, qtbot):
        card = ProjectCard(display_name="foo", project_path="group/foo")
        qtbot.addWidget(card)
        card.set_selected(True)
        assert card._selected is True
        style = card.styleSheet()
        assert "border-left" in style

    def test_set_deselected(self, qtbot):
        card = ProjectCard(display_name="foo", project_path="group/foo")
        qtbot.addWidget(card)
        card.set_selected(True)
        card.set_selected(False)
        assert card._selected is False
        style = card.styleSheet()
        assert "border-left" not in style


class TestProjectCardUpdateIssues:
    def test_issue_link_uses_project_path(self, qtbot):
        """Issue URL should use project_path, not display_name."""
        card = ProjectCard(display_name="foo", project_path="group/foo")
        qtbot.addWidget(card)
        ts = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
        card.update_state("IMPLEMENTATION", ts)
        card.update_issues([42])
        label_text = card._issue_label.text()
        assert "group/foo/-/issues/42" in label_text
        assert '"/foo/-/issues/42"' not in label_text

    def test_issue_link_fallback_display_name(self, qtbot):
        """Dynamic card (no project_path) should use display_name for URL."""
        card = ProjectCard(display_name="dynproj", project_path=None)
        qtbot.addWidget(card)
        ts = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
        card.update_state("IMPLEMENTATION", ts)
        card.update_issues([7])
        label_text = card._issue_label.text()
        assert "dynproj/-/issues/7" in label_text


class TestProjectPanelPrepopulate:
    def test_prepopulate_creates_cards(self, qtbot, monkeypatch):
        monkeypatch.setattr(config, "GITLAB_PROJECTS", ["group/a", "group/b", "group/c"])
        panel = ProjectPanel()
        qtbot.addWidget(panel)
        assert len(panel._path_cards) == 3
        assert "group/a" in panel._path_cards
        assert "group/b" in panel._path_cards
        assert "group/c" in panel._path_cards

    def test_prepopulate_cards_state_is_none(self, qtbot, monkeypatch):
        monkeypatch.setattr(config, "GITLAB_PROJECTS", ["group/a"])
        panel = ProjectPanel()
        qtbot.addWidget(panel)
        card = panel._path_cards["group/a"]
        assert card.state is None
        assert card._state_label.text() == "─"

    def test_prepopulate_name_resolution(self, qtbot, monkeypatch):
        monkeypatch.setattr(config, "GITLAB_PROJECTS", ["group/a", "group/b"])
        panel = ProjectPanel()
        qtbot.addWidget(panel)
        assert panel._name_to_path["a"] == "group/a"
        assert panel._name_to_path["b"] == "group/b"

    def test_prepopulate_collision_uses_full_path(self, qtbot, monkeypatch):
        monkeypatch.setattr(config, "GITLAB_PROJECTS", ["group1/foo", "group2/foo"])
        panel = ProjectPanel()
        qtbot.addWidget(panel)
        assert "foo" in panel._collided_names
        assert "foo" not in panel._name_to_path
        # Both cards should use full path as display name
        assert panel._path_cards["group1/foo"].display_name == "group1/foo"
        assert panel._path_cards["group2/foo"].display_name == "group2/foo"


class TestProjectPanelUpdateProject:
    def test_update_known_project(self, qtbot, monkeypatch):
        monkeypatch.setattr(config, "GITLAB_PROJECTS", ["group/myproj"])
        panel = ProjectPanel()
        qtbot.addWidget(panel)
        ts = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
        panel.update_project("myproj", "INITIALIZE", ts)
        card = panel._path_cards["group/myproj"]
        assert card.state == "INITIALIZE"

    def test_update_unknown_creates_dynamic_card(self, qtbot, monkeypatch):
        monkeypatch.setattr(config, "GITLAB_PROJECTS", [])
        panel = ProjectPanel()
        qtbot.addWidget(panel)
        ts = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
        panel.update_project("unknown", "IDLE", ts)
        assert "unknown" in panel._dynamic_cards
        assert panel._dynamic_cards["unknown"].project_path is None

    def test_dynamic_card_no_path(self, qtbot, monkeypatch):
        monkeypatch.setattr(config, "GITLAB_PROJECTS", [])
        panel = ProjectPanel()
        qtbot.addWidget(panel)
        ts = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
        panel.update_project("dyn", "IDLE", ts)
        card = panel._dynamic_cards["dyn"]
        assert card.project_path is None

    def test_collided_name_no_dynamic_card(self, qtbot, monkeypatch):
        monkeypatch.setattr(config, "GITLAB_PROJECTS", ["g1/foo", "g2/foo"])
        panel = ProjectPanel()
        qtbot.addWidget(panel)
        ts = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
        panel.update_project("foo", "IDLE", ts)
        assert "foo" not in panel._dynamic_cards

    def test_path_cards_and_dynamic_cards_independent(self, qtbot, monkeypatch):
        """discord_name matching a project_path string doesn't cause collision."""
        monkeypatch.setattr(config, "GITLAB_PROJECTS", ["group/proj"])
        panel = ProjectPanel()
        qtbot.addWidget(panel)
        ts = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
        # "group/proj" as discord_name won't match _name_to_path (which maps "proj" -> "group/proj")
        panel.update_project("group/proj", "IDLE", ts)
        assert "group/proj" in panel._dynamic_cards
        assert "group/proj" in panel._path_cards


class TestProjectPanelSelectProject:
    def test_select_project(self, qtbot, monkeypatch):
        monkeypatch.setattr(config, "GITLAB_PROJECTS", ["group/a", "group/b"])
        panel = ProjectPanel()
        qtbot.addWidget(panel)
        panel.select_project("group/a")
        assert panel._selected_card is panel._path_cards["group/a"]
        assert panel._path_cards["group/a"]._selected is True

    def test_select_switches(self, qtbot, monkeypatch):
        monkeypatch.setattr(config, "GITLAB_PROJECTS", ["group/a", "group/b"])
        panel = ProjectPanel()
        qtbot.addWidget(panel)
        panel.select_project("group/a")
        panel.select_project("group/b")
        assert panel._path_cards["group/a"]._selected is False
        assert panel._path_cards["group/b"]._selected is True

    def test_select_none_deselects(self, qtbot, monkeypatch):
        monkeypatch.setattr(config, "GITLAB_PROJECTS", ["group/a"])
        panel = ProjectPanel()
        qtbot.addWidget(panel)
        panel.select_project("group/a")
        panel.select_project(None)
        assert panel._selected_card is None
        assert panel._path_cards["group/a"]._selected is False

    def test_select_unknown_path_does_nothing(self, qtbot, monkeypatch):
        monkeypatch.setattr(config, "GITLAB_PROJECTS", ["group/a"])
        panel = ProjectPanel()
        qtbot.addWidget(panel)
        panel.select_project("nonexistent/path")
        assert panel._selected_card is None


class TestProjectPanelClickSignal:
    def test_card_click_emits_project_clicked(self, qtbot, monkeypatch):
        monkeypatch.setattr(config, "GITLAB_PROJECTS", ["group/a"])
        panel = ProjectPanel()
        qtbot.addWidget(panel)
        card = panel._path_cards["group/a"]
        with qtbot.waitSignal(panel.project_clicked, timeout=1000) as blocker:
            qtbot.mouseClick(card, Qt.LeftButton)
        assert blocker.args == ["group/a"]


class TestProjectPanelGetState:
    def test_get_state_known(self, qtbot, monkeypatch):
        monkeypatch.setattr(config, "GITLAB_PROJECTS", ["group/a"])
        panel = ProjectPanel()
        qtbot.addWidget(panel)
        ts = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
        panel.update_project("a", "INITIALIZE", ts)
        assert panel.get_state("a") == "INITIALIZE"

    def test_get_state_unknown(self, qtbot, monkeypatch):
        monkeypatch.setattr(config, "GITLAB_PROJECTS", [])
        panel = ProjectPanel()
        qtbot.addWidget(panel)
        assert panel.get_state("nope") is None

    def test_get_state_collided_name(self, qtbot, monkeypatch):
        monkeypatch.setattr(config, "GITLAB_PROJECTS", ["g1/foo", "g2/foo"])
        panel = ProjectPanel()
        qtbot.addWidget(panel)
        assert panel.get_state("foo") is None
