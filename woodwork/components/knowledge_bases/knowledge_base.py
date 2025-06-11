from abc import ABC, abstractmethod
import os
import shutil
from langchain_community.document_loaders import PyPDFLoader


from woodwork.components.component import component
from woodwork.interfaces.tool_interface import tool_interface
from woodwork.helper_functions import format_kwargs


class knowledge_base(component, tool_interface, ABC):
    def __init__(self, **config):
        format_kwargs(config, component="knowledge_base")
        super().__init__(**config)

    def embed_file(self, file_path: str):
        if file_path.endswith(".pdf"):
            loader = PyPDFLoader(file_path)
            documents = loader.load()
            full_text = "\n".join([doc.page_content for doc in documents])
            self.embed(full_text)
        else:
            with open(file_path, "r") as file:
                self.embed(file.read())

    def embed_init(self):
        if self._file_to_embed is not None and os.path.exists(self._file_to_embed):
            if os.path.isfile(self._file_to_embed):
                self.embed_file(self._file_to_embed)
            elif os.path.isdir(self._file_to_embed):
                for root, _, files in os.walk(self._file_to_embed):
                    for file in files:
                        file_path = os.path.join(root, file)
                        self.embed_file(file_path)

    def clear_all(self):
        if os.path.exists(self._path):
            shutil.rmtree(self._path)

    @abstractmethod
    def query(self, query):
        pass

    @property
    @abstractmethod
    def retriever(self):
        # Each knowledge base should come with a default retriever. For use with LLMs.
        pass

    @property
    @abstractmethod
    def embedding_model(self):
        # Each knowledge base should come with a default embedding model.
        return self._embedding_model
