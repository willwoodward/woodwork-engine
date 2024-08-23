from langchain_community.llms import HuggingFaceEndpoint

from woodwork.components.llms.llm import llm

class hugging_face(llm):
    def __init__(self, name, config):
        print(f"Establishing connection with model...")
                
        llm = HuggingFaceEndpoint(
            repo_id="mistralai/Mixtral-8x7B-Instruct-v0.1",
            temperature=0.1, 
            model_kwargs={"max_length": 100},
            huggingfacehub_api_token=config["api_key"]
        )
        
        retriever = None
        if "knowledge_base" in config:
            retriever = config["knowledge_base"].retriever
        
        super().__init__(name, llm, retriever)

        print("Model initialised.")
