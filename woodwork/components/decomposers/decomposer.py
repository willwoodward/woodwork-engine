import json
import logging

from abc import ABC, abstractmethod

from woodwork.components.component import component
from woodwork.utils import format_kwargs, get_optional
from woodwork.core.task_master import task_master

log = logging.getLogger(__name__)


class decomposer(component, ABC):
    def __init__(self, tools, task_m: task_master, **config):
        format_kwargs(config, tools=tools, task_m=task_m, component="decomposer")
        super().__init__(**config)
        log.debug("Creating the decomposer...")

        self._tools = tools
        self._task_m = task_m
        self._cache = task_m.cache
        self._cache_mode = False
        api_key = get_optional(config, "api_key")

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

    def close(self):
        if self._cache_mode:
            self._cache.close()

    @abstractmethod
    def input(self, query):
        """Given a query, return the JSON array denoting the actions to take, passed to the task master."""
        pass

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
