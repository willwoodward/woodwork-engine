from neo4j import GraphDatabase
from openai import OpenAI

from woodwork.helper_functions import print_debug
from woodwork.components.knowledge_bases.graph_databases.graph_database import graph_database

class neo4j(graph_database):
    def __init__(self, name, config):
        print_debug("Initialising Neo4j Knowledge Base...")
        
        super().__init__(name, config)
        
        if not self._config_checker(name, ["uri", "user", "password", "api_key"], config): exit()
        self._driver = GraphDatabase.driver(config["uri"], auth=(config["user"], config["password"]))
        if not self._connected(): exit()
        
        self._api_key = config["api_key"]
        self._openai_client = OpenAI()
        
        print_debug(f"Neo4j Knowledge Base {name} created.")
    
    def _connected(self):
        try:
            with self._driver.session() as session:
                session.run("RETURN 1")
                return True
        except Exception as e:
            return False
        finally:
            self._driver.close()
        
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

    def similarity_search(self, prompt, label, property):
        response = self._openai_client.embeddings.create(
            input=prompt,
            model="text-embedding-ada-002"
        )

        # Extract the embedding (a list of 1536 numbers)
        embedding = response.data[0].embedding

        query = f"""MATCH (a:{label})
        CALL db.index.vector.queryNodes('embeddings', 10, {embedding})
        YIELD node AS node, score
        RETURN elementId(node) AS nodeID, node.{property} AS {property}, score"""
        
        return self.run(query)