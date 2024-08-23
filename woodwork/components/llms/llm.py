from woodwork.components.component import component

from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate

class llm(component):
    def __init__(self, name, llm, retriever):
        # Each LLM will have a: LLM object, input_handler, retriever?
        super().__init__(name, "llm")
        
        self.__llm = llm
        self.__retriever = retriever
    


    def input_handler(self, query):
        # If there is no retriever object, there is no connected Knowledge Base
        if not self.__retriever:
            return self.question_answer(query)
        else:
            return self.context_answer(query)
            
    def question_answer(self, query):
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

        return chain.invoke({"input": query}).content
        
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