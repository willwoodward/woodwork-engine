import json
import logging

from abc import ABC, abstractmethod

from woodwork.components.component import component
from woodwork.interfaces import tool_interface
from woodwork.utils import format_kwargs, get_optional
from woodwork.core.task_master import task_master
from woodwork.components.core.planning import planning_tools

# EventEmitter factory
from woodwork.events import create_default_emitter

log = logging.getLogger(__name__)


class agent(component, tool_interface, ABC):
    def __init__(self, tools, task_m: task_master, **config):
        format_kwargs(config, tools=tools, task_m=task_m, component="agent")
        super().__init__(**config)
        log.debug("Creating the agent...")

        self._tools = tools
        self._task_m = task_m
        self._cache = task_m.cache
        self._cache_mode = False
        api_key = get_optional(config, "api_key")

        # Inject core planning tools
        self._is_planner = get_optional(config, "planning", False)
        if self._is_planner:
            planning = planning_tools(**{"name": "planning_tools"})
            self._tools.append(planning)
            self._task_m.add_tools([planning])

        if "cache" in config:
            if config["cache"]:
                # Initialise neo4j cache
                self._cache_mode = True

                if api_key is None:
                    exit()

                self._cache.set_api_key(api_key=api_key)
                self._cache.init_vector_index(index_name="embeddings", label="Prompt", property="embedding")
        else:
            self._cache_mode = False

        # Event emitter: use component's emitter if available, or accept via config, or create default
        if hasattr(self, '_emitter') and self._emitter is not None:
            # Component already created an emitter with hooks/pipes
            pass
        else:
            provided_emitter = config.get("events") if isinstance(config, dict) else None
            self._emitter = provided_emitter if provided_emitter is not None else create_default_emitter()

    def close(self):
        if self._cache_mode:
            self._cache.close()

    def _cache_search_actions(self, prompt: str):
        similar_prompts = self._cache.similarity_search(prompt, "Prompt", "value")

        if len(similar_prompts) == 0:
            return {"prompt": "", "actions": [], "score": 0}

        log.debug(f"[SIMILAR PROMPTS] {similar_prompts}")

        best_prompt = similar_prompts[0]["value"]
        best_inputs = similar_prompts[0]["inputs"]
        score = similar_prompts[0]["score"]

        actions = self._cache.run(f"""MATCH (p:Prompt)
                WHERE elementId(p) = "{similar_prompts[0]["nodeID"]}"
                WITH p
                MATCH path=(p)-[NEXT*]-(a:Action)
                RETURN a AS result, p as name""")

        actions = list(map(lambda x: json.loads(x["result"]["value"].replace("'", '"')), actions))

        return {"prompt": best_prompt, "inputs": best_inputs, "actions": actions, "score": score}


    @abstractmethod
    def input(self, query: str, inputs: dict = None):
        """Given a query, will use the provided tools and memory to perform actions to solve the query."""
        pass

    @property
    def description(self):
        return f"""\nGeneral Reasoning Agent — callable tool.

Call this tool by setting the step **Action** with:
- **tool**: {self.name}
- **action**: a natural-language prompt describing the task. You may include variable placeholders in curly braces, e.g., "Summarize {{{{document}}}}".
- **inputs**: a dict mapping placeholder names (from the prompt) to **variable names** produced by earlier steps outputs (not literals).
- **output**: the variable name to store the result.

The agent will plan, use its internal tools, and memory, and return a result.

Usage Example:
Action: {{{{"tool": "agent", "action": "Translate {{{{text}}}} to French", "inputs": {{{{"text": "text"}}}}, "output": "french_text"}}}}

Available Tools for this Agent:
{[t.name for t in self._tools]}
"""
