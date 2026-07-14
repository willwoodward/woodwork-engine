"""Tests for YAML eval suite loader."""

import os

import pytest
import yaml

from woodwork.eval.loader import EvalSuite, load_suite


class TestLoadSuite:
    def _write_yaml(self, tmpdir, filename, data):
        path = os.path.join(tmpdir, filename)
        with open(path, "w") as f:
            yaml.dump(data, f)
        return path

    def test_basic_loading(self, tmp_path):
        data = {
            "config": "main.ww",
            "cases": [
                {
                    "name": "test_case",
                    "input": "hello",
                    "assert": {"response_contains": ["hi"]},
                }
            ],
        }
        path = self._write_yaml(str(tmp_path), "suite.yaml", data)
        suite = load_suite(path)

        assert isinstance(suite, EvalSuite)
        assert suite.config_path == os.path.normpath(os.path.join(str(tmp_path), "main.ww"))
        assert len(suite.cases) == 1
        assert suite.cases[0].name == "test_case"
        assert suite.cases[0].input == "hello"
        assert suite.cases[0].assertions == {"response_contains": ["hi"]}

    def test_multiple_cases(self, tmp_path):
        data = {
            "config": "main.ww",
            "cases": [
                {"name": "case1", "input": "hello", "assert": {}},
                {"name": "case2", "input": "search for X", "assert": {"tool_called": "search"}},
            ],
        }
        path = self._write_yaml(str(tmp_path), "suite.yaml", data)
        suite = load_suite(path)
        assert len(suite.cases) == 2

    def test_missing_config_key(self, tmp_path):
        data = {"cases": [{"name": "a", "input": "b"}]}
        path = self._write_yaml(str(tmp_path), "suite.yaml", data)
        with pytest.raises(ValueError, match="Missing 'config'"):
            load_suite(path)

    def test_no_cases(self, tmp_path):
        data = {"config": "main.ww", "cases": []}
        path = self._write_yaml(str(tmp_path), "suite.yaml", data)
        with pytest.raises(ValueError, match="No cases"):
            load_suite(path)

    def test_case_missing_name(self, tmp_path):
        data = {"config": "main.ww", "cases": [{"input": "hello"}]}
        path = self._write_yaml(str(tmp_path), "suite.yaml", data)
        with pytest.raises(ValueError, match="missing 'name'"):
            load_suite(path)

    def test_case_missing_input(self, tmp_path):
        data = {"config": "main.ww", "cases": [{"name": "test"}]}
        path = self._write_yaml(str(tmp_path), "suite.yaml", data)
        with pytest.raises(ValueError, match="missing 'input'"):
            load_suite(path)

    def test_config_path_resolution(self, tmp_path):
        """Config path should be resolved relative to the YAML file."""
        subdir = tmp_path / "sub"
        subdir.mkdir()
        data = {"config": "../main.ww", "cases": [{"name": "a", "input": "b", "assert": {}}]}
        path = self._write_yaml(str(subdir), "suite.yaml", data)
        suite = load_suite(path)
        assert suite.config_path == os.path.normpath(os.path.join(str(tmp_path), "main.ww"))

    def test_case_without_assertions(self, tmp_path):
        """Cases without assert key should get empty assertions dict."""
        data = {"config": "main.ww", "cases": [{"name": "test", "input": "hello"}]}
        path = self._write_yaml(str(tmp_path), "suite.yaml", data)
        suite = load_suite(path)
        assert suite.cases[0].assertions == {}

    def test_invalid_yaml_type(self, tmp_path):
        """Top-level list instead of mapping should raise."""
        path = os.path.join(str(tmp_path), "suite.yaml")
        with open(path, "w") as f:
            f.write("- item1\n- item2\n")
        with pytest.raises(ValueError, match="Expected a YAML mapping"):
            load_suite(path)
