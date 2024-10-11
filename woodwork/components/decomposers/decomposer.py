from abc import ABC, abstractmethod

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
                if not self._config_checker(name, ["uri", "user", "password"], config): exit()
                self._cache = neo4j("decomposer_cache", {"uri": config["uri"], "user": config["user"], "password": config["password"] })
    
    @abstractmethod
    def input_handler(self, query):
        """Given a query, return the JSON array denoting the actions to take, passed to the task master."""
        pass

    def _cache_actions(self, prompt: str, instructions: list[any]):
        """Add the actions to the graph if they aren't already present, as a chain."""
        # Check to see if the action has been cached
        
        # Instructions must have at least one instruction
        if len(instructions) == 0: return
        
        # Generate the database query
        query = f"MERGE (:Prompt {{value: \"{prompt}\"}})"
        
        for instruction in instructions:
            query += f"-[:NEXT]->(:Action {{value: \"{instruction}\"}})"
        
        # Execute query
        self._cache.run(query)
        
        return
    
    def _cache_search_actions(self, prompt: str):
        return