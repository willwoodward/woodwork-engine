import re

from components.component import component
from components.knowledge_bases.vector_databases.chroma import chroma
from components.knowledge_bases.graph_databases.neo4j import neo4j

keywords = ["knowledge_base"]
components: list[component] = []

commands = []
with open("main.wf", "r") as f:
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

        command["config"] = {}
        for item in config_items:
            key = item.split(":")[0].strip()
            value = item.split(":")[1].strip()
            command["config"][key] = value

        commands.append(command)



for command in commands:
    if command["component"] == "knowledge_base":
        
        if command["type"] == "chroma": components.append(chroma(command["variable"], command["config"]))
        if command["type"] == "neo4j":  components.append(neo4j(command["variable"], command["config"]))
    

print(components[0])