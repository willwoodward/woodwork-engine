from neo4j import GraphDatabase

from woodwork.components.knowledge_bases.graph_databases.graph_database import graph_database

class neo4j(graph_database):
    def __init__(self, name, config):
        print("Initialising Neo4j Knowledge Base...")
        
        super().__init__(name, config)
        
        self._config_checker(name, ["uri", "user", "password"], config)
        self._driver = GraphDatabase.driver(config["uri"], auth=(config["user"], config["password"]))
        
        print(f"Neo4j Knowledge Base {name} created.")
        
    def close(self):
        self._driver.close()

    def run(self, query, parameters=None):
        with self.driver.session() as session:
            result = session.run(query, parameters)
            return result.data()