from woodwork.config_parser import parse

# Testing component name declaration
def test_same_name_as_keyword():
    raise NotImplementedError

def test_same_name_as_other_variable():
    raise NotImplementedError

def test_double_equals():
    raise NotImplementedError

# Testing keyword parsing
def test_keywords_parsed():
    raise NotImplementedError

# Testing component properties
def test_properties():
    raise NotImplementedError

# Testing component values
def test_string_values():
    config = """
    name1 = keyword1 keyword2 {
        key1: "value1"
    }
    """
    
    components = parse(config)
    assert components["name1"]["config"] == {"key1": "value1"}

def test_variable_values():
    raise NotImplementedError

def test_list_values():
    raise NotImplementedError

def test_list_variable_values():
    raise NotImplementedError

def test_dictionary_values():
    raise NotImplementedError

def test_environment_values():
    raise NotImplementedError

def test_boolean_values():
    raise NotImplementedError