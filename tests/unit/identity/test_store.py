"""Tests for the credential store."""

import json
import time
from pathlib import Path

import pytest

from woodwork.identity.store import CredentialStore


@pytest.fixture
def tmp_store(tmp_path):
    """Create a CredentialStore backed by a temporary directory."""
    return CredentialStore(base_dir=tmp_path)


class TestCredentialStore:
    def test_save_and_load(self, tmp_store):
        data = {"access_token": "abc123", "refresh_token": "xyz789"}
        tmp_store.save("google", data)
        loaded = tmp_store.load("google")
        assert loaded == data

    def test_load_missing_provider(self, tmp_store):
        assert tmp_store.load("nonexistent") is None

    def test_delete_existing(self, tmp_store):
        tmp_store.save("google", {"token": "test"})
        assert tmp_store.delete("google") is True
        assert tmp_store.load("google") is None

    def test_delete_nonexistent(self, tmp_store):
        assert tmp_store.delete("nonexistent") is False

    def test_has_valid_credentials_no_expiry(self, tmp_store):
        tmp_store.save("google", {"access_token": "abc"})
        assert tmp_store.has_valid_credentials("google") is True

    def test_has_valid_credentials_not_expired(self, tmp_store):
        future_expiry = time.time() + 3600
        tmp_store.save("google", {"access_token": "abc", "expiry": future_expiry})
        assert tmp_store.has_valid_credentials("google") is True

    def test_has_valid_credentials_expired(self, tmp_store):
        past_expiry = time.time() - 100
        tmp_store.save("google", {"access_token": "abc", "expiry": past_expiry})
        assert tmp_store.has_valid_credentials("google") is False

    def test_has_valid_credentials_missing(self, tmp_store):
        assert tmp_store.has_valid_credentials("google") is False

    def test_file_permissions(self, tmp_store, tmp_path):
        tmp_store.save("google", {"token": "secret"})
        file_path = tmp_path / "google.json"
        # Check file is readable only by owner
        mode = file_path.stat().st_mode & 0o777
        assert mode == 0o600

    def test_corrupted_file_returns_none(self, tmp_store, tmp_path):
        file_path = tmp_path / "google.json"
        file_path.write_text("not valid json {{{")
        assert tmp_store.load("google") is None

    def test_overwrite_existing(self, tmp_store):
        tmp_store.save("google", {"version": 1})
        tmp_store.save("google", {"version": 2})
        loaded = tmp_store.load("google")
        assert loaded["version"] == 2
