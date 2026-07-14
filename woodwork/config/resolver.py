"""Dependency resolution for parsed component declarations.

Handles resolving component dependencies via DFS traversal and validation.
"""

import logging

log = logging.getLogger(__name__)


def resolve_dict(dictionary, dependency, component_object):
    """Recursively resolve a dependency reference within a dictionary."""
    for key, value in dictionary.items():
        if value == dependency:
            dictionary[key] = component_object
        elif isinstance(value, dict):
            resolve_dict(value, dependency, component_object)


def dependency_resolver(commands, component):
    """Resolve component dependencies using DFS traversal.

    Each component has a 'depends_on' array listing variable names it references.
    This function recursively resolves those dependencies, creating objects as needed.
    """
    from woodwork.config.factory import create_object

    log.debug(component)

    # Base case: no dependencies
    if component["depends_on"] == []:
        if "object" not in component:
            import time

            component_name = component.get("variable", "unknown")
            log.debug(f"Creating component: {component_name}")
            start = time.time()
            component["object"] = create_object(component)
            elapsed = time.time() - start
            if elapsed > 1.0:
                log.warning(f"Component {component_name} took {elapsed:.1f}s to initialize")
        return component["object"]

    # Resolve each dependency
    for dependency in component["depends_on"]:
        if not dependency or dependency.strip() == "":
            continue

        if dependency not in commands:
            raise ValueError(
                f"Dependency '{dependency}' not found for component '{component.get('variable', 'unknown')}'"
            )

        component_object = dependency_resolver(commands, commands[dependency])

        for key, value in component["config"].items():
            if isinstance(value, list):
                for i in range(len(value)):
                    if value[i] == dependency:
                        value[i] = component_object

            if isinstance(value, dict):
                resolve_dict(value, dependency, component_object)

            if value == dependency:
                log.debug("Value: %s; Dependency: %s", value, dependency)
                component["config"][key] = component_object

    # All dependencies resolved - create the object
    component["depends_on"] = []
    component["object"] = create_object(component)
    return component["object"]


def command_checker(commands):
    """Validate parsed commands for conflicts (e.g., multiple command_line inputs)."""
    terminals_remaining = 1

    for _, command in commands.items():
        if command["component"] == "input" and command["type"] == "command_line":
            if terminals_remaining == 1:
                terminals_remaining = 0
            else:
                raise ValueError("Only one command_line input can be initialised.")
