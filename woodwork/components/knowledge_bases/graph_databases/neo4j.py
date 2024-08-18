from components.knowledge_bases.graph_databases.graph_database import graph_database

class neo4j(graph_database):
    def __init__(self, name, config):
        print("Initialising Neo4j Knowledge Base...")
        
        super().__init__(name)
        
        print(f"Neo4j Knowledge Base {name} created.")