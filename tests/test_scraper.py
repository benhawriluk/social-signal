"""Tests for the scraper module (unit tests that don't hit Reddit)."""

from src.scraper import _hash_author


class TestHashAuthor:
    def test_hashes_username(self):
        h = _hash_author("testuser")
        assert h is not None
        assert len(h) == 64  # SHA-256 hex digest

    def test_same_username_same_hash(self):
        assert _hash_author("user1") == _hash_author("user1")

    def test_different_username_different_hash(self):
        assert _hash_author("user1") != _hash_author("user2")

    def test_deleted_returns_none(self):
        assert _hash_author("[deleted]") is None

    def test_none_returns_none(self):
        assert _hash_author(None) is None
