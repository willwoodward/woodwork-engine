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

def dependency_resolver(commands, component):
    # Parser parses into JSON for each component
    # Each component should have a 'depends_on' array if it uses a variable as a value, init as []
    # How do we get each variable? Dict of commands, key = name, value = component dictionary
    # Traverse the depends_on as DFS
    
    print(component)
    # Base case: no dependencies in the depends_on array
    if component["depends_on"] == []:
        # Initialise component, return object reference
        if "object" not in component:
            component["object"] = create_object(component)
        return component["object"]

    # Else, if the depends_on array has dependencies
    for dependency in component["depends_on"]:
        # Resolve that dependency, replace those variables in the config
        component_object = dependency_resolver(commands, commands[dependency])
        
        for key, value in component["config"].items():
            # Handle arrays
            if isinstance(value, list):
                for i in range(len(value)):
                    if value[i] == dependency:
                        value[i] = component_object
            
            if value == dependency:
                print(value, dependency)
                component["config"][key] = component_object
    
    # Return component object
    component["depends_on"] = []
    component["object"] = create_object(component)
    return component["object"]

def create_object(command):
    if command["component"] == "knowledge_base":
        if command["type"] == "chroma": return chroma(command["variable"], command["config"])
        if command["type"] == "neo4j":  return neo4j(command["variable"], command["config"])

    if command["component"] == "llm":
        if command["type"] == "hugging_face": return hugging_face(command["variable"], command["config"])
        if command["type"] == "openai": return openai(command["variable"], command["config"])

    if command["component"] == "input":
        if command["type"] == "command_line": return command_line(command["variable"], command["config"])

    if command["component"] == "api":
        if command["type"] == "web": return web(command["variable"], command["config"])

    if command["component"] == "decomposer":
        command["config"]["output"] = task_m
        if command["type"] == "llm": return llm(command["variable"], command["config"])

def main_function():
    components: list[component] = []
    
    commands: dict[name, command] = {}

    current_directory = os.getcwd()
    load_dotenv(dotenv_path=os.path.join(current_directory, '.env'))

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
            # Make to a set
            command["depends_on"] = []
            for item in config_items:
                key = item.split(":")[0].strip()
                value = item.split(":")[1].strip()
                
                # If the value is not a string, it references a variable
                # We replace this variable with a reference to the object
                if value[0] != "\"" and value[0] != "'" and value[0] != '$' and value[0] != "[":
                    # Add variable to depends_on
                    command["depends_on"].append(value)
                
                # If the value starts with $, then it is a secret key in the .env file
                # Replace this with the secret
                elif value[0] == '$':
                    value = os.getenv(value[1::])
                
                # If the value is an array, parse it as an array of references
                elif value[0] == "[":
                    value = list(map(lambda x: x.strip(), value[1:-1:].split(",")))
                    
                    for i in range(len(value)):
                        command["depends_on"].append(value[i])
                    
                    print(f"values = {value}")
                                    
                elif (value[0] == "\"" and value[-1] == "\"") or (value[0] == "\'" and value[-1] == "\'"):
                    value = value[1:-1:]

                command["config"][key] = value
            
            print("[COMMAND]", command)
            commands[command["variable"]] = command
    
    tools = []
    for name in commands.keys():
        dependency_resolver(commands, commands[name])
        tools.append(commands[name]["object"])
    
    task_m.add_tools(tools)
    
    # print("[COMMANDS]", commands)
