# from langchain_chroma import Chroma

# from langchain_community.embeddings.sentence_transformer import SentenceTransformerEmbeddings
# from langchain_community.embeddings import HuggingFaceEmbeddings

from woodwork.helper_functions import print_debug
from woodwork.components.knowledge_bases.vector_databases.vector_database import (
    vector_database,
)


class chroma(vector_database):
    def __init__(self, name, **config):
        super().__init__(name, **config)
        print_debug("Initialising Chroma Knowledge Base...")

        # client = get_optional(config, "client", "local")
        # path = get_optional(config, "path", ".woodwork/chroma")

        # embedding_function = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

        # self.__db = Chroma(
        #     client=client,
        #     collection_name="embedding_store",
        #     embedding_function=embedding_function,
        #     persist_directory=path,
        # )

        # self.retriever = self.__db.as_retriever()

        print_debug(f"Chroma Knowledge Base {name} created.")

    def query(self, query, n=3):
        pass

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
