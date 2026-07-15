"""Tests for woodwork.primitives (File, Env)."""

import os

import pytest

from woodwork.primitives import Env, File


class TestEnv:
    def test_reads_existing_variable(self, monkeypatch):
        monkeypatch.setenv("TEST_KEY", "hello")
        value = Env("TEST_KEY")
        assert value == "hello"

    def test_is_str_subclass(self, monkeypatch):
        monkeypatch.setenv("TEST_KEY", "hello")
        value = Env("TEST_KEY")
        assert isinstance(value, str)

    def test_transparent_to_str_operations(self, monkeypatch):
        monkeypatch.setenv("TEST_KEY", "world")
        value = Env("TEST_KEY")
        assert value.upper() == "WORLD"
        assert f"say {value}" == "say world"

    def test_raises_on_missing_variable(self, monkeypatch):
        monkeypatch.delenv("MISSING_KEY", raising=False)
        with pytest.raises(KeyError, match="MISSING_KEY"):
            Env("MISSING_KEY")

    def test_stores_key_attribute(self, monkeypatch):
        monkeypatch.setenv("MY_VAR", "val")
        value = Env("MY_VAR")
        assert value.key == "MY_VAR"

    def test_repr(self, monkeypatch):
        monkeypatch.setenv("REPR_KEY", "x")
        value = Env("REPR_KEY")
        assert "REPR_KEY" in repr(value)


class TestFile:
    def test_stores_path(self):
        f = File("prompts/system.txt")
        assert f.path == "prompts/system.txt"

    def test_str_returns_path(self):
        f = File("prompts/system.txt")
        assert str(f) == "prompts/system.txt"

    def test_repr(self):
        f = File("foo.txt")
        assert "foo.txt" in repr(f)

    def test_read(self, tmp_path):
        p = tmp_path / "prompt.txt"
        p.write_text("You are helpful.")
        f = File(str(p))
        assert f.read() == "You are helpful."

    def test_read_missing_file_raises(self, tmp_path):
        f = File(str(tmp_path / "nonexistent.txt"))
        with pytest.raises(FileNotFoundError):
            f.read()
