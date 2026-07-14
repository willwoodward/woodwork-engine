from woodwork.components.knowledge_bases.knowledge_base import KnowledgeBase


class GraphDatabase(KnowledgeBase):
    def __init__(self, **config):
        super().__init__(**config)
