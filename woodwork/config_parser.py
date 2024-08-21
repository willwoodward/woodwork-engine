import re
import os
from dotenv import load_dotenv

from woodwork.components.component import component
from woodwork.components.knowledge_bases.vector_databases.chroma import chroma
from woodwork.components.knowledge_bases.graph_databases.neo4j import neo4j
from woodwork.components.llms.hugging_face import hugging_face
from woodwork.components.inputs.command_line import command_line

def main_function():
    components: list[component] = []

    current_directory = os.getcwd()
    load_dotenv()

    commands = []
    with open(current_directory + "/main.ww", "r") as f:
        lines = f.read()
        
        entry_pattern = r".+=.+\{[\s\S]*?\}"
        entries = re.findall(entry_pattern, lines)

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
                if value[0] != "\"" and value[0] != "'" and value[0] != '$':
                    # Search components for the variable
                    for c in components:
                        if c.name == value:
                            value = c
                            break
                
                # If the value starts with $, then it is a secret key in the .env file
                # Replace this with the secret
                elif value[0] == '$':
                    value = os.getenv(value[1::])

                command["config"][key] = value
        
            # Create the objects specified by the command
            if command["component"] == "knowledge_base":
                if command["type"] == "chroma": components.append(chroma(command["variable"], command["config"]))
                if command["type"] == "neo4j":  components.append(neo4j(command["variable"], command["config"]))
            
            if command["component"] == "llm":
                if command["type"] == "hugging_face": components.append(hugging_face(command["variable"], command["config"]))
            
            if command["component"] == "input":
                if command["type"] == "command_line": components.append(command_line(command["variable"], command["config"]))
