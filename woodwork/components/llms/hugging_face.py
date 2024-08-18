from langchain_community.llms import HuggingFaceEndpoint
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
import os
from dotenv import load_dotenv

from woodwork.components.llms.llm import llm

class hugging_face(llm):
    def __init__(self, name, config):
        print("Establishing connection with model...")
        
        load_dotenv()
        
        self.__llm = HuggingFaceEndpoint(repo_id="mistralai/Mixtral-8x7B-Instruct-v0.1",
                    temperature=0.1, 
                    model_kwargs={"max_length": 100},
                    huggingfacehub_api_token=os.getenv("HF_API_TOKEN"))
                
        super().__init__(name)
        
        if config["knowledge_base"]:
            self.__retriever = config["knowledge_base"].retriever

        print("Model initialised.")
    
    def input_handler(self, query):
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