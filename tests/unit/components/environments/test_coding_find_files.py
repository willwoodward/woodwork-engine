"""Unit tests for coding environment find_files functionality."""
import pytest
from unittest.mock import Mock, MagicMock, patch


class TestFindFilesPatternParsing:
    """Test find_files pattern parsing for various glob patterns."""

    def test_simple_pattern(self):
        """Test simple filename pattern like '*.py'."""
        from woodwork.components.environments.coding import coding

        # Mock Docker to avoid actual initialization
        with patch('woodwork.components.environments.coding.Docker'):
            env = coding(name="test_env", local_path="/workspace")

            # Mock the docker container
            container = Mock()
            env.docker.get_container = Mock(return_value=container)

            # Mock the exec_run to return test data
            exec_result = Mock()
            exec_result.exit_code = 0
            exec_result.output = b"/workspace/file1.py\n/workspace/file2.py"
            container.exec_run = Mock(return_value=exec_result)

            # Call find_files with simple pattern
            result = env.find_files("*.py")

            # Verify the command was constructed correctly
            container.exec_run.assert_called_once()
            call_args = container.exec_run.call_args[0][0]
            assert "find /workspace -maxdepth 1 -type f -name '*.py'" in call_args
            assert result == ["file1.py", "file2.py"]

    def test_directory_with_glob_pattern(self):
        """Test pattern with directory path like 'woodwork/components/llms/*'."""
        from woodwork.components.environments.coding import coding

        # Mock Docker to avoid actual initialization
        with patch('woodwork.components.environments.coding.Docker'):
            env = coding(name="test_env", local_path="/workspace")

            # Mock the docker container
            container = Mock()
            env.docker.get_container = Mock(return_value=container)

            # Mock the exec_run to return test data
            exec_result = Mock()
            exec_result.exit_code = 0
            exec_result.output = b"/workspace/woodwork/components/llms/llm.py\n/workspace/woodwork/components/llms/openai.py"
            container.exec_run = Mock(return_value=exec_result)

            # Call find_files with directory + glob pattern
            result = env.find_files("woodwork/components/llms/*")

            # Verify the command was constructed correctly
            container.exec_run.assert_called_once()
            call_args = container.exec_run.call_args[0][0]
            assert "find /workspace/woodwork/components/llms -maxdepth 1 -type f -name '*'" in call_args
            assert result == ["woodwork/components/llms/llm.py", "woodwork/components/llms/openai.py"]

    def test_directory_with_specific_extension(self):
        """Test pattern like 'woodwork/components/llms/*.py'."""
        from woodwork.components.environments.coding import coding

        # Mock Docker to avoid actual initialization
        with patch('woodwork.components.environments.coding.Docker'):
            env = coding(name="test_env", local_path="/workspace")

            # Mock the docker container
            container = Mock()
            env.docker.get_container = Mock(return_value=container)

            # Mock the exec_run to return test data
            exec_result = Mock()
            exec_result.exit_code = 0
            exec_result.output = b"/workspace/woodwork/components/llms/llm.py\n/workspace/woodwork/components/llms/openai.py"
            container.exec_run = Mock(return_value=exec_result)

            # Call find_files with directory + specific extension
            result = env.find_files("woodwork/components/llms/*.py")

            # Verify the command was constructed correctly
            container.exec_run.assert_called_once()
            call_args = container.exec_run.call_args[0][0]
            assert "find /workspace/woodwork/components/llms -maxdepth 1 -type f -name '*.py'" in call_args
            assert result == ["woodwork/components/llms/llm.py", "woodwork/components/llms/openai.py"]

    def test_recursive_pattern(self):
        """Test recursive pattern like '**/*.py'."""
        from woodwork.components.environments.coding import coding

        # Mock Docker to avoid actual initialization
        with patch('woodwork.components.environments.coding.Docker'):
            env = coding(name="test_env", local_path="/workspace")

            # Mock the docker container
            container = Mock()
            env.docker.get_container = Mock(return_value=container)

            # Mock the exec_run to return test data
            exec_result = Mock()
            exec_result.exit_code = 0
            exec_result.output = b"/workspace/file1.py\n/workspace/subdir/file2.py"
            container.exec_run = Mock(return_value=exec_result)

            # Call find_files with recursive pattern
            result = env.find_files("**/*.py")

            # Verify the command was constructed correctly (no maxdepth for recursive)
            container.exec_run.assert_called_once()
            call_args = container.exec_run.call_args[0][0]
            assert "find /workspace -type f -name '*.py'" in call_args
            assert "-maxdepth" not in call_args
            assert result == ["file1.py", "subdir/file2.py"]

    def test_empty_result(self):
        """Test when no files match the pattern."""
        from woodwork.components.environments.coding import coding

        # Mock Docker to avoid actual initialization
        with patch('woodwork.components.environments.coding.Docker'):
            env = coding(name="test_env", local_path="/workspace")

            # Mock the docker container
            container = Mock()
            env.docker.get_container = Mock(return_value=container)

            # Mock the exec_run to return error (no matches)
            exec_result = Mock()
            exec_result.exit_code = 1
            exec_result.output = b""
            container.exec_run = Mock(return_value=exec_result)

            # Call find_files with pattern that matches nothing
            result = env.find_files("nonexistent/*")

            # Should return empty list
            assert result == []
