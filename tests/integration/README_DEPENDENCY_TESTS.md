# Dependency Group Integration Tests

This directory contains integration tests for verifying that the dependency groups in `pyproject.toml` ([test], [dev], [all]) are properly configured.

## Purpose

These tests ensure that:
1. Each dependency group includes the required packages
2. The hierarchical structure works (dev includes test, all includes dev)
3. Users can run tests with minimal dependencies
4. Developers get all necessary tools
5. Optional features install correctly

## Test Categories

### Structure Tests (Fast)
These tests parse `pyproject.toml` and verify the structure without installing anything:
- `test_pyproject_has_all_dependency_groups` - Checks all groups exist
- `test_test_group_has_pytest` - Verifies pytest is in [test]
- `test_dev_group_references_test` - Checks [dev] includes [test]
- `test_all_group_references_dev` - Checks [all] includes [dev]
- `test_pytest_asyncio_not_in_core_dependencies` - Ensures optional deps aren't in core

Run with: `pytest tests/integration/test_dependency_groups.py::TestPyprojectTomlStructure -v`

### Installation Tests (Slow)
These tests create temporary virtual environments and actually install packages:
- `test_test_group_installs_pytest` - Verifies pytest installs with [test]
- `test_test_group_can_run_tests` - Checks tests can actually run
- `test_dev_group_includes_test_dependencies` - Verifies [dev] gets pytest
- `test_dev_group_installs_dev_tools` - Checks ruff, black, ty install
- `test_all_group_includes_dev_dependencies` - Verifies [all] gets everything
- `test_all_group_installs_optional_features` - Checks chromadb, langchain, etc.

Run with: `pytest tests/integration/test_dependency_groups.py::TestDependencyGroups -v`

Skip slow tests: `pytest tests/integration/test_dependency_groups.py -m "not slow" -v`

## When to Run

### Always (CI/CD)
Run structure tests before every commit - they're fast and catch configuration errors early:
```bash
pytest tests/integration/test_dependency_groups.py::TestPyprojectTomlStructure
```

### Before Releases
Run all installation tests to ensure dependency groups work correctly:
```bash
pytest tests/integration/test_dependency_groups.py
```

### After Modifying pyproject.toml
Run all tests if you:
- Add/remove dependencies
- Change dependency versions
- Modify the dependency group structure
- Add new optional features

## Common Failures

**"pytest not in [test] dependencies"**
- You removed pytest from the [test] group
- Fix: Add `"pytest>=8.3.5"` back to [test]

**"[dev] should reference woodwork-engine[test]"**
- The hierarchical structure is broken
- Fix: Ensure [dev] includes `"woodwork-engine[test]"`

**"pytest-asyncio should not be in core dependencies"**
- pytest-asyncio was added to runtime dependencies
- Fix: Move it to [test] group only

**"chromadb not installed"**
- Optional dependency missing from [all]
- Fix: Add chromadb back to [all] group

## Adding New Dependencies

When adding dependencies, follow this guide:

### Runtime Dependencies
Add to `dependencies` in pyproject.toml:
```toml
dependencies = [
    "new-package>=1.0.0",
]
```

### Test Dependencies
Add to `[test]` group:
```toml
[project.optional-dependencies]
test = [
    "pytest>=8.3.5",
    "pytest-asyncio>=0.24.0",
    "new-test-package>=1.0.0",
]
```

### Dev Tools
Add to `[dev]` group:
```toml
dev = [
    "woodwork-engine[test]",
    "ruff>=0.11.12",
    "new-dev-tool>=1.0.0",
]
```

### Optional Features
Add to `[all]` group:
```toml
all = [
    "woodwork-engine[dev]",
    "chromadb>=1.0.12",
    "new-optional-feature>=1.0.0",
]
```

After adding dependencies, run the tests to ensure the structure is still correct.
