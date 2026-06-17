"""Tests for DiscordThread._raw_edit_to_dict (Issue #37)."""

from datetime import datetime
from types import SimpleNamespace

from discord_client import DiscordThread


def _payload(data, cached_message=None, message_id=42):
    return SimpleNamespace(data=data, cached_message=cached_message, message_id=message_id)


def test_content_present():
    d = DiscordThread._raw_edit_to_dict(_payload({"content": "x"}))
    assert d is not None
    assert d["content"] == "x"
    assert d["message_id"] == 42


def test_no_content_returns_none():
    assert DiscordThread._raw_edit_to_dict(_payload({})) is None


def test_empty_content_returns_none():
    assert DiscordThread._raw_edit_to_dict(_payload({"content": ""})) is None


def test_created_at_from_cached_message():
    cached = SimpleNamespace(created_at=datetime(2020, 1, 1))
    d = DiscordThread._raw_edit_to_dict(_payload({"content": "x"}, cached_message=cached))
    assert d["created_at"] == datetime(2020, 1, 1)


def test_created_at_from_edited_timestamp():
    d = DiscordThread._raw_edit_to_dict(
        _payload({"content": "x", "edited_timestamp": "2021-06-01T12:00:00"})
    )
    assert isinstance(d["created_at"], datetime)
    assert d["created_at"] == datetime(2021, 6, 1, 12, 0, 0)


def test_created_at_none_when_absent():
    d = DiscordThread._raw_edit_to_dict(_payload({"content": "x"}))
    assert d["created_at"] is None


def test_created_at_invalid_timestamp_no_crash():
    d = DiscordThread._raw_edit_to_dict(
        _payload({"content": "x", "edited_timestamp": "not-a-date"})
    )
    assert d["created_at"] is None
