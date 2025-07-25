import logging

from langchain.text_splitter import CharacterTextSplitter, RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
import hashlib

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
        results = self._retriever.invoke(query)

        context_parts = []
        for x in results:
            # Escape braces in content for formatting safety
            content = x.page_content.replace("{", "{{").replace("}", "}}")
            # Extract the file_path metadata (change key if yours is different)
            file_path = x.metadata.get("file_path", "unknown file")

            # Format how you want the metadata to appear — here just prefixing
            context_parts.append(f"[File: {file_path}]\n{content}")

        return "\n\n".join(context_parts)

    def embed(self, document: str, file_rel_path: str):
        # Split into chunks (assume self._recursive_text_splitter exists)
        chunks = self._recursive_text_splitter.split_text(document)
        chunk_ids = []
        metadatas = []
        for idx, chunk in enumerate(chunks):
            # Create deterministic ID: hash of file_rel_path + chunk + idx
            chunk_id = hashlib.sha256(f"{file_rel_path}:{idx}:{chunk}".encode("utf-8")).hexdigest()
            chunk_ids.append(chunk_id)
            metadatas.append({"file_path": file_rel_path})

        # Add texts with IDs to vector DB (assuming self._db.add_texts supports ids param)
        self._db.add_texts(texts=chunks, ids=chunk_ids, metadatas=metadatas)

        return chunk_ids

    def delete_vectors(self, ids):
        if not ids:
            return

        try:
            self._db.delete(ids=ids)
            print(f"Deleted {len(ids)} vectors from Chroma.")
        except Exception as e:
            print(f"Error deleting vectors from Chroma: {e}")

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
