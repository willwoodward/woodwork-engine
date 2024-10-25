from langchain_openai import ChatOpenAI

from woodwork.helper_functions import print_debug
from woodwork.components.llms.llm import llm

class openai(llm):
    def __init__(self, name, config):
        print_debug(f"Establishing connection with model...")
        
        llm = ChatOpenAI(
            model=config["model"],
            temperature=0,
            max_tokens=None,
            timeout=None,
            max_retries=2,
            api_key=config["api_key"]
        )
        
        retriever = None
        if "knowledge_base" in config:
            retriever = config["knowledge_base"].retriever
        
        super().__init__(name, llm, retriever, config)

        print_debug("Model initialised.")
