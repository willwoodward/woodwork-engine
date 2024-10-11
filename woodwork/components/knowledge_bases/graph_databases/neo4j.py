from neo4j import GraphDatabase

from woodwork.components.knowledge_bases.graph_databases.graph_database import graph_database

class neo4j(graph_database):
    def __init__(self, name, config):
        print("Initialising Neo4j Knowledge Base...")
        
        super().__init__(name, config)
        
        if not self._config_checker(name, ["uri", "user", "password", "api_key"], config): exit()
        self._driver = GraphDatabase.driver(config["uri"], auth=(config["user"], config["password"]))
        self._api_key = config["api_key"]
        
        print(f"Neo4j Knowledge Base {name} created.")
        
    def close(self):
        self._driver.close()

    def run(self, query, parameters=None):
        with self._driver.session() as session:
            result = session.run(query, parameters)
            return result.data()
    
    def query(self, query):
        return
    
    def embed(self, label, property):
        query = f"""MATCH (a:{label})
        WHERE a.embedding IS null
        WITH a, genai.vector.encode(a.{property}, "OpenAI", {{ token: \"{self._api_key}\" }}) AS embedding
        CALL db.create.setNodeVectorProperty(a, 'embedding', embedding);"""
        
        return self.run(query)