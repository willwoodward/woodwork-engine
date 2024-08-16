from components.knowledge_base import knowledge_base

class vector_database(knowledge_base):
    def __init__(self, name):
        super().__init__(name)

    def retriever(self):
        print("Retrieved...")