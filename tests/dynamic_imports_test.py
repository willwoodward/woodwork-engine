import pytest
from woodwork.utils.helper_functions import import_all_classes
from woodwork.parser.dependencies import init, activate_virtual_environment


def test_venv_setup():
    try:
        init({"isolated": True, "all": True})
        assert True
    except:
        assert False


@pytest.mark.skip("Skipping...revisit test validity.")
def test_all_requirements_present():
    activate_virtual_environment()
    if import_all_classes("woodwork.components"):
        assert True
    else:
        assert False
