from woodwork.components.decomposers.decomposer import decomposer
from woodwork.components.task_master import task_master

from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
import json

class llm(decomposer):
    def __init__(self, name, config):
        super().__init__(name, config)
        print("Initialising decomposer...")
        
        if not self._config_checker(name, ["api_key"], config): exit()
        
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
    
    def __clean(self, x):
        start_index = -1
        end_index = -1

        for i in range(len(x)-1):
            if x[i] == "[":
                start_index = i

        for i in range(len(x)-1, 0, -1):
            if x[i] == "]":
                end_index = i
        
        if start_index == -1:
            return None

        return json.loads(x[start_index:end_index+1:])
    
    def input_handler(self, query):
        # Search cache for similar results
        if self._cache_mode:
            closest_query = self._cache_search_actions(query)
            if closest_query["score"] > 0.95:
                print("Cache hit!")
                return self._output.execute(closest_query["actions"])
        
        tool_documentation = ""
        for obj in self._tools:
            tool_documentation += f"{obj.type}:\n{obj.describe()}\n\n"
        
        print(f"[DOCUMENTATION]:\n {tool_documentation}")
        system_prompt = (
            "Given the following tools and their descriptions:\n"
            "{tools} "
            "Answer the user's prompt, returning only the necessary endpoint URIs or LLM prompts "
            "to carry out the steps to solving the user's prompt. "
            "If you do not have necessary tools, say so."
            "Structure your steps in the following schema: "
            "[{{{{\"tool\": tool, \"action\": prompt or function or endpoint, \"inputs\": {{{{variable: value}}}}, \"output\": value}}}}, ...]"
            "Containing the LLM prompt inside action, with curly braces to denote variable inputs, and then containing the variable inputs inside the inputs array."
            "Format these JSON objects into an array of steps, returing only this array. "
            "Specify only the function or endpoint name when they are used. "
            "If you do not have the necessary information, ask for the required information. "
        ).format(tools=tool_documentation)
        
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                ("human", "{input}"),
            ]
        )
        
        chain = prompt | self.__llm
        result = chain.invoke({"input": query}).content
        
        print(f"[RESULT] {result}")
        
        # Clean output as JSON
        result = self.__clean(result)
        
        # Cache instructions
        if self._cache_mode: self._cache_actions(query, result)
        
        # Send to task_master
        return self._output.execute(result)
