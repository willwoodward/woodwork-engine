import os

from woodwork.components.knowledge_bases.knowledge_base import knowledge_base
from woodwork.helper_functions import format_kwargs


class text_file(knowledge_base):
    def __init__(self, path: str, **config):
        format_kwargs(config, path=path, type="text_file")
        super().__init__(**config)

        self._path = path

        # Check if the file exists before creating it
        if not os.path.exists(path):
            with open(path, "w"):
                pass

        with open(path, "r") as file:
            self.__data = file.read()

    def query(self, query):
        if query in self.__data:
            return True
        return False

    def read(self):
        return self.__data

    def write(self, content):
        with open(self._path, "w") as file:
            file.write(content)
            self.__data = content

    @property
    def description(self):
        return """
            A text file, where the action represents a function name, and inputs is a dictionary of kwargs:
            query(query) - returns True or False depending on if the query is present in the text file.
            read() - returns the entire text file's contents
            write(content) - replaces the text file's contents with content.
        """

    def input(self, function_name, inputs) -> str | None:
        func = None
        if function_name == "query":
            func = self.query
        if function_name == "read":
            func = self.read
        if function_name == "write":
            func = self.write

        if func is None:
            return

        return func(**inputs)
