from woodwork.helper_functions import import_all_classes

def test_all_requirements_present():
    assert import_all_classes('woodwork.components') == True