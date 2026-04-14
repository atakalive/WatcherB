"""Tests for config.reload() and MainWindow._reload_config()."""

import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

import config


class TestConfigReload:
    """config.reload() の単体テスト."""

    @pytest.fixture(autouse=True)
    def _save_restore_config(self):
        """Save and restore config module variables and os.environ."""
        saved_config = {attr: getattr(config, attr) for attr in [
            "DISCORD_BOT_TOKEN", "CHANNEL_ID", "HISTORY_LIMIT", "SEND_ENABLED",
            "GITLAB_BASE_URL", "GITLAB_URL", "GITLAB_TOKEN", "GITLAB_PROJECTS",
            "ISSUE_LIST_WIDTH", "ICON_PATH", "WINDOW_WIDTH", "WINDOW_HEIGHT",
            "FONT_FAMILY", "FONT_SIZE", "LINE_HEIGHT",
        ]}
        saved_env = os.environ.copy()
        saved_dotenv_keys = config._last_dotenv_keys.copy()
        yield
        for attr, val in saved_config.items():
            setattr(config, attr, val)
        os.environ.clear()
        os.environ.update(saved_env)
        config._last_dotenv_keys = saved_dotenv_keys

    def test_reload_updates_font_size(self, tmp_path):
        """FONT_SIZE が .env の変更で更新されること."""
        env_file = tmp_path / ".env"
        env_file.write_text("FONT_SIZE=30\n")
        config.reload(dotenv_path=env_file)
        assert config.FONT_SIZE == 30

    def test_reload_restores_default_on_key_removal(self, tmp_path):
        """.env からキーを削除した場合、デフォルト値に戻ること."""
        env_file = tmp_path / ".env"
        env_file.write_text("FONT_SIZE=30\n")
        config.reload(dotenv_path=env_file)
        assert config.FONT_SIZE == 30
        # FONT_SIZE を .env から削除して reload
        env_file.write_text("")
        config.reload(dotenv_path=env_file)
        assert config.FONT_SIZE == 20  # デフォルト値

    def test_reload_preserves_shell_env_vars(self, tmp_path):
        """シェル環境変数由来の設定が reload で破壊されないこと."""
        os.environ["FONT_SIZE"] = "24"
        env_file = tmp_path / ".env"
        env_file.write_text("")  # .env に FONT_SIZE なし
        config._last_dotenv_keys = set()  # 前回も .env にない
        config.reload(dotenv_path=env_file)
        assert config.FONT_SIZE == 24  # シェル環境変数の値が保持される

    def test_reload_invalid_value_no_partial_update(self, tmp_path):
        """不正値で ValueError が発生した場合、モジュール変数が変更されないこと.

        二段階防御の検証: FONT_SIZE より後に変換される LINE_HEIGHT で失敗させ、
        直接代入方式なら FONT_SIZE がデフォルト値に変わるケースを捕捉する。
        """
        env_file = tmp_path / ".env"
        # まず FONT_SIZE=30 で reload して非デフォルト値にする
        env_file.write_text("FONT_SIZE=30\n")
        config.reload(dotenv_path=env_file)
        assert config.FONT_SIZE == 30
        # FONT_SIZE=30 + LINE_HEIGHT=bad で失敗させる
        env_file.write_text("FONT_SIZE=30\nLINE_HEIGHT=bad\n")
        with pytest.raises(ValueError):
            config.reload(dotenv_path=env_file)
        # FONT_SIZE は 30 のまま（デフォルト 20 に巻き戻っていないこと）
        assert config.FONT_SIZE == 30


class TestReloadConfig:
    """MainWindow._reload_config() の配線テスト."""

    def test_reload_success_applies_qss(self, monkeypatch):
        """成功時に QApplication.setStyleSheet が呼ばれること."""
        from watcher import MainWindow
        mw = MagicMock(spec=MainWindow)
        mw.statusBar.return_value = MagicMock()
        mock_app = MagicMock()
        monkeypatch.setattr(config, "reload", lambda **kw: None)
        with patch("watcher.QApplication.instance", return_value=mock_app):
            MainWindow._reload_config(mw)
        mock_app.setStyleSheet.assert_called_once()
        mw.statusBar().showMessage.assert_called_once_with("Configuration reloaded", 3000)

    def test_reload_failure_shows_error(self, monkeypatch):
        """失敗時にステータスバーにエラーが表示され、QSS は更新されないこと."""
        from watcher import MainWindow
        mw = MagicMock(spec=MainWindow)
        mw.statusBar.return_value = MagicMock()
        mock_app = MagicMock()
        def raise_error(**kw):
            raise ValueError("bad value")
        monkeypatch.setattr(config, "reload", raise_error)
        with patch("watcher.QApplication.instance", return_value=mock_app):
            MainWindow._reload_config(mw)
        mock_app.setStyleSheet.assert_not_called()
        msg = mw.statusBar().showMessage.call_args[0][0]
        assert "bad value" in msg
