from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain.text_splitter import CharacterTextSplitter
import os

from woodwork.helper_functions import print_debug, get_optional
from woodwork.components.knowledge_bases.vector_databases.vector_database import (
    vector_database,
)
from woodwork.globals import global_config


class chroma(vector_database):
    def __init__(self, name, api_key, **config):
        super().__init__(name, **config)
        print_debug("Initialising Chroma Knowledge Base...")

        path = get_optional(config, "path", ".woodwork/chroma")
        file_to_embed = get_optional(config, "file_to_embed")

        embeddings = OpenAIEmbeddings(model="text-embedding-3-large")

        self._db = Chroma(
            collection_name="collection",
            embedding_function=embeddings,
            persist_directory=path,
        )

        self.retriever = self._db.as_retriever()

        self._text_splitter = CharacterTextSplitter(
            separator="\n\n",  # Split by paragraphs
            chunk_size=1000,   # Maximum characters per chunk
            chunk_overlap=200  # Overlap between chunks (change to 200)
        )

        print_debug(f"Chroma Knowledge Base {name} created.")

        if global_config["mode"] == "embed":
            if file_to_embed is not None and os.path.exists(file_to_embed):
                with open(file_to_embed, "r") as file:
                    self.embed(file.read())

    def query(self, query, n=3):
        pass

    def embed(self, document: str):
        print("embedding")
        chunks = self._text_splitter.split_text(document)
        self._db.add_texts(chunks)
        return

    @property
    def description(self):
        return """
            A vector database, where the action represents a function name, and inputs is a dictionary of kwargs:
            query(query, n=3) - returns the n (defaults to 3) most similar text embeddings to the supplied query string 
        """

    def input(self, function_name, inputs) -> str:
        func = None
        if function_name == "query":
            func = self.query

        if func is None:
            return

        return func(**inputs)
