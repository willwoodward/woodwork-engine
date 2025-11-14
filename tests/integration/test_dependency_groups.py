"""Integration tests for pyproject.toml dependency groups.

These tests verify that the dependency groups ([test], [dev], [all]) are properly
configured and include all necessary dependencies for their intended purpose.
"""

import subprocess
import sys
import tempfile
from pathlib import Path
import pytest

pytestmark = pytest.mark.slow


class TestDependencyGroups:
    """Test that dependency groups are properly configured."""

    @pytest.fixture
    def temp_venv(self):
        """Create a temporary virtual environment for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            venv_path = Path(tmpdir) / "test_venv"

            # Create venv
            subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True, capture_output=True)

            # Get python and pip paths
            if sys.platform == "win32":
                python_path = venv_path / "Scripts" / "python.exe"
                pip_path = venv_path / "Scripts" / "pip.exe"
            else:
                python_path = venv_path / "bin" / "python"
                pip_path = venv_path / "bin" / "pip"

            yield {"venv_path": venv_path, "python": str(python_path), "pip": str(pip_path)}

    def test_test_group_installs_pytest(self, temp_venv):
        """Test that [test] group installs pytest and pytest-asyncio."""
        # Install with [test] extra
        result = subprocess.run(
            [temp_venv["pip"], "install", "-e", ".[test]"],
            cwd=Path(__file__).parent.parent.parent,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Installation failed: {result.stderr}"

        # Verify pytest is installed
        result = subprocess.run([temp_venv["python"], "-m", "pytest", "--version"], capture_output=True, text=True)
        assert result.returncode == 0, "pytest not installed"
        assert "pytest" in result.stdout

        # Verify pytest-asyncio is available
        result = subprocess.run([temp_venv["python"], "-c", "import pytest_asyncio"], capture_output=True, text=True)
        assert result.returncode == 0, "pytest-asyncio not installed"

    def test_test_group_can_run_tests(self, temp_venv):
        """Test that [test] group can run basic unit tests."""
        # Install with [test] extra
        subprocess.run(
            [temp_venv["pip"], "install", "-e", ".[test]"],
            cwd=Path(__file__).parent.parent.parent,
            check=True,
            capture_output=True,
        )

        # Try to run a simple test
        test_path = Path(__file__).parent.parent / "unit" / "components" / "environments" / "test_coding_search.py"
        if test_path.exists():
            result = subprocess.run(
                [temp_venv["python"], "-m", "pytest", str(test_path), "-v"],
                cwd=Path(__file__).parent.parent.parent,
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0, f"Tests failed: {result.stdout}\n{result.stderr}"

    def test_dev_group_includes_test_dependencies(self, temp_venv):
        """Test that [dev] group includes [test] dependencies."""
        # Install with [dev] extra
        result = subprocess.run(
            [temp_venv["pip"], "install", "-e", ".[dev]"],
            cwd=Path(__file__).parent.parent.parent,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Installation failed: {result.stderr}"

        # Verify pytest is included
        result = subprocess.run([temp_venv["python"], "-m", "pytest", "--version"], capture_output=True, text=True)
        assert result.returncode == 0, "pytest not installed with [dev]"

    def test_dev_group_installs_dev_tools(self, temp_venv):
        """Test that [dev] group installs ruff, black, ty."""
        # Install with [dev] extra
        subprocess.run(
            [temp_venv["pip"], "install", "-e", ".[dev]"],
            cwd=Path(__file__).parent.parent.parent,
            check=True,
            capture_output=True,
        )

        # Check ruff
        result = subprocess.run([temp_venv["python"], "-m", "ruff", "--version"], capture_output=True, text=True)
        assert result.returncode == 0, "ruff not installed"

        # Check black
        result = subprocess.run([temp_venv["python"], "-m", "black", "--version"], capture_output=True, text=True)
        assert result.returncode == 0, "black not installed"

        # Check ty
        result = subprocess.run([temp_venv["python"], "-c", "import ty"], capture_output=True, text=True)
        assert result.returncode == 0, "ty not installed"

    def test_all_group_includes_dev_dependencies(self, temp_venv):
        """Test that [all] group includes [dev] and [test] dependencies."""
        # Install with [all] extra
        result = subprocess.run(
            [temp_venv["pip"], "install", "-e", ".[all]"],
            cwd=Path(__file__).parent.parent.parent,
            capture_output=True,
            text=True,
            timeout=300,  # chromadb can take a while
        )

        assert result.returncode == 0, f"Installation failed: {result.stderr}"

        # Verify pytest is included
        result = subprocess.run([temp_venv["python"], "-m", "pytest", "--version"], capture_output=True, text=True)
        assert result.returncode == 0, "pytest not installed with [all]"

        # Verify ruff is included
        result = subprocess.run([temp_venv["python"], "-m", "ruff", "--version"], capture_output=True, text=True)
        assert result.returncode == 0, "ruff not installed with [all]"

    @pytest.mark.slow
    def test_all_group_installs_optional_features(self, temp_venv):
        """Test that [all] group installs optional features like chromadb, langchain."""
        # Install with [all] extra
        subprocess.run(
            [temp_venv["pip"], "install", "-e", ".[all]"],
            cwd=Path(__file__).parent.parent.parent,
            check=True,
            capture_output=True,
            timeout=300,
        )

        # Check chromadb
        result = subprocess.run([temp_venv["python"], "-c", "import chromadb"], capture_output=True, text=True)
        assert result.returncode == 0, "chromadb not installed"

        # Check langchain
        result = subprocess.run([temp_venv["python"], "-c", "import langchain"], capture_output=True, text=True)
        assert result.returncode == 0, "langchain not installed"

        # Check docker
        result = subprocess.run([temp_venv["python"], "-c", "import docker"], capture_output=True, text=True)
        assert result.returncode == 0, "docker not installed"


class TestPyprojectTomlStructure:
    """Test the structure of pyproject.toml dependency groups."""

    def test_pyproject_has_all_dependency_groups(self):
        """Test that pyproject.toml defines all expected dependency groups."""
        import tomli

        pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            pyproject = tomli.load(f)

        optional_deps = pyproject["project"]["optional-dependencies"]

        # Check all groups exist
        assert "test" in optional_deps, "Missing [test] dependency group"
        assert "dev" in optional_deps, "Missing [dev] dependency group"
        assert "all" in optional_deps, "Missing [all] dependency group"

    def test_test_group_has_pytest(self):
        """Test that [test] group includes pytest packages."""
        import tomli

        pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            pyproject = tomli.load(f)

        test_deps = pyproject["project"]["optional-dependencies"]["test"]

        # Check for pytest dependencies
        pytest_found = any("pytest" in dep and "pytest-asyncio" not in dep for dep in test_deps)
        pytest_asyncio_found = any("pytest-asyncio" in dep for dep in test_deps)

        assert pytest_found, "pytest not in [test] dependencies"
        assert pytest_asyncio_found, "pytest-asyncio not in [test] dependencies"

    def test_dev_group_references_test(self):
        """Test that [dev] group references [test] group."""
        import tomli

        pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            pyproject = tomli.load(f)

        dev_deps = pyproject["project"]["optional-dependencies"]["dev"]

        # Check if [dev] references [test]
        test_ref_found = any("woodwork-engine[test]" in dep for dep in dev_deps)

        assert test_ref_found, "[dev] should reference woodwork-engine[test]"

    def test_all_group_references_dev(self):
        """Test that [all] group references [dev] group."""
        import tomli

        pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            pyproject = tomli.load(f)

        all_deps = pyproject["project"]["optional-dependencies"]["all"]

        # Check if [all] references [dev]
        dev_ref_found = any("woodwork-engine[dev]" in dep for dep in all_deps)

        assert dev_ref_found, "[all] should reference woodwork-engine[dev]"

    def test_pytest_asyncio_not_in_core_dependencies(self):
        """Test that pytest-asyncio is not in core dependencies."""
        import tomli

        pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            pyproject = tomli.load(f)

        core_deps = pyproject["project"]["dependencies"]

        # pytest-asyncio should NOT be in core dependencies
        pytest_asyncio_found = any("pytest-asyncio" in dep for dep in core_deps)

        assert not pytest_asyncio_found, "pytest-asyncio should not be in core dependencies"
