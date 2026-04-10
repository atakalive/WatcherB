import importlib

import config
from config import _parse_gitlab_projects


class TestParseGitlabProjects:
    def test_empty_string(self):
        assert _parse_gitlab_projects("") == []

    def test_single_project(self):
        assert _parse_gitlab_projects("a/b") == ["a/b"]

    def test_multiple_projects(self):
        assert _parse_gitlab_projects("a/b,c/d,e/f/g") == ["a/b", "c/d", "e/f/g"]

    def test_whitespace_trimmed(self):
        assert _parse_gitlab_projects("a/b, c/d , e/f") == ["a/b", "c/d", "e/f"]

    def test_trailing_comma(self):
        assert _parse_gitlab_projects("a/b,") == ["a/b"]

    def test_only_commas(self):
        assert _parse_gitlab_projects(",,,") == []


class TestConfigModuleLevelVars:
    """Test that module-level variables are correctly evaluated from env vars.

    Each test sets env vars via monkeypatch, reloads config, and asserts.
    monkeypatch automatically restores env vars after each test.
    """

    def _reload(self):
        """Reload config module to re-evaluate module-level variables."""
        importlib.reload(config)

    def test_gitlab_url_default(self, monkeypatch):
        monkeypatch.delenv("GITLAB_URL", raising=False)
        self._reload()
        assert config.GITLAB_URL == "https://gitlab.com"

    def test_gitlab_url_trailing_slash_removed(self, monkeypatch):
        monkeypatch.setenv("GITLAB_URL", "https://gitlab.example.com/")
        self._reload()
        assert config.GITLAB_URL == "https://gitlab.example.com"

    def test_gitlab_url_custom(self, monkeypatch):
        monkeypatch.setenv("GITLAB_URL", "https://gitlab.mycompany.com")
        self._reload()
        assert config.GITLAB_URL == "https://gitlab.mycompany.com"

    def test_gitlab_token_default(self, monkeypatch):
        monkeypatch.delenv("GITLAB_TOKEN", raising=False)
        self._reload()
        assert config.GITLAB_TOKEN == ""

    def test_gitlab_token_set(self, monkeypatch):
        monkeypatch.setenv("GITLAB_TOKEN", "glpat-xxxx")
        self._reload()
        assert config.GITLAB_TOKEN == "glpat-xxxx"

    def test_gitlab_projects_from_env(self, monkeypatch):
        monkeypatch.setenv("GITLAB_PROJECTS", "a/b,c/d")
        self._reload()
        assert config.GITLAB_PROJECTS == ["a/b", "c/d"]

    def test_gitlab_projects_empty(self, monkeypatch):
        monkeypatch.setenv("GITLAB_PROJECTS", "")
        self._reload()
        assert config.GITLAB_PROJECTS == []

    def test_issue_list_width_default(self, monkeypatch):
        monkeypatch.delenv("ISSUE_LIST_WIDTH", raising=False)
        self._reload()
        assert config.ISSUE_LIST_WIDTH == 280

    def test_issue_list_width_custom(self, monkeypatch):
        monkeypatch.setenv("ISSUE_LIST_WIDTH", "350")
        self._reload()
        assert config.ISSUE_LIST_WIDTH == 350


def test_issue_browser_importable():
    import issue_browser  # noqa: F401
