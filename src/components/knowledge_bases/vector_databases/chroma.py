from components.knowledge_bases.vector_databases.vector_database import vector_database

class chroma(vector_database):
    def __init__(self, name):
        super().__init__(name)