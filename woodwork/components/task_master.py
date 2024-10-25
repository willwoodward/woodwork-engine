from woodwork.components.component import component

import json

class task_master(component):
    def __init__(self, name):
        super().__init__(name, "task_master")
    
    def add_tools(self, tools):
        self.__tools = tools

    def execute(self, instructions: str):
        print(instructions)
        
        variables = {}
        
        for instruction in instructions:
            result = None
            
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
            print(f"instruction = {instruction}")
            print(f"result = {result}")

    def _use_tool(self, instruction):
        try:
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
            
            else: return
            return result
        except:
            print("This instruction was not able to execute.")
            return