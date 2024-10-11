from abc import ABC, abstractmethod
from openai import OpenAI

from woodwork.components.component import component
from woodwork.components.knowledge_bases.graph_databases.neo4j import neo4j

class decomposer(component, ABC):
    def __init__(self, name, config):
        super().__init__(name, "decomposer")
        print("Creating the decomposer...")
        
        if not self._config_checker(name, ["tools", "output"], config): exit()

        self._tools = config["tools"]
        self._output = config["output"]
        self._cache = None
        
        if "cache" in config:
            if config["cache"] == "true":
                # Initialise neo4j cache
                if not self._config_checker(name, ["uri", "user", "password", "api_key"], config): exit()
                self._cache = neo4j("decomposer_cache", {"uri": config["uri"], "user": config["user"], "password": config["password"], "api_key": config["api_key"] })
    
    @abstractmethod
    def input_handler(self, query):
        """Given a query, return the JSON array denoting the actions to take, passed to the task master."""
        pass

    def _cache_actions(self, prompt: str, instructions: list[any]):
        """Add the actions to the graph if they aren't already present, as a chain."""
        # Check to see if the action has been cached
        if self._cache_search_actions(prompt)["score"] > 0.95:
            print("Similar prompts have already been cached.")
            return
        
        # Instructions must have at least one instruction
        if len(instructions) == 0: return
        
        # Generate the database query
        query = f"MERGE (:Prompt {{value: \"{prompt}\"}})"
        
        for instruction in instructions:
            query += f"-[:NEXT]->(:Action {{value: \"{instruction}\"}})"
        
        # Execute query
        self._cache.run(query)
        
        # Add the vector embedding for the prompt
        self._cache.embed("Prompt", "value")        
        return
    
    def _cache_search_actions(self, prompt: str):
        similar_prompts = self._cache.similarity_search(prompt, "Prompt", "value")
        print(f"[SIMILAR PROMPTS] {similar_prompts}")
        
        best_prompt = similar_prompts[0]["value"]
        score = similar_prompts[0]["score"]
        
        actions = self._cache.run(f"""MATCH (p:Prompt)
                WHERE elementId(p) = \"{similar_prompts[0]["nodeID"]}\"
                WITH p
                MATCH path=(p)-[NEXT*]-(a:Action)
                RETURN a AS result""")
        
        actions = list(map(lambda x: x["result"]["value"], actions))
        
        return {"prompt": best_prompt, "actions": actions, "score": score}