import json
import logging

from abc import ABC, abstractmethod
from typing import Any

from woodwork.components.component import component
from woodwork.components.knowledge_bases.graph_databases.neo4j import neo4j
from woodwork.helper_functions import format_kwargs, get_optional

log = logging.getLogger(__name__)


class decomposer(component, ABC):
    def __init__(self, tools, output, **config):
        format_kwargs(config, tools=tools, output=output, component="decomposer")
        super().__init__(**config)
        log.debug("Creating the decomposer...")

        self._tools = tools
        self._output = output
        self._cache = None
        api_key = get_optional(config, "api_key")

        if "cache" in config:
            if config["cache"]:
                # Initialise neo4j cache
                self._cache_mode = True

                if api_key is None:
                    exit()

                self._cache = neo4j(
                    uri="bolt://localhost:7687",
                    user="neo4j",
                    password="testpassword",
                    api_key=api_key,
                    name="decomposer_cache",
                )
                self._cache.init_vector_index("embeddings", "Prompt", "embedding")
        else:
            self._cache_mode = False

    def close(self):
        if self._cache_mode:
            self._cache.close()

    @abstractmethod
    def input(self, query):
        """Given a query, return the JSON array denoting the actions to take, passed to the task master."""
        pass

    def _cache_actions(self, workflow: dict[str, Any]):
        """Add the actions to the graph if they aren't already present, as a chain."""
        prompt = workflow["name"]
        workflow_inputs = str(list(workflow["inputs"].keys()))
        instructions = workflow["plan"]

        # Check to see if the action has been cached
        if self._cache_search_actions(prompt)["score"] > 0.96:
            log.debug("Similar prompts have already been cached.")
            return

        # Instructions must have at least one instruction
        if len(instructions) == 0:
            return

        # Generate the database query
        query = f'MERGE (p:Prompt {{value: "{prompt}", inputs: {workflow_inputs}}})'

        for instruction in instructions:
            query += f'-[:NEXT]->(:Action {{value: "{instruction}"}})'

        query += "\nRETURN elementId(p) as id"

        # Execute query
        # result = self._cache.run(query)[0]

        # Add the vector embedding for the prompt
        # self._cache.embed("Prompt", "value")

        # Return the ID of the prompt node
        # return result["id"]
        return None

    def _cache_search_actions(self, prompt: str):
        similar_prompts = self._cache.similarity_search(prompt, "Prompt", "value")

        if len(similar_prompts) == 0:
            return {"prompt": "", "actions": [], "score": 0}

        log.debug(f"[SIMILAR PROMPTS] {similar_prompts}")

        best_prompt = similar_prompts[0]["value"]
        best_inputs = similar_prompts[0]["inputs"]
        score = similar_prompts[0]["score"]

        actions = self._cache.run(f"""MATCH (p:Prompt)
                WHERE elementId(p) = \"{similar_prompts[0]["nodeID"]}\"
                WITH p
                MATCH path=(p)-[NEXT*]-(a:Action)
                RETURN a AS result, p as name""")

        actions = list(map(lambda x: json.loads(x["result"]["value"].replace("'", '"')), actions))

        return {"prompt": best_prompt, "inputs": best_inputs, "actions": actions, "score": score}
