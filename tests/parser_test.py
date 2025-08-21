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
    
    planner = decomposer llm {
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


@pytest.mark.skip("Skipping...revisit test validity. Typically don't want to test environment variables in unit tests.")
def test_environment_values():
    config = """
    llm = llm openai {
        api_key: $OPENAI_API_KEY
    }
    """
    components = parse(config)
    load_dotenv(dotenv_path=os.path.join(os.getcwd(), ".env"))
    assert components["llm"]["config"]["api_key"] == os.getenv("OPENAI_API_KEY")


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
