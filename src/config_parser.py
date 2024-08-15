from components.knowledge_bases.chroma import chroma

keywords = ["knowledge_base"]
components = []

line = []
with open("main.wf", "r") as f:
    lines = list(map(lambda line: line.strip("\n"), f.readlines()))
    
for line in lines:
    if "knowledge_base" in line:
        # The name is everything before the equals sign with the whitespace removed either side
        # Add error handling for spaces
        name = line.split("=")[0].strip()
        type = line.split("knowledge_base")[1].strip().strip("{").strip("}")
        
        if type == "chroma ":
            components.append(chroma(name))