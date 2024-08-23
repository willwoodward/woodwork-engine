from woodwork.components.decomposers.decomposer import decomposer

from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

class llm(decomposer):
    def __init__(self, name, config):
        print("Initialising decomposer...")
        
        self.__llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
            max_tokens=None,
            timeout=None,
            max_retries=2,
            api_key=config["api_key"]
        )
        
        self.__retriever = None
        if "knowledge_base" in config:
            retriever = config["knowledge_base"].retriever
        
        self.__api = config["api"]
        
        super().__init__(name)
        print("Decomposer initialised.")
    
    def input_handler(self, query):
        # Feed the input into an LLM query and return actions
        system_prompt = (
            "Given the following documentation for an API server:"
            "{context}"
            "Answer the user's prompt, returning only the necessary endpoint URIs "
            "With no formatting except for newlines, to carry out the steps to solving the user's prompt. "
            "If you do not have necessary tools, say so."
        ).format(context=self.__api.describe())
        
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                ("human", "{input}"),
            ]
        )
        
        chain = prompt | self.__llm

        return chain.invoke({"input": query}).content