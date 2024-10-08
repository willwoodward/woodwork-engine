import os

from woodwork.components.knowledge_base import knowledge_base

class text_file(knowledge_base):
    def __init__(self, name, config):
        super().__init__(name)

        # Check if the file exists before creating it
        if not os.path.exists(config["path"]):
            with open(config["path"], 'w'):
                pass
        
        with open(config["path"], 'r') as file:
            self.__data = file.read()

    
    def query(self, query):
        if query in self.__data: return True
        return False

    def get_data(self):
        return self.__data