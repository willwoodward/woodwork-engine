import logging

from langchain.text_splitter import CharacterTextSplitter, RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

from woodwork.components.knowledge_bases.vector_databases.vector_database import (
    vector_database,
)
from woodwork.helper_functions import format_kwargs, get_optional

log = logging.getLogger(__name__)


class chroma(vector_database):
    def __init__(self, api_key: str, **config):
        format_kwargs(config, api_key=api_key, type="chroma")
        super().__init__(**config)
        log.debug("Initializing Chroma Knowledge Base...")

        self._path = get_optional(config, "path", ".woodwork/chroma")
        self._file_to_embed = get_optional(config, "file_to_embed")
        self._embedding_model = OpenAIEmbeddings(model="text-embedding-3-large")

        self._db = Chroma(
            collection_name="collection",
            embedding_function=self._embedding_model,
            persist_directory=self._path,
        )

        self._retriever = self._db.as_retriever()

        self._text_splitter = CharacterTextSplitter(
            separator="\n\n",  # Split by paragraphs
            chunk_size=1000,  # Maximum characters per chunk
            chunk_overlap=200,  # Overlap between chunks (change to 200)
        )

        self._recursive_text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
        )

        log.debug("Chroma Knowledge Base created.")

    def query(self, query, n=3):
        pass

    def embed(self, document: str):
        # chunks = self._text_splitter.split_text(document)
        chunks = self._recursive_text_splitter.split_text(document)
        self._db.add_texts(chunks)

        return

    @property
    def retriever(self):
        return self._retriever

    @property
    def embedding_model(self):
        return self._embedding_model

    @property
    def description(self):
        return """
            A vector database, where the action represents a function name, and inputs is a dictionary of kwargs:
            query(query, n=3) - returns the n (defaults to 3) most similar text embeddings to the supplied query string 
        """

    def input(self, function_name, inputs) -> str | None:
        func = None
        if function_name == "query":
            func = self.query

        if func is None:
            return

        return func(**inputs)
