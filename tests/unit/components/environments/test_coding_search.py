"""Unit tests for coding environment find_files and search_in_files functionality."""

from unittest.mock import Mock, patch


class TestSearchInFilesPatternParsing:
    """Test search_in_files pattern parsing for various glob patterns."""

    def test_search_with_recursive_directory_pattern(self):
        """Test search with pattern like 'tests/**/*.py'."""
        from woodwork.components.environments.coding import coding

        # Mock Docker to avoid actual initialization
        with patch("woodwork.components.environments.coding.Docker"):
            env = coding(name="test_env", local_path="/workspace")

            # Mock the docker container
            container = Mock()
            env.docker.get_container = Mock(return_value=container)

            # Mock the exec_run to return test data
            exec_result = Mock()
            exec_result.exit_code = 0
            exec_result.output = b"/workspace/tests/test_file.py:10:def test_llm():\n/workspace/tests/subdir/test_other.py:5:    llm = LLM()"
            container.exec_run = Mock(return_value=exec_result)

            # Call search_in_files with recursive directory pattern
            result = env.search_in_files("llm", file_glob="tests/**/*.py", case_insensitive=True)

            # Verify the command was constructed correctly
            container.exec_run.assert_called_once()
            call_args = container.exec_run.call_args[0][0]
            # Should search in /workspace/tests recursively
            assert "find /workspace/tests -type f -name '*.py'" in call_args
            assert "-i" in call_args  # case insensitive flag
            assert result == "tests/test_file.py:10:def test_llm():\ntests/subdir/test_other.py:5:    llm = LLM()"

    def test_search_with_simple_recursive_pattern(self):
        """Test search with pattern like '**/*.py'."""
        from woodwork.components.environments.coding import coding

        # Mock Docker to avoid actual initialization
        with patch("woodwork.components.environments.coding.Docker"):
            env = coding(name="test_env", local_path="/workspace")

            # Mock the docker container
            container = Mock()
            env.docker.get_container = Mock(return_value=container)

            # Mock the exec_run to return test data
            exec_result = Mock()
            exec_result.exit_code = 0
            exec_result.output = b"/workspace/file.py:1:import llm"
            container.exec_run = Mock(return_value=exec_result)

            # Call search_in_files with simple recursive pattern
            env.search_in_files("llm", file_glob="**/*.py")

            # Verify the command searches everywhere
            container.exec_run.assert_called_once()
            call_args = container.exec_run.call_args[0][0]
            assert "find /workspace -type f -name '*.py'" in call_args

    def test_search_with_directory_no_recursive(self):
        """Test search with pattern like 'tests/*.py' (non-recursive)."""
        from woodwork.components.environments.coding import coding

        # Mock Docker to avoid actual initialization
        with patch("woodwork.components.environments.coding.Docker"):
            env = coding(name="test_env", local_path="/workspace")

            # Mock the docker container
            container = Mock()
            env.docker.get_container = Mock(return_value=container)

            # Mock the exec_run to return test data
            exec_result = Mock()
            exec_result.exit_code = 0
            exec_result.output = b"/workspace/tests/test_file.py:10:def test_llm():"
            container.exec_run = Mock(return_value=exec_result)

            # Call search_in_files with non-recursive directory pattern
            env.search_in_files("llm", file_glob="tests/*.py")

            # Verify maxdepth 1 is used
            container.exec_run.assert_called_once()
            call_args = container.exec_run.call_args[0][0]
            assert "find /workspace/tests -maxdepth 1 -type f -name '*.py'" in call_args

    def test_search_with_context_lines(self):
        """Test search with context lines."""
        from woodwork.components.environments.coding import coding

        # Mock Docker to avoid actual initialization
        with patch("woodwork.components.environments.coding.Docker"):
            env = coding(name="test_env", local_path="/workspace")

            # Mock the docker container
            container = Mock()
            env.docker.get_container = Mock(return_value=container)

            # Mock the exec_run to return test data
            exec_result = Mock()
            exec_result.exit_code = 0
            exec_result.output = b"result"
            container.exec_run = Mock(return_value=exec_result)

            # Call search_in_files with context lines
            env.search_in_files("test", file_glob="*.py", context_lines=2)

            # Verify context flag is included
            container.exec_run.assert_called_once()
            call_args = container.exec_run.call_args[0][0]
            assert "-C 2" in call_args

    def test_search_no_matches(self):
        """Test search when no matches are found."""
        from woodwork.components.environments.coding import coding

        # Mock Docker to avoid actual initialization
        with patch("woodwork.components.environments.coding.Docker"):
            env = coding(name="test_env", local_path="/workspace")

            # Mock the docker container
            container = Mock()
            env.docker.get_container = Mock(return_value=container)

            # Mock the exec_run to return error (no matches)
            exec_result = Mock()
            exec_result.exit_code = 1
            exec_result.output = b""
            container.exec_run = Mock(return_value=exec_result)

            # Call search_in_files
            result = env.search_in_files("nonexistent", file_glob="*.py")

            # Should return no matches message
            assert result == "No matches found"


class TestFindFilesPatternParsing:
    """Test find_files pattern parsing for various glob patterns."""

    def test_simple_pattern(self):
        """Test simple filename pattern like '*.py'."""
        from woodwork.components.environments.coding import coding

        # Mock Docker to avoid actual initialization
        with patch("woodwork.components.environments.coding.Docker"):
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
        with patch("woodwork.components.environments.coding.Docker"):
            env = coding(name="test_env", local_path="/workspace")

            # Mock the docker container
            container = Mock()
            env.docker.get_container = Mock(return_value=container)

            # Mock the exec_run to return test data
            exec_result = Mock()
            exec_result.exit_code = 0
            exec_result.output = (
                b"/workspace/woodwork/components/llms/llm.py\n/workspace/woodwork/components/llms/openai.py"
            )
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
        with patch("woodwork.components.environments.coding.Docker"):
            env = coding(name="test_env", local_path="/workspace")

            # Mock the docker container
            container = Mock()
            env.docker.get_container = Mock(return_value=container)

            # Mock the exec_run to return test data
            exec_result = Mock()
            exec_result.exit_code = 0
            exec_result.output = (
                b"/workspace/woodwork/components/llms/llm.py\n/workspace/woodwork/components/llms/openai.py"
            )
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
        with patch("woodwork.components.environments.coding.Docker"):
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
        with patch("woodwork.components.environments.coding.Docker"):
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
