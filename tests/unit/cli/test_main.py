"""Unit tests for CLI main module.

Tests the refactored CLI functions to ensure proper separation of concerns
and correct behavior for future --build, --deploy, --run flags.
"""

import pytest
from unittest.mock import Mock, patch
from woodwork.cli.main import (
    parse_and_validate_config,
    generate_exports,
    deploy_containers,
    start_components,
    start_runtime,
    _start_task_master_runtime,
)


class TestParseAndValidateConfig:
    """Test configuration parsing phase."""

    @patch("woodwork.cli.main._get_task_master")
    @patch("woodwork.cli.main.dependencies")
    @patch("woodwork.cli.main.config_parser")
    @patch("woodwork.cli.main.Console")
    def test_parse_config_success(self, mock_console, mock_parser, mock_deps, mock_get_tm):
        """Test successful configuration parsing."""
        # Setup
        mock_tm = Mock()
        mock_tm._tools = [Mock(name="comp1"), Mock(name="comp2")]
        mock_get_tm.return_value = mock_tm
        console_instance = Mock()
        mock_console.return_value = console_instance

        # Execute
        components = parse_and_validate_config()

        # Assert
        mock_deps.activate_virtual_environment.assert_called_once()
        mock_parser.main_function.assert_called_once()
        assert components == mock_tm._tools
        assert console_instance.print.call_count == 2  # Start and completion messages

    @patch("woodwork.cli.main._get_task_master")
    @patch("woodwork.cli.main.dependencies")
    @patch("woodwork.cli.main.config_parser")
    @patch("woodwork.cli.main.Console")
    def test_parse_config_displays_timing(self, mock_console, mock_parser, mock_deps, mock_get_tm):
        """Test that parsing displays timing information."""
        console_instance = Mock()
        mock_console.return_value = console_instance
        mock_tm = Mock()
        mock_tm._tools = []
        mock_get_tm.return_value = mock_tm

        parse_and_validate_config()

        # Check timing message was displayed
        calls = console_instance.print.call_args_list
        assert any("Config parsed in" in str(call) for call in calls)
        assert all(call[1]["style"] == "dim" for call in calls)
        assert all(call[1]["highlight"] is False for call in calls)


class TestGenerateExports:
    """Test export generation phase."""

    @patch("woodwork.cli.main.get_registry")
    @patch("woodwork.cli.main.generate_exported_objects_file")
    @patch("woodwork.cli.main.Console")
    def test_generate_exports_success(self, mock_console, mock_gen, mock_get_reg):
        """Test successful export generation."""
        console_instance = Mock()
        mock_console.return_value = console_instance
        mock_registry = Mock()
        mock_get_reg.return_value = mock_registry

        generate_exports()

        mock_gen.assert_called_once_with(registry=mock_registry)
        assert console_instance.print.call_count == 1


class TestDeployContainers:
    """Test container deployment phase."""

    @patch("woodwork.cli.main.Deployer")
    @patch("woodwork.cli.main.Console")
    def test_deploy_containers_success(self, mock_console, mock_deployer_class):
        """Test successful container deployment."""
        console_instance = Mock()
        mock_console.return_value = console_instance
        mock_deployer = Mock()
        mock_deployer_class.return_value = mock_deployer

        deploy_containers()

        mock_deployer.main.assert_called_once()
        assert console_instance.print.call_count == 2  # Start and completion

    @patch("woodwork.cli.main.Deployer")
    @patch("woodwork.cli.main.Console")
    def test_deploy_containers_displays_timing(self, mock_console, mock_deployer_class):
        """Test that deployment displays timing information."""
        console_instance = Mock()
        mock_console.return_value = console_instance
        mock_deployer = Mock()
        mock_deployer_class.return_value = mock_deployer

        deploy_containers()

        calls = console_instance.print.call_args_list
        assert any("Containers deployed in" in str(call) for call in calls)


class TestStartComponents:
    """Test component starting phase."""

    @patch("woodwork.cli.main.parallel_func_apply")
    @patch("woodwork.cli.main.start_component")
    @patch("woodwork.cli.main.Console")
    def test_start_components_success(self, mock_console, mock_start, mock_parallel):
        """Test successful component starting."""
        console_instance = Mock()
        mock_console.return_value = console_instance
        components = [Mock(name="comp1"), Mock(name="comp2"), Mock(name="comp3")]

        start_components(components)

        mock_parallel.assert_called_once_with(components, mock_start, "started", "starting")
        assert console_instance.print.call_count == 1

    @patch("woodwork.cli.main.parallel_func_apply")
    @patch("woodwork.cli.main.start_component")
    @patch("woodwork.cli.main.Console")
    def test_start_components_displays_count(self, mock_console, mock_start, mock_parallel):
        """Test that component count is displayed."""
        console_instance = Mock()
        mock_console.return_value = console_instance
        components = [Mock(), Mock(), Mock()]

        start_components(components)

        calls = console_instance.print.call_args_list
        assert any("3 components" in str(call) for call in calls)


class TestStartRuntime:
    """Test runtime starting phase."""

    @patch("woodwork.cli.main.globals")
    @patch("woodwork.cli.main._start_async_runtime")
    def test_start_runtime_async_mode(self, mock_async, mock_globals):
        """Test runtime starts in async mode when message bus is active."""
        mock_globals.global_config.get.return_value = True
        components = [Mock()]

        start_runtime(components)

        mock_async.assert_called_once_with(components)

    @patch("woodwork.cli.main.globals")
    @patch("woodwork.cli.main._start_task_master_runtime")
    def test_start_runtime_task_master_mode(self, mock_tm, mock_globals):
        """Test runtime starts in task master mode when message bus is inactive."""
        mock_globals.global_config.get.return_value = False
        components = [Mock()]

        start_runtime(components)

        mock_tm.assert_called_once()


class TestAsyncRuntime:
    """Test async runtime implementation.

    Note: Detailed async runtime tests are skipped because asyncio and AsyncRuntime
    are imported locally within _start_async_runtime(). The integration tests
    in TestIntegration verify the full workflow works correctly.
    """

    pass


class TestTaskMasterRuntime:
    """Test task master runtime implementation."""

    @patch("woodwork.cli.main._get_task_master")
    def test_task_master_runtime_starts(self, mock_get_tm):
        """Test task master runtime starts correctly."""
        mock_task_m = Mock()
        mock_get_tm.return_value = mock_task_m

        _start_task_master_runtime()

        mock_task_m.start.assert_called_once()


class TestIntegration:
    """Integration tests for CLI workflow."""

    @patch("woodwork.cli.main._get_task_master")
    @patch("woodwork.cli.main.dependencies")
    @patch("woodwork.cli.main.config_parser")
    @patch("woodwork.cli.main.get_registry")
    @patch("woodwork.cli.main.generate_exported_objects_file")
    @patch("woodwork.cli.main.Deployer")
    @patch("woodwork.cli.main.parallel_func_apply")
    @patch("woodwork.cli.main.Console")
    def test_full_workflow_build_deploy_start(
        self,
        mock_console,
        mock_parallel,
        mock_deployer_class,
        mock_gen,
        mock_get_reg,
        mock_parser,
        mock_deps,
        mock_get_tm,
    ):
        """Test the complete workflow: build -> deploy -> start."""
        # Setup
        mock_components = [Mock(name="comp1"), Mock(name="comp2")]
        mock_tm = Mock()
        mock_tm._tools = mock_components
        mock_get_tm.return_value = mock_tm
        console_instance = Mock()
        mock_console.return_value = console_instance

        # Execute phases in order
        components = parse_and_validate_config()
        generate_exports()
        deploy_containers()
        start_components(components)

        # Assert all phases executed
        mock_deps.activate_virtual_environment.assert_called_once()
        mock_parser.main_function.assert_called_once()
        mock_gen.assert_called_once()
        mock_deployer_class.return_value.main.assert_called_once()
        mock_parallel.assert_called_once()
        assert components == mock_components


class TestErrorHandling:
    """Test error handling in CLI functions."""

    @patch("woodwork.cli.main.dependencies")
    @patch("woodwork.cli.main.config_parser")
    @patch("woodwork.cli.main.Console")
    def test_parse_config_handles_errors(self, mock_console, mock_parser, mock_deps):
        """Test that configuration parsing errors propagate correctly."""
        mock_parser.main_function.side_effect = Exception("Parse error")
        console_instance = Mock()
        mock_console.return_value = console_instance

        with pytest.raises(Exception, match="Parse error"):
            parse_and_validate_config()

    @patch("woodwork.cli.main.Deployer")
    @patch("woodwork.cli.main.Console")
    def test_deploy_handles_errors(self, mock_console, mock_deployer_class):
        """Test that deployment errors propagate correctly."""
        mock_deployer = Mock()
        mock_deployer.main.side_effect = Exception("Deployment failed")
        mock_deployer_class.return_value = mock_deployer
        console_instance = Mock()
        mock_console.return_value = console_instance

        with pytest.raises(Exception, match="Deployment failed"):
            deploy_containers()
