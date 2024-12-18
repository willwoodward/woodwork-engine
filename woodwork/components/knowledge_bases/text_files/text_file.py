import os

from woodwork.components.knowledge_bases.knowledge_base import knowledge_base

class text_file(knowledge_base):
    def __init__(self, name, config):
        super().__init__(name, config)

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
    
    @property
    def description(self):
        return """
            A text file, where the action represents a function name, and inputs is a dictionary of kwargs:
            query(query) - returns True or False depending on if the query is present in the text file.
            get_data() - returns the entire text file's contents
        """
    
    def input(self, function_name, inputs) -> str:
        func = None
        if function_name == "query": func = self.query
        if function_name == "get_data": func = self.get_data
        
        if func is None: return
        
        return func(**inputs)
        