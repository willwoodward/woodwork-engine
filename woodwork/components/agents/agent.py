import json
import logging
from typing import Optional

from abc import ABC, abstractmethod

from woodwork.components.component import Component
from woodwork.interfaces import tool_interface
from woodwork.utils import format_kwargs, get_optional
from woodwork.components.tools.planning import planning_tools

log = logging.getLogger(__name__)


class Agent(Component, tool_interface, ABC):
    def __init__(self, tools, **config):
        log.debug(f"[Agent] Received config keys: {list(config.keys())}")
        # Remove task_m from config if passed (legacy support)
        config.pop("task_m", None)
        format_kwargs(config, tools=tools, component="agent")
        log.debug(f"[Agent] Config keys after format_kwargs: {list(config.keys())}")
        super().__init__(**config)
        log.debug("Creating the agent...")

        self._tools = tools
        self._cache = None
        self._cache_mode = False

        # Agents must be provided with a model (an LLM component instance)
        model = get_optional(config, "model")
        if model is None:
            raise TypeError("Agent components must be configured with a 'model' (LLM component).")
        self.model = model

        # Backwards-compatible retrieval of api_key where required (e.g., for cache initialization).
        api_key = None
        if hasattr(model, "_api_key"):
            api_key = getattr(model, "_api_key")
        elif hasattr(model, "config") and isinstance(getattr(model, "config"), dict):
            api_key = model.config.get("api_key")

        # Inject core planning tools
        self._is_planner = get_optional(config, "planning", False)
        if self._is_planner:
            planning = planning_tools(**{"name": "planning_tools"})
            self._tools.append(planning)

        # Auto-discover and register tool schemas with event bus
        try:
            from woodwork.runtime.unified_event_bus import get_global_event_bus

            event_bus = get_global_event_bus()
            schemas = event_bus.discover_tools_from_agent(self)
            log.info(f"[Agent] Auto-discovered {len(schemas)} tool schemas for workflow builder")
        except Exception as e:
            log.warning(f"[Agent] Failed to auto-discover tool schemas: {e}")

        if config.get("cache", False):
            try:
                from woodwork.components.knowledge_bases.graph_databases.neo4j import Neo4j
                from woodwork.defaults import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

                self._cache = Neo4j(uri=NEO4J_URI, user=NEO4J_USER, password=NEO4J_PASSWORD, name="agent_cache")
                self._cache_mode = True

                if api_key is None:
                    raise TypeError("Cache enabled for agent but no API key provided via model or agent config.")

                self._cache.set_api_key(api_key=api_key)
                self._cache.init_vector_index(index_name="embeddings", label="Prompt", property="embedding")
            except Exception as e:
                log.warning(f"[Agent] Cache requested but unavailable: {e}. Continuing without cache.")
                self._cache_mode = False

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
    def input(self, query: str, inputs: Optional[dict] = None):
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
