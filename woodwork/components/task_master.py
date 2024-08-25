from woodwork.components.component import component

import json

class task_master(component):
    def __init__(self, name):
        super().__init__(name, "task_master")
    
    def add_tools(self, tools):
        self.__tools = tools

    def execute(self, instructions: str):
        # Decode JSON input
        print(instructions)
        instructions = json.loads(instructions)
        
        variables = {}
        
        for instruction in instructions:
            result = None
            
            # Substitute variable inputs
            for key in instruction["inputs"]:
                variable = instruction["inputs"][key]
                if variable in variables:
                    instruction["inputs"][key] = variables[variable]
            
            if instruction["tool"] == "api":
                # Call the api
                api = list(filter(lambda x: x.type == "api", self.__tools))[0]
                result = api.call(instruction["action"], instruction["inputs"])
            
            if instruction["tool"] == "llm":
                result = "llm"

            # Add the result to the variables
            variables[instruction["output"]] = result
            print(f"result = {result}")

