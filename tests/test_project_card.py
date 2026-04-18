"""Tests for ProjectCard and ProjectPanel (Issue #15)."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QPoint, Qt

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


class TestProjectPanelRefresh:
    def test_refresh_adds_new_project(self, qtbot, monkeypatch):
        monkeypatch.setattr(config, "GITLAB_PROJECTS", ["g/a"])
        panel = ProjectPanel()
        qtbot.addWidget(panel)
        monkeypatch.setattr(config, "GITLAB_PROJECTS", ["g/a", "g/b"])
        removed = panel.refresh_projects()
        assert removed == set()
        assert "g/a" in panel._path_cards
        assert "g/b" in panel._path_cards

    def test_refresh_removes_missing_project(self, qtbot, monkeypatch):
        monkeypatch.setattr(config, "GITLAB_PROJECTS", ["g/a", "g/b"])
        panel = ProjectPanel()
        qtbot.addWidget(panel)
        monkeypatch.setattr(config, "GITLAB_PROJECTS", ["g/a"])
        removed = panel.refresh_projects()
        assert removed == {"g/b"}
        assert "g/b" not in panel._path_cards

    def test_refresh_preserves_existing_card_state(self, qtbot, monkeypatch):
        monkeypatch.setattr(config, "GITLAB_PROJECTS", ["g/a"])
        panel = ProjectPanel()
        qtbot.addWidget(panel)
        ts = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
        panel._path_cards["g/a"].update_state("IMPLEMENTATION", ts)
        original_id = id(panel._path_cards["g/a"])
        monkeypatch.setattr(config, "GITLAB_PROJECTS", ["g/a", "g/b"])
        panel.refresh_projects()
        assert id(panel._path_cards["g/a"]) == original_id
        assert panel._path_cards["g/a"].state == "IMPLEMENTATION"

    def test_refresh_recomputes_collision(self, qtbot, monkeypatch):
        monkeypatch.setattr(config, "GITLAB_PROJECTS", ["g1/foo"])
        panel = ProjectPanel()
        qtbot.addWidget(panel)
        assert panel._name_to_path.get("foo") == "g1/foo"
        monkeypatch.setattr(config, "GITLAB_PROJECTS", ["g1/foo", "g2/foo"])
        panel.refresh_projects()
        assert "foo" in panel._collided_names
        assert "foo" not in panel._name_to_path
        # 逆方向: collision 解消
        monkeypatch.setattr(config, "GITLAB_PROJECTS", ["g1/foo"])
        panel.refresh_projects()
        assert "foo" not in panel._collided_names
        assert panel._name_to_path.get("foo") == "g1/foo"

    def test_refresh_updates_display_name_on_collision_change(self, qtbot, monkeypatch):
        monkeypatch.setattr(config, "GITLAB_PROJECTS", ["g1/foo", "g2/foo"])
        panel = ProjectPanel()
        qtbot.addWidget(panel)
        card = panel._path_cards["g1/foo"]
        assert card.display_name == "g1/foo"
        monkeypatch.setattr(config, "GITLAB_PROJECTS", ["g1/foo"])
        panel.refresh_projects()
        assert card.display_name == "foo"
        assert card._name_label.text() == "foo"

    def test_refresh_clears_selected_when_removed(self, qtbot, monkeypatch):
        monkeypatch.setattr(config, "GITLAB_PROJECTS", ["g/a"])
        panel = ProjectPanel()
        qtbot.addWidget(panel)
        panel.select_project("g/a")
        monkeypatch.setattr(config, "GITLAB_PROJECTS", [])
        panel.refresh_projects()
        assert panel._selected_card is None

    def test_refresh_noop(self, qtbot, monkeypatch):
        monkeypatch.setattr(config, "GITLAB_PROJECTS", ["g/a", "g/b"])
        panel = ProjectPanel()
        qtbot.addWidget(panel)
        ids_before = {p: id(c) for p, c in panel._path_cards.items()}
        name_to_path_before = dict(panel._name_to_path)
        collided_before = set(panel._collided_names)
        removed = panel.refresh_projects()
        assert removed == set()
        assert {p: id(c) for p, c in panel._path_cards.items()} == ids_before
        assert panel._name_to_path == name_to_path_before
        assert panel._collided_names == collided_before

    def test_refresh_reorders_layout(self, qtbot, monkeypatch):
        monkeypatch.setattr(config, "GITLAB_PROJECTS", ["g/a", "g/b", "g/c"])
        panel = ProjectPanel()
        qtbot.addWidget(panel)
        ids_before = {p: id(c) for p, c in panel._path_cards.items()}
        monkeypatch.setattr(config, "GITLAB_PROJECTS", ["g/c", "g/a", "g/b"])
        panel.refresh_projects()
        assert {p: id(c) for p, c in panel._path_cards.items()} == ids_before
        widgets_in_layout = [
            panel._layout.itemAt(i).widget() for i in range(3)
        ]
        assert widgets_in_layout == [
            panel._path_cards["g/c"],
            panel._path_cards["g/a"],
            panel._path_cards["g/b"],
        ]

    def test_refresh_preserves_dynamic_card_position(self, qtbot, monkeypatch):
        monkeypatch.setattr(config, "GITLAB_PROJECTS", ["g/a", "g/b"])
        panel = ProjectPanel()
        qtbot.addWidget(panel)
        ts = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
        panel.update_project("dynX", "IMPLEMENTATION", ts)
        dyn_id = id(panel._dynamic_cards["dynX"])
        # 初期 layout: [g/a, g/b, dynX, stretch]
        widgets_before = [panel._layout.itemAt(i).widget() for i in range(3)]
        assert widgets_before == [
            panel._path_cards["g/a"],
            panel._path_cards["g/b"],
            panel._dynamic_cards["dynX"],
        ]
        monkeypatch.setattr(config, "GITLAB_PROJECTS", ["g/b", "g/a", "g/c"])
        panel.refresh_projects()
        widgets_after = [panel._layout.itemAt(i).widget() for i in range(4)]
        assert widgets_after == [
            panel._path_cards["g/b"],
            panel._path_cards["g/a"],
            panel._path_cards["g/c"],
            panel._dynamic_cards["dynX"],
        ]
        assert id(panel._dynamic_cards["dynX"]) == dyn_id

    def test_refresh_removes_dynamic_card_when_path_added(self, qtbot, monkeypatch):
        monkeypatch.setattr(config, "GITLAB_PROJECTS", [])
        panel = ProjectPanel()
        qtbot.addWidget(panel)
        ts = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
        panel.update_project("foo", "IMPLEMENTATION", ts)
        assert "foo" in panel._dynamic_cards
        monkeypatch.setattr(config, "GITLAB_PROJECTS", ["group/foo"])
        panel.refresh_projects()
        assert "foo" not in panel._dynamic_cards
        assert "group/foo" in panel._path_cards
        # layout に dynamic card が残っていないこと（path card のみ + stretch）
        widgets_after = [panel._layout.itemAt(i).widget() for i in range(panel._layout.count() - 1)]
        assert widgets_after == [panel._path_cards["group/foo"]]

    def test_refresh_removes_dynamic_card_on_collision(self, qtbot, monkeypatch):
        monkeypatch.setattr(config, "GITLAB_PROJECTS", [])
        panel = ProjectPanel()
        qtbot.addWidget(panel)
        ts = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
        panel.update_project("foo", "IMPLEMENTATION", ts)
        assert "foo" in panel._dynamic_cards
        monkeypatch.setattr(config, "GITLAB_PROJECTS", ["g1/foo", "g2/foo"])
        panel.refresh_projects()
        assert "foo" not in panel._dynamic_cards
        assert "foo" in panel._collided_names
        assert "g1/foo" in panel._path_cards
        assert "g2/foo" in panel._path_cards

    def test_refresh_keeps_unrelated_dynamic_card(self, qtbot, monkeypatch):
        monkeypatch.setattr(config, "GITLAB_PROJECTS", [])
        panel = ProjectPanel()
        qtbot.addWidget(panel)
        ts = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
        panel.update_project("alpha", "IMPLEMENTATION", ts)
        panel.update_project("beta", "DONE", ts)
        monkeypatch.setattr(config, "GITLAB_PROJECTS", ["group/gamma"])
        panel.refresh_projects()
        assert "alpha" in panel._dynamic_cards
        assert "beta" in panel._dynamic_cards
        assert "group/gamma" in panel._path_cards


class TestProjectCardContextMenu:
    def test_context_menu_policy_set_for_path_card(self, qtbot):
        card = ProjectCard(display_name="foo", project_path="group/foo")
        qtbot.addWidget(card)
        assert card.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu

    def test_context_menu_policy_default_for_dynamic_card(self, qtbot):
        card = ProjectCard(display_name="dyn", project_path=None)
        qtbot.addWidget(card)
        assert card.contextMenuPolicy() == Qt.ContextMenuPolicy.DefaultContextMenu

    def test_context_menu_signal_invokes_handler(self, qtbot, monkeypatch):
        calls: list[QPoint] = []

        def fake_handler(self, pos):
            calls.append(pos)

        monkeypatch.setattr(ProjectCard, "_on_context_menu", fake_handler)
        card = ProjectCard(display_name="foo", project_path="group/foo")
        qtbot.addWidget(card)
        card.customContextMenuRequested.emit(QPoint(10, 20))
        assert len(calls) == 1
        assert calls[0] == QPoint(10, 20)

    def test_context_menu_emits_when_action_selected(self, qtbot):
        card = ProjectCard(display_name="foo", project_path="group/foo")
        qtbot.addWidget(card)
        fake_action = object()
        fake_menu = MagicMock()
        fake_menu.addAction.return_value = fake_action
        fake_menu.exec.return_value = fake_action
        with patch("widgets.QMenu", return_value=fake_menu):
            with qtbot.waitSignal(card.open_issues_page_requested, timeout=1000) as blocker:
                card._on_context_menu(QPoint(0, 0))
        assert blocker.args == ["group/foo"]
        fake_menu.addAction.assert_called_once_with("Open Issues Page in Browser")

    def test_context_menu_no_emit_when_cancelled(self, qtbot):
        card = ProjectCard(display_name="foo", project_path="group/foo")
        qtbot.addWidget(card)
        fake_action = object()
        fake_menu = MagicMock()
        fake_menu.addAction.return_value = fake_action
        fake_menu.exec.return_value = None
        with patch("widgets.QMenu", return_value=fake_menu):
            with qtbot.assertNotEmitted(card.open_issues_page_requested):
                card._on_context_menu(QPoint(0, 0))

    def test_context_menu_no_emit_when_no_path(self, qtbot):
        card = ProjectCard(display_name="dyn", project_path=None)
        qtbot.addWidget(card)
        with patch("widgets.QMenu") as mock_menu_cls:
            with qtbot.assertNotEmitted(card.open_issues_page_requested):
                card._on_context_menu(QPoint(0, 0))
            mock_menu_cls.assert_not_called()


class TestProjectPanelContextMenuRelay:
    def test_panel_relays_open_issues_signal_from_static_card(self, qtbot, monkeypatch):
        monkeypatch.setattr(config, "GITLAB_PROJECTS", ["group/a"])
        panel = ProjectPanel()
        qtbot.addWidget(panel)
        card = panel._path_cards["group/a"]
        with qtbot.waitSignal(panel.open_issues_page_requested, timeout=1000) as blocker:
            card.open_issues_page_requested.emit("group/a")
        assert blocker.args == ["group/a"]

    def test_panel_relays_after_refresh_adds_new_card(self, qtbot, monkeypatch):
        monkeypatch.setattr(config, "GITLAB_PROJECTS", ["group/a"])
        panel = ProjectPanel()
        qtbot.addWidget(panel)
        monkeypatch.setattr(config, "GITLAB_PROJECTS", ["group/a", "group/b"])
        panel.refresh_projects()
        new_card = panel._path_cards["group/b"]
        with qtbot.waitSignal(panel.open_issues_page_requested, timeout=1000) as blocker:
            new_card.open_issues_page_requested.emit("group/b")
        assert blocker.args == ["group/b"]
