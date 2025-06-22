from woodwork.registry import get_registry
from woodwork.config_parser import main_function

main_function()
registry = get_registry()

model = registry.get("llm")
