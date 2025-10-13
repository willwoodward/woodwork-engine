"""
Workflow Variable Extraction Feature

Automatically extracts variables from prompts to make workflows reusable.
Converts "read emails from Bob" to "read emails from {name}" with variables.

Uses LLM-based extraction when available, falls back to regex patterns.
"""

import re
import json
import logging
from typing import Dict, Any, List, Tuple, Optional

log = logging.getLogger(__name__)


def extract_variables_with_llm(prompt: str, llm) -> Tuple[str, Dict[str, Any], Dict[str, str]]:
    """
    Extract variables from a prompt using an LLM.

    Returns:
        (parameterized_prompt, variables, schema)
    """
    try:
        extraction_prompt = f"""Extract variables from this user prompt to make it reusable as a template.

User prompt: "{prompt}"

Identify specific values that could be replaced with variables:
- Person names (Bob, Alice, etc.) -> {{name}}
- Numbers with context (5 days, 10 emails) -> {{days}}, {{count}}, etc.
- Quoted strings ("search query") -> {{query}}
- Dates, times, or other specific values

Return a JSON object with:
{{
  "parameterized": "the prompt with {{variables}} instead of specific values",
  "variables": {{"variable_name": "extracted_value"}},
  "schema": {{"variable_name": "string|number"}}
}}

Example:
Input: "read all emails from Bob sent in the last 5 days"
Output:
{{
  "parameterized": "read all emails from {{name}} sent in the last {{days}} days",
  "variables": {{"name": "Bob", "days": "5"}},
  "schema": {{"name": "string", "days": "number"}}
}}

IMPORTANT: Return ONLY the JSON object, no other text."""

        # Call the LLM
        response = llm.invoke(extraction_prompt)

        # Extract content from response
        if hasattr(response, 'content'):
            response_text = response.content
        else:
            response_text = str(response)

        # Clean up response - remove markdown code blocks if present
        response_text = response_text.strip()
        if response_text.startswith('```json'):
            response_text = response_text[7:]
        if response_text.startswith('```'):
            response_text = response_text[3:]
        if response_text.endswith('```'):
            response_text = response_text[:-3]
        response_text = response_text.strip()

        # Parse JSON response
        result = json.loads(response_text)

        parameterized = result.get('parameterized', prompt)
        variables = result.get('variables', {})
        schema = result.get('schema', {})

        log.info(f"[LLM Variable Extraction] Extracted {len(variables)} variables")
        log.debug(f"[LLM Variable Extraction] Parameterized: {parameterized}")
        log.debug(f"[LLM Variable Extraction] Variables: {variables}")

        return parameterized, variables, schema

    except Exception as e:
        log.warning(f"[LLM Variable Extraction] Failed: {e}, falling back to regex")
        return extract_variables_from_prompt_regex(prompt)


def extract_variables_from_prompt_regex(prompt: str) -> Tuple[str, Dict[str, Any], Dict[str, str]]:
    """
    Fallback regex-based extraction (only used if LLM fails).
    Returns empty if no variables found to avoid false positives.
    """
    """
    Extract variables from a prompt using pattern matching.

    Returns:
        (parameterized_prompt, variables, schema)

    Example:
        Input: "read all emails from Bob sent in the last 5 days"
        Output: (
            "read all emails from {name} sent in the last {days} days",
            {"name": "Bob", "days": "5"},
            {"name": "string", "days": "number"}
        )
    """
    variables = {}
    schema = {}
    parameterized = prompt

    # Pattern 1: Possessive names: "Bob's", "Alice's" -> {name}'s
    possessive_pattern = r'\b([A-Z][a-z]+)\'s\b'
    matches = re.finditer(possessive_pattern, prompt)
    for match in matches:
        name = match.group(1)

        # Skip common words that look like names
        if name.lower() not in ['the', 'this', 'that', 'these', 'those', 'a', 'an']:
            var_name = 'name' if 'name' not in variables else f'name_{len([k for k in variables if k.startswith("name")])+1}'
            variables[var_name] = name
            schema[var_name] = 'string'
            parameterized = parameterized.replace(f"{name}'s", f"{{{var_name}}}'s", 1)

    # Pattern 2: "from/to [Proper Name]" -> {name}
    name_pattern = r'\b(from|to|for|by|about)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b'
    matches = re.finditer(name_pattern, prompt)
    for match in matches:
        preposition = match.group(1)
        name = match.group(2)

        # Skip if already extracted as possessive
        if name in variables.values():
            continue

        # Skip common words that look like names
        if name.lower() not in ['the', 'this', 'that', 'these', 'those', 'a', 'an']:
            var_name = 'name' if 'name' not in variables else f'name_{len([k for k in variables if k.startswith("name")])+1}'
            variables[var_name] = name
            schema[var_name] = 'string'
            parameterized = parameterized.replace(f'{preposition} {name}', f'{preposition} {{{var_name}}}', 1)

    # Pattern 2: Numbers with units -> {count}, {days}, etc.
    number_pattern = r'\b(last|next|in|within|over)\s+(\d+)\s+(days?|weeks?|months?|years?|hours?|minutes?|items?|emails?|messages?)\b'
    matches = re.finditer(number_pattern, prompt)
    for match in matches:
        preposition = match.group(1)
        number = match.group(2)
        unit = match.group(3)

        # Determine variable name from unit
        if 'day' in unit:
            var_name = 'days'
        elif 'week' in unit:
            var_name = 'weeks'
        elif 'month' in unit:
            var_name = 'months'
        elif 'year' in unit:
            var_name = 'years'
        elif 'hour' in unit:
            var_name = 'hours'
        elif 'minute' in unit:
            var_name = 'minutes'
        elif 'email' in unit or 'message' in unit:
            var_name = 'count'
        elif 'item' in unit:
            var_name = 'count'
        else:
            var_name = 'number'

        # Handle duplicates
        if var_name in variables:
            var_name = f'{var_name}_{len([k for k in variables if k.startswith(var_name)])+1}'

        variables[var_name] = number
        schema[var_name] = 'number'
        parameterized = parameterized.replace(f'{preposition} {number} {unit}', f'{preposition} {{{var_name}}} {unit}', 1)

    # Pattern 3: Standalone numbers (less aggressive)
    standalone_number_pattern = r'\b(\d+)\s+(emails?|messages?|items?|files?|documents?)\b'
    matches = re.finditer(standalone_number_pattern, prompt)
    for match in matches:
        number = match.group(1)
        unit = match.group(2)

        var_name = 'count'
        if var_name in variables:
            var_name = f'count_{len([k for k in variables if k.startswith("count")])+1}'

        variables[var_name] = number
        schema[var_name] = 'number'
        parameterized = parameterized.replace(f'{number} {unit}', f'{{{var_name}}} {unit}', 1)

    # Pattern 4: Quoted strings -> {query}, {text}
    quoted_pattern = r'"([^"]+)"'
    matches = re.finditer(quoted_pattern, prompt)
    for i, match in enumerate(matches):
        quoted_text = match.group(1)
        var_name = f'query_{i+1}' if i > 0 else 'query'

        variables[var_name] = quoted_text
        schema[var_name] = 'string'
        parameterized = parameterized.replace(f'"{quoted_text}"', f'{{{var_name}}}', 1)

    log.debug(f"[Variable Extraction] Original: {prompt}")
    log.debug(f"[Variable Extraction] Parameterized: {parameterized}")
    log.debug(f"[Variable Extraction] Variables: {variables}")
    log.debug(f"[Variable Extraction] Schema: {schema}")

    return parameterized, variables, schema


def extract_variables_from_prompt(prompt: str, llm=None) -> Tuple[str, Dict[str, Any], Dict[str, str]]:
    """
    Extract variables from a prompt using LLM.

    Falls back to no extraction if LLM unavailable (prefer accuracy over false positives).
    """
    if llm is not None:
        try:
            return extract_variables_with_llm(prompt, llm)
        except Exception as e:
            log.warning(f"LLM extraction failed: {e}, skipping variable extraction")
            return prompt, {}, {}

    # No LLM available - skip extraction to avoid regex false positives
    log.debug("No LLM available for variable extraction, skipping")
    return prompt, {}, {}


