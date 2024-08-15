from components.knowledge_base import knowledge_base

class chroma(knowledge_base):
    def __init__(self, name):
        super().__init__(name)
        self.score = 5
    
    def test(self):
        print(self.data)