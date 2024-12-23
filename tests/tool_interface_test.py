import pytest
import os
from dotenv import load_dotenv

from woodwork.interfaces.tool_interface import tool_interface
from woodwork.helper_functions import import_all_classes

import_all_classes("woodwork.components")
load_dotenv()


def get_all_subclasses(cls):
    subclasses = cls.__subclasses__()
    for subclass in subclasses:
        subclasses.extend(get_all_subclasses(subclass))
    return subclasses


def get_leaf_subclasses(cls):
    # Get direct subclasses of the provided class
    subclasses = cls.__subclasses__()
    leaf_subclasses = []

    for subclass in subclasses:
        # Recursively find leaf subclasses
        leaves = get_leaf_subclasses(subclass)
        # If the subclass has no further subclasses, it’s a leaf node
        if not leaves:
            leaf_subclasses.append(subclass)
        else:
            leaf_subclasses.extend(leaves)

    return leaf_subclasses


# Factory function to initialise classes with default inputs
def create_instance(cls):
    # class_name: parameters
    default_config = {
        "openai": {
            "name": "openai_example",
            "api_key": os.getenv("OPENAI_API_KEY"),
        },
        "hugging_face": {
            "name": "hugging_face-example",
            "api_key": os.getenv("HF_API_TOKEN"),
        },
    }

    if cls.__name__ in default_config.keys():
        return cls(**default_config[cls.__name__])
    return cls()


input_implementors = get_leaf_subclasses(tool_interface)
print("Collected subclasses of tool_interface:", input_implementors)


@pytest.mark.parametrize("input_implementor", input_implementors)
def test_input_returns(input_implementor):
    input_instance = create_instance(input_implementor)

    try:
        # Pass in a dummy action and inputs dictionary.
        # Should return a str response, or None if it is invalid
        result = input_instance.input("action", {})
        assert isinstance(result, str) or isinstance(result, None)
    except:
        assert False
