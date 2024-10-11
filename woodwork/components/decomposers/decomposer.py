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
        
        # Initialise neo4j cache
        if not self._config_checker(name, ["uri", "user", "password"], config): exit()
        cache = neo4j("decomposer_cache", {"uri": config["uri"], "user": config["user"], "password": config["password"] })
        
        # Testing
        cache.run("MERGE (:Prompt {value: \"This is an example prompt\"})")
    
    @abstractmethod
    def input_handler(self, query):
        """Given a query, return the JSON array denoting the actions to take, passed to the task master."""
        pass
