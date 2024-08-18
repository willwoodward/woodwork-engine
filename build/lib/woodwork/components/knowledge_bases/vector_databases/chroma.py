import chromadb

from langchain_chroma import Chroma
# from langchain_community.embeddings.sentence_transformer import SentenceTransformerEmbeddings
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_text_splitters import CharacterTextSplitter
from langchain.schema.document import Document

from components.knowledge_bases.vector_databases.vector_database import vector_database

class chroma(vector_database):
    def __init__(self, name, config):
        print("Initialising Chroma Knowledge Base...")
        
        client = None
        if config["client"] == "local":
            if config["path"] == None:
                config["path"] = "../.woodwork/chroma"
            else:
                client = chromadb.PersistentClient(path=config["path"])
                
        embedding_function = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

        persistent_client = chromadb.PersistentClient()
        
        self.__db = Chroma(
            client=persistent_client,
            collection_name="embedding_store",
            embedding_function=embedding_function,
            persist_directory="../.woodwork/chroma"
        )

        retriever = self.__db.as_retriever()
        
        super().__init__(name, retriever)
        
        print(f"Chroma Knowledge Base {name} created.")