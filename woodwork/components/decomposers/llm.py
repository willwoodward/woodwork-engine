from woodwork.components.decomposers.decomposer import decomposer
from woodwork.components.task_master import task_master

from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
import json

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
        
        self.__output = config["output"]
        
        super().__init__(name)
    
    def input_handler(self, query):
        # Feed the input into an LLM query and return actions
        system_prompt = (
            "Given the following documentation for an API server:"
            "{context}"
            "And the ability to prompt an LLM and receive an output, "
            "Answer the user's prompt, returning only the necessary endpoint URIs or LLM prompts "
            "to carry out the steps to solving the user's prompt. "
            "If you do not have necessary tools, say so."
            "Structure your steps in the following schema: "
            "{{{{\"tool\": api or llm, \"action\": prompt or endpoint, \"inputs\": {{{{variable: value}}}}, \"output\": value}}}}"
            "Containing the LLM prompt inside action, with curly braces to denote variable inputs, and then containing the variable inputs inside the inputs array."
            "Format these JSON objects into an array of steps, returing only this array."
        ).format(context=self.__api.describe())
        
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                ("human", "{input}"),
            ]
        )
        
        chain = prompt | self.__llm
        result = chain.invoke({"input": query}).content
        
        # Send to task_master
        self.__output.execute(result)

        return result