import pytest

from woodwork.components.input_interface import input_interface
from woodwork.helper_functions import import_all_classes
import_all_classes('woodwork.components')

def get_all_subclasses(cls):
    subclasses = cls.__subclasses__()
    for subclass in subclasses:
        subclasses.extend(get_all_subclasses(subclass))
    return subclasses

input_implementors = get_all_subclasses(input_interface)
print("Collected subclasses of input_interface:", input_implementors)

@pytest.mark.parametrize("input_implementor", input_implementors)
def test_input_returns(input_implementor):
    input_instance = input_implementor()
    
    try:
        result = input_instance.input("Some input")
        assert isinstance(result, str)
    except:
        assert False