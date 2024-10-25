import chromadb

from langchain_chroma import Chroma
# from langchain_community.embeddings.sentence_transformer import SentenceTransformerEmbeddings
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_text_splitters import CharacterTextSplitter
from langchain.schema.document import Document

from woodwork.components.knowledge_bases.vector_databases.vector_database import vector_database

class chroma(vector_database):
    def __init__(self, name, config):        
        print_debug("Initialising Chroma Knowledge Base...")
        
        self._config_checker(name, ["client"], config)
        
        client = None
        if config["client"] == "local":
            if "path" not in config:
                config["path"] = ".woodwork/chroma"
            else:
                client = chromadb.PersistentClient(path=config["path"])
                
        embedding_function = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        
        self.__db = Chroma(
            client=client,
            collection_name="embedding_store",
            embedding_function=embedding_function,
            persist_directory=config["path"]
        )

        self.retriever = self.__db.as_retriever()

        super().__init__(name, config)
        
        print_debug(f"Chroma Knowledge Base {name} created.")
    
    def query(self, query):
        pass