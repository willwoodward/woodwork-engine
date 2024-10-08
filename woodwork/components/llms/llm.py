from woodwork.components.component import component

from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate

class llm(component):
    def __init__(self, name, llm, retriever, config):
        # Each LLM will have a: LLM object, input_handler, retriever?
        super().__init__(name, "llm")
                        
        self.__llm = llm
        self.__retriever = retriever
        
        self._memory = None
        if "memory" in config:
            self._memory = config["memory"]
    


    def input_handler(self, query):
        # If there is no retriever object, there is no connected Knowledge Base
        if not self.__retriever:
            return self.question_answer(query)
        else:
            return self.context_answer(query)
            
    def question_answer(self, query):
        # Defining the system prompt
        if self._memory:
            system_prompt = (
                "You are a helpful assistant, answer the provided question, "
                "In 3 sentences or less. "
                "Here are the previous messages as context: "
                "{context}"
            ).format(context=self._memory.data)
        else:
            system_prompt = (
                "You are a helpful assistant, answer the provided question, "
                "In 3 sentences or less. "
            )
        
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                ("human", "{input}"),
            ]
        )
        
        chain = prompt | self.__llm
        response = chain.invoke({"input": query}).content
        
        # Adding to memory
        if self._memory:
            self._memory.add(f"[USER] {query}")
            self._memory.add(f"[AI] {response}")

        return response
        
    def context_answer(self, query):
        system_prompt = (
            "Use the given context to answer the question. "
            "If you don't know the answer, say you don't know. "
            "Use three sentence maximum and keep the answer concise. "
            "Return only the answer to the question. "
            "Context: {context}"
        )
        
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                ("human", "{input}"),
            ]
        )
        
        question_answer_chain = create_stuff_documents_chain(self.__llm, prompt)
        chain = create_retrieval_chain(self.__retriever, question_answer_chain)

        return chain.invoke({"input": query})['answer']

    def describe(self):
        return "Ask the LLM a prompt in the form of the string and it will return an answer to that prompt."