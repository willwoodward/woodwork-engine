from components.llms.llm import llm

class hugging_face(llm):
    def __init__(self, name, config):
        print("Establishing connection with model...")
        
        super().__init__(name)

        print("Model initialised.")