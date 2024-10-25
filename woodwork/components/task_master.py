from woodwork.helper_functions import print_debug
from woodwork.components.component import component

class task_master(component):
    def __init__(self, name):
        super().__init__(name, "task_master")
    
    def add_tools(self, tools):
        self.__tools = tools

    def execute(self, instructions: str):        
        variables = {}
        prev_instructon = ""
        
        for instruction in instructions:            
            # Substitute variable inputs
            for key in instruction["inputs"]:
                variable = instruction["inputs"][key]
                if variable in variables:
                    instruction["inputs"][key] = variables[variable]
            
            # Use tool
            result = self._use_tool(instruction)

            if not result: break

            # Add the result to the variables
            variables[instruction["output"]] = result
            prev_instructon = result
            print_debug(f"instruction = {instruction}")
            print_debug(f"result = {result}")
        
        return prev_instructon

    def _use_tool(self, instruction):
        try:
            result = None
            if instruction["tool"] == "api":
                # Call the api
                api = list(filter(lambda x: x.type == "api", self.__tools))[0]
                result = api.call(instruction["action"], instruction["inputs"])
            
            if instruction["tool"] == "llm":
                # Substitute inputs
                prompt = instruction["action"]
                for key in instruction["inputs"]:
                    prompt = prompt.replace(key, instruction["inputs"][key])
                
                llm = list(filter(lambda x: x.type == "llm", self.__tools))[0]
                result = llm.question_answer(prompt)
            
            return result
        except:
            print("This instruction was not able to execute.")
            return