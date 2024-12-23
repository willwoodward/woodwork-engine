from woodwork.components.knowledge_bases.knowledge_base import knowledge_base


class vector_database(knowledge_base):
    def __init__(self, name, config):
        super().__init__(name, config)
