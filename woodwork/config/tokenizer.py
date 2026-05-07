"""Tokenizer for .ww configuration files.

Handles extracting declarations, parsing component declarations, and parsing config values.
"""

import os
import re
import logging

from typing import Any

log = logging.getLogger(__name__)


def get_declarations(file: str) -> list[str]:
    """Given a file, returns an array of strings containing the component declarations."""

    entry_pattern = r".+=.+\{"
    matches = []

    for match in re.finditer(entry_pattern, file):
        start_pos = match.start()
        stack = 1
        end_pos = match.end()

        # Use a stack to find the closing brace
        for i in range(end_pos, len(file)):
            char = file[i]
            if char == "{":
                stack += 1
            elif char == "}":
                stack -= 1
                if stack == 0:
                    end_pos = i + 1
                    break

        # Determine the starting line number
        line_number = file[:start_pos].count("\n") + 1

        # Add the full declaration text to the matches
        matches.append((file[start_pos:end_pos], line_number))

    return matches


def extract_nested_dict(key: str, text: str) -> str:
    # Match {key} followed by optional whitespace and a colon
    pattern = re.escape(key) + r"\s*:\s*\{"
    match = re.search(pattern, text)
    if not match:
        return ""

    # Start parsing from where the dictionary begins
    start_pos = match.end()  # Position after the colon and whitespace
    stack = []
    dict_start = -1

    for i in range(start_pos - 1, len(text)):
        char = text[i]
        if char == "{":
            if not stack:
                dict_start = i
            stack.append("{")
        elif char == "}":
            stack.pop()
            if not stack:  # Found the matching closing brace
                return text[dict_start : i + 1].strip()

    return ""  # Return empty string if no complete dictionary is found


def parse_component_declaration(entry: str) -> tuple[str, str, str]:
    """Parse a component declaration into variable, component, and type.

    Args:
        entry: Component declaration string (e.g., "model = llm openai { ... }")

    Returns:
        Tuple of (variable_name, component_type, specific_type)
        Example: ("model", "llm", "openai")
    """
    # Match: variable = component type {
    pattern = r"^\s*(\w+)\s*=\s*(\w+)\s+(\w+)\s*\{"
    match = re.match(pattern, entry)

    if not match:
        raise ValueError(f"Invalid component declaration format: {entry[:50]}...")

    variable, component, type_name = match.groups()
    return variable, component, type_name


def parse_config(entry: str) -> tuple[dict[Any, Any], list[Any] | Any]:
    config_items = list(
        map(
            lambda x: x.replace("\n", "").strip(),
            re.findall(r"\n[^\n]+", entry),
        ),
    )
    config_items = [x for x in config_items if x != ""]

    # Handle multiline arrays by joining them
    merged_items = []
    i = 0
    while i < len(config_items):
        item = config_items[i]

        # Check if this line starts an array
        if ":" in item and "[" in item and "]" not in item:
            # This is a multiline array - collect all lines until we find the closing ]
            array_lines = [item]
            i += 1
            while i < len(config_items) and "]" not in config_items[i]:
                array_lines.append(config_items[i])
                i += 1
            # Add the closing line
            if i < len(config_items):
                array_lines.append(config_items[i])

            # Join all array lines into one
            key_part = array_lines[0].split(":", 1)[0] + ":"
            array_content = " ".join([line.split(":", 1)[1] if ":" in line else line for line in array_lines])
            merged_items.append(key_part + " " + array_content.strip())
        else:
            merged_items.append(item)
        i += 1

    config_items = merged_items

    # If the value is a {, delete the nested elements (will be parsed later)
    # BUT preserve dictionary content that's inside arrays (for hooks/pipes)
    i = 0
    brace_counter = 0
    deletion_mode = False
    while i < len(config_items):
        if "}" in config_items[i]:
            # Check if this closing brace is part of an array
            line = config_items[i]
            # If the line contains both ] and }, it's likely ending an array with dict content
            if "]" in line and "}" in line:
                # Keep this line, it's array content
                i += 1
                brace_counter -= 1
                if brace_counter == 0:
                    deletion_mode = False
            else:
                config_items.pop(i)
                brace_counter -= 1
                if brace_counter == 0:
                    deletion_mode = False
        elif deletion_mode:
            # Check if this line is part of an array structure
            line = config_items[i]
            # If it contains array-like content or is indented (suggesting it's array content), keep it
            if (
                "[" in line
                or "]" in line
                or line.startswith("    ")
                or line.startswith("\t")
                or any(key in line for key in ["event:", "script_path:", "function_name:"])
            ):
                # This looks like array content, keep it
                i += 1
            else:
                if "{" in config_items[i]:
                    brace_counter += 1
                config_items.pop(i)
        elif "{" in config_items[i]:
            # Check if this { is part of an array
            line = config_items[i]
            if "[" in line:  # This looks like an array with dict content
                # Don't enter deletion mode, just continue
                i += 1
            else:
                brace_counter += 1
                deletion_mode = True
                i += 1
        else:
            i += 1

    config = {}
    # Make to a set
    depends_on = []
    for item in config_items:
        # Skip empty lines or lines without colons
        if not item.strip() or ":" not in item:
            continue

        parts = item.split(":", 1)
        if len(parts) < 2:
            continue

        key = parts[0].strip()
        value = parts[1].strip()

        # Dealing with nested dictionaries:
        if value[0] == "{":
            # Find inside the string
            value, nested_deps = parse_config(extract_nested_dict(key, entry))
            depends_on += nested_deps

        # If the value starts with $, then it is a secret key in the .env file
        # Replace this with the secret
        elif value[0] == "$":
            value = os.getenv(value[1::])

        # If the value is an array, parse it as an array of references
        elif value[0] == "[":
            array_content = value[1:-1]  # Remove [ and ]
            array_items = []

            # Parse array items that can be strings, dictionaries, or simple references
            current_item = ""
            in_quotes = False
            quote_char = None
            brace_count = 0

            i = 0
            while i < len(array_content):
                char = array_content[i]

                if not in_quotes and char in ['"', "'"]:
                    in_quotes = True
                    quote_char = char
                    current_item += char
                elif in_quotes and char == quote_char:
                    in_quotes = False
                    current_item += char
                    quote_char = None
                elif not in_quotes and char == "{":
                    brace_count += 1
                    current_item += char
                elif not in_quotes and char == "}":
                    brace_count -= 1
                    current_item += char
                elif not in_quotes and char == "," and brace_count == 0:
                    # End of current item
                    cleaned_item = current_item.strip()
                    if cleaned_item:
                        # Check if it's a dictionary-like structure
                        if cleaned_item.startswith("{") and cleaned_item.endswith("}"):
                            # Parse as dictionary
                            dict_content = cleaned_item[1:-1].strip()  # Remove { and }
                            parsed_dict = {}

                            # Split by lines and parse key-value pairs
                            dict_lines = [line.strip() for line in dict_content.split("\n") if line.strip()]
                            for line in dict_lines:
                                if ":" in line:
                                    line_key, line_value = line.split(":", 1)
                                    line_key = line_key.strip().strip("\"'")
                                    line_value = line_value.strip().strip("\"'")

                                    # Map common keys for hooks and pipes
                                    if line_key in ["event", "script_path", "function_name"]:
                                        parsed_dict[line_key] = line_value
                                else:
                                    # Handle lines without colons (might be values from multiline parsing)
                                    # Try to extract quoted strings as values
                                    if '"' in line or "'" in line:
                                        parts = re.findall(r'["\']([^"\']*)["\']', line)
                                        if len(parts) == 3:  # event, script_path, function_name
                                            parsed_dict["event"] = parts[0]
                                            parsed_dict["script_path"] = parts[1]
                                            parsed_dict["function_name"] = parts[2]

                            array_items.append(parsed_dict)
                        else:
                            # Remove outer quotes if present
                            if (cleaned_item.startswith('"') and cleaned_item.endswith('"')) or (
                                cleaned_item.startswith("'") and cleaned_item.endswith("'")
                            ):
                                cleaned_item = cleaned_item[1:-1]
                            else:
                                # Unquoted, non-dict item: treat as variable reference
                                # (skip booleans and numbers)
                                if cleaned_item.lower() not in ("true", "false"):
                                    try:
                                        float(cleaned_item)
                                    except ValueError:
                                        depends_on.append(cleaned_item)
                            array_items.append(cleaned_item)
                    current_item = ""
                else:
                    current_item += char
                i += 1

            # Don't forget the last item
            if current_item.strip():
                cleaned_item = current_item.strip()
                if cleaned_item.startswith("{") and cleaned_item.endswith("}"):
                    # Parse as dictionary
                    dict_content = cleaned_item[1:-1].strip()
                    parsed_dict = {}

                    # Handle the case where we have space-separated quoted strings
                    if '"' in dict_content or "'" in dict_content:
                        parts = re.findall(r'["\']([^"\']*)["\']', dict_content)
                        if len(parts) == 3:  # event, script_path, function_name
                            parsed_dict["event"] = parts[0]
                            parsed_dict["script_path"] = parts[1]
                            parsed_dict["function_name"] = parts[2]

                    array_items.append(parsed_dict)
                else:
                    if (cleaned_item.startswith('"') and cleaned_item.endswith('"')) or (
                        cleaned_item.startswith("'") and cleaned_item.endswith("'")
                    ):
                        cleaned_item = cleaned_item[1:-1]
                    else:
                        # Unquoted, non-dict item: treat as variable reference
                        if cleaned_item.lower() not in ("true", "false"):
                            try:
                                float(cleaned_item)
                            except ValueError:
                                depends_on.append(cleaned_item)
                    array_items.append(cleaned_item)

            value = array_items

        elif (value[0] == '"' and value[-1] == '"') or (value[0] == "'" and value[-1] == "'"):
            value = value[1:-1:]

        # If the value is not a string, it references a variable
        # We replace this variable with a reference to the object
        # Could be a boolean
        elif value.lower() == "true":
            value = True
        elif value.lower() == "false":
            value = False

        else:
            # Check if it's a numeric value
            try:
                # Try to convert to int or float
                if "." in value:
                    value = float(value)
                else:
                    value = int(value)
            except (ValueError, AttributeError):
                # Not a number, treat as variable dependency
                depends_on.append(value)

        config[key] = value

    return config, depends_on
