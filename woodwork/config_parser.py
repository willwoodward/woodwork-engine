import re
import os
from dotenv import load_dotenv

from woodwork.components.component import component
from woodwork.components.knowledge_bases.vector_databases.chroma import chroma
from woodwork.components.knowledge_bases.graph_databases.neo4j import neo4j
from woodwork.components.llms.hugging_face import hugging_face
from woodwork.components.llms.openai import openai
from woodwork.components.inputs.command_line import command_line
from woodwork.components.apis.web import web
from woodwork.components.decomposers.llm import llm
from woodwork.components.task_master import task_master

task_m = task_master("task_master")

def dependency_resolver(components, component):
    # Parser parses into JSON for each component
    # Each component should have a 'depends_on' array if it uses a variable as a value, init as []
    # How do we get each variable? Dict of components, key = name, value = component dictionary
    # Traverse the depends_on as DFS
    
    # Base case: no more dependencies in the depends_on array
    if component.depends_on == []:
        # Initialise component, return object reference
        component.depends_on = None
        return

    # Else, if the depends_on array has dependencies
    for dependency in depends_on:
        # Resolve that dependency, replace those variables in the config
        component_object = dependency_resolver(components, dependency)
    
    # Return component object
    component.depends_on = None
    return 

def main_function():
    components: list[component] = []

    current_directory = os.getcwd()
    load_dotenv()

    with open(current_directory + "/main.ww", "r") as f:
        lines = f.read()
        
        entry_pattern = r".+=.+\{[\s\S]*?\}"
        entries = re.findall(entry_pattern, lines)
        print(entries)

        for entry in entries:
            command = {}
            # Replace these with some fancy regex
            command["variable"] = entry.split("=")[0].strip()
            command["component"] = entry.split("=")[1].split(" ")[1].strip()
            command["type"] = entry.split(command["component"])[1].split("{")[0].strip()
            
            config_items = list(map(lambda x: x.replace("\n", "").strip(), re.findall(r"\n[^\n\}]+", entry)))
            config_items = [x for x in config_items if x != ""]

            # Parses the settings for each command
            command["config"] = {}
            for item in config_items:
                key = item.split(":")[0].strip()
                value = item.split(":")[1].strip()
                
                # If the value is not a string, it references a variable
                # We replace this variable with a reference to the object
                if value[0] != "\"" and value[0] != "'" and value[0] != '$' and value[0] != "[":
                    # Search components for the variable
                    for c in components:
                        if c.name == value:
                            value = c
                            break
                
                # If the value starts with $, then it is a secret key in the .env file
                # Replace this with the secret
                elif value[0] == '$':
                    value = os.getenv(value[1::])
                
                # If the value is an array, parse it as an array of references
                elif value[0] == "[":
                    value = list(map(lambda x: x.strip(), value[1::].split(",")))
                    
                    for i in range(len(value)):
                        for c in components:
                            if c.name == value[i]:
                                value[i] = c
                                break
                    
                    print(f"values = {value}")
                                    
                elif (value[0] == "\"" and value[-1] == "\"") or (value[0] == "\'" and value[-1] == "\'"):
                    value = value[1:-1:]

                command["config"][key] = value
            
            print(command)

            # Create the objects specified by the command
            if command["component"] == "knowledge_base":
                if command["type"] == "chroma": components.append(chroma(command["variable"], command["config"]))
                if command["type"] == "neo4j":  components.append(neo4j(command["variable"], command["config"]))

            if command["component"] == "llm":
                if command["type"] == "hugging_face": components.append(hugging_face(command["variable"], command["config"]))
                if command["type"] == "openai": components.append(openai(command["variable"], command["config"]))

            if command["component"] == "input":
                task_m.add_tools(components)
                if command["type"] == "command_line": components.append(command_line(command["variable"], command["config"]))

            if command["component"] == "api":
                if command["type"] == "web": components.append(web(command["variable"], command["config"]))

            if command["component"] == "decomposer":
                command["config"]["output"] = task_m
                if command["type"] == "llm": components.append(llm(command["variable"], command["config"]))
