from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain.text_splitter import CharacterTextSplitter

from woodwork.helper_functions import print_debug, get_optional
from woodwork.components.knowledge_bases.vector_databases.vector_database import (
    vector_database,
)


class chroma(vector_database):
    def __init__(self, name, api_key, **config):
        super().__init__(name, **config)
        print_debug("Initialising Chroma Knowledge Base...")

        self._path = get_optional(config, "path", ".woodwork/chroma")
        self._file_to_embed = get_optional(config, "file_to_embed")

        embeddings = OpenAIEmbeddings(model="text-embedding-3-large")

        self._db = Chroma(
            collection_name="collection",
            embedding_function=embeddings,
            persist_directory=self._path,
        )

        self.retriever = self._db.as_retriever()

        self._text_splitter = CharacterTextSplitter(
            separator="\n\n",  # Split by paragraphs
            chunk_size=1000,  # Maximum characters per chunk
            chunk_overlap=200,  # Overlap between chunks (change to 200)
        )

        print_debug(f"Chroma Knowledge Base {name} created.")

    def query(self, query, n=3):
        pass

    def embed(self, document: str):
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
