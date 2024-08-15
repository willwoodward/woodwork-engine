import chromadb

from components.knowledge_bases.vector_databases.vector_database import vector_database

class chroma(vector_database):
    def __init__(self, name, config):
        print("Initialising Chroma Knowledge Base...")
        
        client = None
        if config["client"] == "local":
            if config["path"] == None:
                print("Local file path needs to be present for a local chroma client.")
            else:
                client = chromadb.PersistentClient(path=config["path"])
        
        super().__init__(name)
        
        print(f"Chroma Knowledge Base {name} created.")