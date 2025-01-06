from woodwork.helper_functions import import_all_classes
from woodwork.dependencies import init_all, activate_virtual_environment


def test_venv_setup():
    try:
        init_all({"isolated": True})
        assert True
    except:
        assert False


def test_all_requirements_present():
    activate_virtual_environment()
    if import_all_classes("woodwork.components"):
        assert True
    else:
        assert False
