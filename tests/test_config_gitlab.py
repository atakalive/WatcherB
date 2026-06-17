import os

import pytest

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

    各テストは monkeypatch で env var を設定し、config を再読込して assert する。
    再読込は public な config.reload() に空の一時 .env を dotenv_path で渡して行い、
    開発機プロジェクトルートの本番 .env に依存しない hermetic な構成にする
    （旧実装はモジュールトップの load_dotenv() を再実行する経路で実 .env の値を
    os.environ に載せ、test_gitlab_token_default 等を壊していた。WatcherB #38）。
    """

    @pytest.fixture(autouse=True)
    def _hermetic_config(self, tmp_path):
        """空の一時 .env を用意し、config のモジュール変数と os.environ を保存・復元する."""
        env_file = tmp_path / ".env"
        env_file.write_text("")
        self._empty_env = env_file
        # reload() が mutate する全属性（managed env keys + ICON_PATH）を動的に列挙する。
        # config 側に managed key が追加されてもテストの保存漏れが起きないようにする。
        saved_config = {
            attr: getattr(config, attr)
            for attr in (config._MANAGED_ENV_KEYS | {"ICON_PATH"})
        }
        saved_env = os.environ.copy()
        saved_dotenv_keys = config._last_dotenv_keys.copy()
        yield
        for attr, val in saved_config.items():
            setattr(config, attr, val)
        os.environ.clear()
        os.environ.update(saved_env)
        config._last_dotenv_keys = saved_dotenv_keys

    def _reload(self):
        """Re-evaluate config module-level vars hermetically from a tmp empty .env.

        _last_dotenv_keys を空にしてから空 .env で reload することで、reload が os.environ の
        managed key を pop して monkeypatch 値を消す副作用を防ぎ、os.environ（= monkeypatch で
        設定した値）だけを反映させる。
        """
        config._last_dotenv_keys = set()
        config.reload(dotenv_path=self._empty_env)

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
