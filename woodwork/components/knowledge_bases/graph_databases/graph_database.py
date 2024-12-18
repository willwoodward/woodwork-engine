from woodwork.components.knowledge_bases.knowledge_base import knowledge_base

class graph_database(knowledge_base):
    def __init__(self, name, config):
        super().__init__(name, config)

    @property
    def description(self): return "A graph database that can be added to, queried and cleared. The query language is Cypher."