import unittest

import pytest

from woodwork.errors import ParseError
from woodwork.argument_parser import parse_args, check_parse_conflicts


class TestCLIArgs(unittest.TestCase):
    @pytest.mark.skip("Deprecated functionality. This test is no longer relevant.")
    def test_log_default(self):
        args = parse_args([])
        self.assertEqual(args.log, "info")

    @pytest.mark.skip("Deprecated functionality. This test is no longer relevant.")
    def test_log_debug(self):
        args = parse_args(["--log", "debug"])
        self.assertEqual(args.log, "debug")

    @pytest.mark.skip("Deprecated functionality. This test is no longer relevant.")
    def test_invalid_log_level(self):
        with pytest.raises(SystemExit):
            parse_args(["--log", "invalid"])

    def test_target_argument(self):
        args = parse_args(["--workflow", "add", "--target", "/tmp/foo.yaml"])
        self.assertEqual(args.workflow, "add")
        self.assertEqual(args.target, "/tmp/foo.yaml")

    def test_init_argument(self):
        args = parse_args(["--init", "isolated"])
        self.assertEqual(args.init, "isolated")

    def test_mode_argument(self):
        args = parse_args(["--mode", "debug"])
        self.assertEqual(args.mode, "debug")

    def test_missing_add_workflow_target(self):
        args = parse_args(["--workflow", "add"])

        with pytest.raises(ParseError):
            check_parse_conflicts(args)

    def test_missing_remove_workflow_target(self):
        args = parse_args(["--workflow", "remove"])

        with pytest.raises(ParseError):
            check_parse_conflicts(args)

    def test_missing_find_workflow_target(self):
        args = parse_args(["--workflow", "find"])

        with pytest.raises(ParseError):
            check_parse_conflicts(args)

    def test_valid_add_workflow_target(self):
        args = parse_args(["--workflow", "add", "--target", "/tmp/foo.yaml"])
        check_parse_conflicts(args)
        assert args.target == "/tmp/foo.yaml"
        assert args.workflow == "add"
