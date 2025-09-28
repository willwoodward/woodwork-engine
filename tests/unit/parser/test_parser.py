# from woodwork.dependencies import activate_virtual_environment
from woodwork.parser.config_parser import parse
from woodwork.utils.errors.errors import ForbiddenVariableNameError

import pytest
import os
from dotenv import load_dotenv


# activate_virtual_environment()


# Testing component name declaration
def test_parsing():
    config = """
    name1 = keyword1 keyword2 {
        key1: "value1"
    }
    """
    components = parse(config)
    print(components)
    assert "name1" in components
    assert components["name1"]["variable"] == "name1"
    assert components["name1"]["component"] == "keyword1"
    assert components["name1"]["type"] == "keyword2"
    assert components["name1"]["config"] == {"key1": "value1"}


def test_same_name_as_keyword():
    config = """
    keyword1 = keyword1 keyword2 {
        key1: "value1"
    }
    """
    components = parse(config)
    assert "keyword1" in components
    assert components["keyword1"]["variable"] == "keyword1"
    assert components["keyword1"]["component"] == "keyword1"
    assert components["keyword1"]["type"] == "keyword2"
    assert components["keyword1"]["config"] == {"key1": "value1"}


def test_name_not_boolean():
    config = """
    true = keyword1 keyword2 {
        key1: "value1"
    }
    """
    with pytest.raises(ForbiddenVariableNameError):
        parse(config)

    config = """
    FALSE = keyword1 keyword2 {
        key1: "value1"
    }
    """
    with pytest.raises(ForbiddenVariableNameError):
        parse(config)


def test_same_name_as_other_variable():
    config = """
    name1 = keyword1 keyword2 {
        key1: "value1"
    }
    
    name1 = keyword1 keyword2 {
        key1: "value1"
    }
    """

    with pytest.raises(ForbiddenVariableNameError):
        parse(config)


# Testing keyword parsing
def test_keywords_parsed():
    config = """
    name1 = keyword1 keyword2 {
        key1: "value1"
    }
    """
    components = parse(config)
    assert components["name1"]["component"] == "keyword1"
    assert components["name1"]["type"] == "keyword2"


# Testing config properties
def test_properties_parsed():
    config = """
    name1 = keyword1 keyword2 {
        key1: "value1"
        key2: "value2"
    }
    """
    components = parse(config)
    assert list(components["name1"]["config"].keys()) == ["key1", "key2"]


# Testing config values
def test_string_values():
    config = """
    name1 = keyword1 keyword2 {
        key1: "value1"
    }
    """
    components = parse(config)
    assert components["name1"]["config"] == {"key1": "value1"}


@pytest.mark.skip("Skipping...revisit test validity.")
def test_variable_values():
    from woodwork.components.llms.openai import openai

    config = """
    llm = llm openai {
        api_key: $OPENAI_API_KEY
    }
    
    name1 = keyword1 keyword2 {
        key1: llm
    }
    """
    components = parse(config)
    assert isinstance(components["name1"]["config"]["key1"], openai)


# def test_list_values():
#     config = """
#     name1 = keyword1 keyword2 {
#         key1: ["value1", "value2", "value3"]
#     }
#     """
#     components = parse(config)
#     assert components["name1"]["config"] == {"key1": ["value1", "value2", "value3"]}


@pytest.mark.skip("Skipping...revisit test validity.")
def test_list_variable_values():
    from woodwork.components.llms.openai import openai

    config = """
    llm1 = llm openai {
        api_key: $OPENAI_API_KEY
    }
    
    llm2 = llm openai {
        api_key: $OPENAI_API_KEY
    }
    
    planner = agent llm {
        api_key: $OPENAI_API_KEY
        tools: [llm1, llm2]
    }
    """
    components = parse(config)
    assert isinstance(components["planner"]["config"]["tools"][0], openai)
    assert isinstance(components["planner"]["config"]["tools"][1], openai)


def test_dictionary_values():
    config = """
    name1 = keyword1 keyword2 {
        key1: "value1"
        key2: {
            subkey1: "subvalue1"
            subkey2: "subvalue2"
        }
        key3: "value3"
    }
    """
    components = parse(config)
    assert components["name1"]["config"] == {
        "key1": "value1",
        "key2": {"subkey1": "subvalue1", "subkey2": "subvalue2"},
        "key3": "value3",
    }


def test_nested_dictionary_values():
    config = """
    name1 = keyword1 keyword2 {
        key1: "value1"
        key2: {
            subkey1: "subvalue1"
            subkey2: {
                subkey3: "subvalue3"
                subkey4: "subvalue4"
            }
            subkey5: "subvalue5"
        }
        key3: "value3"
    }
    """
    components = parse(config)
    assert components["name1"]["config"] == {
        "key1": "value1",
        "key2": {
            "subkey1": "subvalue1",
            "subkey2": {"subkey3": "subvalue3", "subkey4": "subvalue4"},
            "subkey5": "subvalue5",
        },
        "key3": "value3",
    }


def test_multiple_dictionary_values():
    config = """
    name1 = keyword1 keyword2 {
        key1: {
            subkey3: "subvalue3"
            subkey4: "subvalue4"
        }
        key2: {
            subkey1: "subvalue1"
            subkey2: "subvalue2"
        }
        key3: "value3"
    }
    """
    components = parse(config)
    assert components["name1"]["config"] == {
        "key1": {"subkey3": "subvalue3", "subkey4": "subvalue4"},
        "key2": {"subkey1": "subvalue1", "subkey2": "subvalue2"},
        "key3": "value3",
    }


def test_nested_special_values():
    config = """
    name1 = keyword1 keyword2 {
        key1: "value1"
        key2: {
            subkey1: true
            subkey2: "subvalue2"
        }
        key3: "value3"
    }
    """
    components = parse(config)
    assert components["name1"]["config"] == {
        "key1": "value1",
        "key2": {"subkey1": True, "subkey2": "subvalue2"},
        "key3": "value3",
    }


@pytest.mark.skip("Skipping...revisit test validity.")
def test_nested_variable_references():
    from woodwork.components.llms.openai import openai

    config = """
    llm = llm openai {
        api_key: $OPENAI_API_KEY
    }
    
    name1 = keyword1 keyword2 {
        key1: {
            subkey1: {
                subkey2: llm
            }
        }
    }
    """
    components = parse(config)
    assert isinstance(components["name1"]["config"]["key1"]["subkey1"]["subkey2"], openai)


def test_environment_values():
    """Test that simple environment variables are resolved correctly."""
    os.environ["TEST_API_KEY"] = "test_key_value"

    config = """
    llm = llm openai {
        api_key: $TEST_API_KEY
    }
    """

    try:
        components = parse(config)
        assert components["llm"]["config"]["api_key"] == "test_key_value"
    finally:
        del os.environ["TEST_API_KEY"]


def test_boolean_values():
    config = """
    name1 = keyword1 keyword2 {
        key1: true
    }
    """
    components = parse(config)
    assert components["name1"]["config"] == {"key1": True}

    # Testing with capitalised T
    config = """
    name1 = keyword1 keyword2 {
        key1: True
    }
    """
    components = parse(config)
    assert components["name1"]["config"] == {"key1": True}

    # Testing with all caps
    config = """
    name1 = keyword1 keyword2 {
        key1: TRUE
    }
    """
    components = parse(config)
    assert components["name1"]["config"] == {"key1": True}


def test_environment_variables_in_nested_dictionaries():
    """Test that environment variables are properly resolved in nested dictionaries."""
    # Set up test environment variables
    os.environ["TEST_TOKEN"] = "test_token_value"
    os.environ["TEST_NAME"] = "test_name_value"
    os.environ["TEST_EMAIL"] = "test@example.com"

    config = """
    test_component = mcp server {
        server: "test/server"
        version: "latest"
        env: {
            TOKEN: $TEST_TOKEN
            USERNAME: "hardcoded_user"
            DEBUG: true
        }
    }
    """

    try:
        components = parse(config)

        # Check that nested environment variables were resolved
        env_config = components["test_component"]["config"]["env"]
        assert env_config["TOKEN"] == "test_token_value"
        assert env_config["USERNAME"] == "hardcoded_user"  # Non-env var should remain
        assert env_config["DEBUG"] is True  # Boolean should remain

    finally:
        # Clean up test environment variables
        del os.environ["TEST_TOKEN"]
        del os.environ["TEST_NAME"]
        del os.environ["TEST_EMAIL"]


def test_environment_variables_in_deeply_nested_dictionaries():
    """Test environment variable resolution in deeply nested dictionary structures."""
    # Set up test environment variables
    os.environ["TEST_GIT_NAME"] = "Agent Smith"
    os.environ["TEST_GIT_EMAIL"] = "agent@matrix.com"
    os.environ["TEST_GITHUB_TOKEN"] = "ghp_test123"

    config = """
    dev_env = environment coding {
        repo_url: "test/repo"
        environment_variables: {
            GIT_AUTHOR_NAME: $TEST_GIT_NAME
            GIT_AUTHOR_EMAIL: $TEST_GIT_EMAIL
            GIT_COMMITTER_NAME: $TEST_GIT_NAME
            GIT_COMMITTER_EMAIL: $TEST_GIT_EMAIL
            GITHUB_TOKEN: $TEST_GITHUB_TOKEN
            PYTHON_ENV: "development"
            CONFIG: {
                nested_token: $TEST_GITHUB_TOKEN
                nested_name: $TEST_GIT_NAME
                static_value: "test"
            }
        }
    }
    """

    try:
        components = parse(config)

        # Check that deeply nested environment variables were resolved
        env_vars = components["dev_env"]["config"]["environment_variables"]
        assert env_vars["GIT_AUTHOR_NAME"] == "Agent Smith"
        assert env_vars["GIT_AUTHOR_EMAIL"] == "agent@matrix.com"
        assert env_vars["GIT_COMMITTER_NAME"] == "Agent Smith"
        assert env_vars["GIT_COMMITTER_EMAIL"] == "agent@matrix.com"
        assert env_vars["GITHUB_TOKEN"] == "ghp_test123"
        assert env_vars["PYTHON_ENV"] == "development"  # Non-env var should remain

        # Check deeply nested environment variables
        nested_config = env_vars["CONFIG"]
        assert nested_config["nested_token"] == "ghp_test123"
        assert nested_config["nested_name"] == "Agent Smith"
        assert nested_config["static_value"] == "test"

    finally:
        # Clean up test environment variables
        del os.environ["TEST_GIT_NAME"]
        del os.environ["TEST_GIT_EMAIL"]
        del os.environ["TEST_GITHUB_TOKEN"]


def test_environment_variables_mixed_with_other_types():
    """Test that environment variables work alongside other value types in nested dictionaries."""
    # Set up test environment variables
    os.environ["TEST_API_KEY"] = "secret_key_123"
    os.environ["TEST_PORT"] = "8080"

    config = """
    api_service = api web {
        name: "test_api"
        config: {
            authentication: {
                api_key: $TEST_API_KEY
                enabled: true
                timeout: 30
                methods: ["GET", "POST"]
            }
            server: {
                port: $TEST_PORT
                host: "localhost"
                debug: false
            }
        }
    }
    """

    try:
        components = parse(config)

        # Check mixed types in nested dictionaries
        config_dict = components["api_service"]["config"]["config"]

        auth = config_dict["authentication"]
        assert auth["api_key"] == "secret_key_123"  # Environment variable
        assert auth["enabled"] is True              # Boolean
        assert auth["timeout"] == 30               # Integer (as dependency)
        assert auth["methods"] == ["GET", "POST"]  # Array

        server = config_dict["server"]
        assert server["port"] == "8080"            # Environment variable (string)
        assert server["host"] == "localhost"       # String literal
        assert server["debug"] is False            # Boolean

    finally:
        # Clean up test environment variables
        del os.environ["TEST_API_KEY"]
        del os.environ["TEST_PORT"]


def test_missing_environment_variables_in_nested_dictionaries():
    """Test behavior when environment variables don't exist in nested dictionaries."""
    config = """
    test_component = api functions {
        settings: {
            missing_var: $NONEXISTENT_VAR
            another_setting: "valid_value"
        }
    }
    """

    components = parse(config)

    # Missing environment variables should result in None
    settings = components["test_component"]["config"]["settings"]
    assert settings["missing_var"] is None
    assert settings["another_setting"] == "valid_value"


def test_environment_variables_real_world_mcp_config():
    """Test environment variable parsing with realistic MCP server configuration."""
    os.environ["TEST_GITHUB_TOKEN"] = "ghp_real_token_123"
    os.environ["TEST_SERVER_VERSION"] = "v2.1.0"

    config = """
    github_mcp = mcp server {
        server: "github/mcp-server"
        version: $TEST_SERVER_VERSION
        toolsets: "repos,issues,prs"
        env: {
            GITHUB_TOKEN: $TEST_GITHUB_TOKEN
            API_VERSION: "2022-11-28"
            RATE_LIMIT: 5000
        }
    }
    """

    try:
        components = parse(config)

        mcp_config = components["github_mcp"]["config"]
        assert mcp_config["server"] == "github/mcp-server"
        assert mcp_config["version"] == "v2.1.0"  # From env var
        assert mcp_config["toolsets"] == "repos,issues,prs"

        env_config = mcp_config["env"]
        assert env_config["GITHUB_TOKEN"] == "ghp_real_token_123"  # From env var
        assert env_config["API_VERSION"] == "2022-11-28"          # String literal
        assert env_config["RATE_LIMIT"] == 5000                   # Integer (as dependency)

    finally:
        del os.environ["TEST_GITHUB_TOKEN"]
        del os.environ["TEST_SERVER_VERSION"]


def test_environment_variables_real_world_coding_environment():
    """Test environment variable parsing with realistic coding environment configuration."""
    os.environ["TEST_GIT_USER"] = "coding-agent"
    os.environ["TEST_GIT_EMAIL"] = "agent@example.com"
    os.environ["TEST_WORKSPACE_TOKEN"] = "workspace_secret_123"

    config = """
    dev_environment = environment coding {
        repo_url: "user/project"
        local_path: "/workspace"
        environment_variables: {
            GIT_AUTHOR_NAME: $TEST_GIT_USER
            GIT_AUTHOR_EMAIL: $TEST_GIT_EMAIL
            GIT_COMMITTER_NAME: $TEST_GIT_USER
            GIT_COMMITTER_EMAIL: $TEST_GIT_EMAIL
            WORKSPACE_TOKEN: $TEST_WORKSPACE_TOKEN
            NODE_ENV: "development"
            DEBUG: true
            PORT: 3000
        }
    }
    """

    try:
        components = parse(config)

        env_vars = components["dev_environment"]["config"]["environment_variables"]

        # Environment variables should be resolved
        assert env_vars["GIT_AUTHOR_NAME"] == "coding-agent"
        assert env_vars["GIT_AUTHOR_EMAIL"] == "agent@example.com"
        assert env_vars["GIT_COMMITTER_NAME"] == "coding-agent"
        assert env_vars["GIT_COMMITTER_EMAIL"] == "agent@example.com"
        assert env_vars["WORKSPACE_TOKEN"] == "workspace_secret_123"

        # Non-environment values should remain as-is
        assert env_vars["NODE_ENV"] == "development"
        assert env_vars["DEBUG"] is True
        assert env_vars["PORT"] == 3000  # Integer (as dependency)

    finally:
        del os.environ["TEST_GIT_USER"]
        del os.environ["TEST_GIT_EMAIL"]
        del os.environ["TEST_WORKSPACE_TOKEN"]


def test_environment_variables_empty_values():
    """Test that empty environment variables are handled correctly."""
    os.environ["TEST_EMPTY_VAR"] = ""
    os.environ["TEST_WHITESPACE_VAR"] = "   "

    config = """
    test_component = api web {
        settings: {
            empty_value: $TEST_EMPTY_VAR
            whitespace_value: $TEST_WHITESPACE_VAR
            normal_value: "normal"
        }
    }
    """

    try:
        components = parse(config)

        settings = components["test_component"]["config"]["settings"]
        assert settings["empty_value"] == ""
        assert settings["whitespace_value"] == "   "
        assert settings["normal_value"] == "normal"

    finally:
        del os.environ["TEST_EMPTY_VAR"]
        del os.environ["TEST_WHITESPACE_VAR"]
