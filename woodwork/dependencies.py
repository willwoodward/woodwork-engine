import re
import os
import subprocess
import sys

def init():
    print("Initialising dependencies...")
    
    components = set()
    with open(os.getcwd() + "/main.ww", "r") as f:
        lines = f.read()
        
        entry_pattern = r".+=.+\{[\s\S]*?\}"
        entries = re.findall(entry_pattern, lines)

        for entry in entries:
            component = entry.split("=")[1].split(" ")[1].strip()
            type = entry.split(component)[1].split("{")[0].strip()
            components.add((component, type))
    
    components = list(components)
    
    # Install dependencies
    # Dependencies stored in requirements/{component}/{type}
    for (component, type) in components:
        
        #  Install component dependencies first
        import importlib.resources as pkg_resources
        from pathlib import Path

        # Access the requirements directory as a package resource
        requirements_dir = pkg_resources.files('woodwork')/'requirements'
        
        component_requirements = os.path.join(requirements_dir, component, f"{component}.txt")
        try:
            if os.path.isfile(component_requirements):
                subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", component_requirements], stdout=subprocess.DEVNULL)
                print(f"Installed dependencies for {component}.")
        except subprocess.CalledProcessError:
            print(f"Failed to install dependencies for {component}.")
            sys.exit(1)
        
        # Install the component type dependencies
        type_requirements = os.path.join(requirements_dir, component, f"{type}.txt")
        try:
            if os.path.isfile(type_requirements):
                subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", type_requirements], stdout=subprocess.DEVNULL)
                print(f"Installed dependencies for {component}.")
        except subprocess.CalledProcessError:
            sys.exit(1)