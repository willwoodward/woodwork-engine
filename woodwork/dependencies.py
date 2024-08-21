import re
import os
import subprocess
import sys
import importlib.resources as pkg_resources

def setup_virtual_env(options):
    isolated = options["isolated"]

    # Create the virtual environment    
    if not os.path.exists('.woodwork/env'):
        print("Setting up a virtual environment...")
        
        if isolated:
            subprocess.check_call([sys.executable, '-m', 'venv', '.woodwork/env'])
        else:
            subprocess.check_call([sys.executable, '-m', 'venv', '.woodwork/env', '--system-site-packages'])

    # Else, enforce the current global packages flag
    with open(os.getcwd() + "/.woodwork/env/pyvenv.cfg", "r") as f:
        lines = f.read()
                
        if not isolated:
            lines = lines.replace("include-system-site-packages = false", "include-system-site-packages = true")
        if isolated:
            lines = lines.replace("include-system-site-packages = true", "include-system-site-packages = false")
        
    with open(os.getcwd() + "/.woodwork/env/pyvenv.cfg", "w") as f:
        f.write(lines)





def activate_virtual_environment():
    # Path to the virtual environment
    venv_path = os.path.join(os.getcwd(), '.woodwork', 'env')
    
    if not os.path.exists(venv_path):
        setup_virtual_env({"isolated": False})

    # Check if we're already in the virtual environment
    if sys.prefix == venv_path:
        print("Virtual environment is already active.")
        return

    # Execute the activation script
    activate_script = os.path.join(venv_path, 'bin', 'activate')
    cmd = f'source {activate_script}'
    
    # Run the command in the virtual environment
    subprocess.run(f"/bin/bash -c \"source .woodwork/env/bin/activate\"", shell=True, check=True)

    # Adjust sys.path to prioritize the virtual environment
    site_packages = os.path.join(venv_path, 'lib', f'python{sys.version_info.major}.{sys.version_info.minor}', 'site-packages')
    sys.path.insert(0, site_packages)

    print("Virtual environment activated.")





def init(options={"isolated": False}):
    # Make sure the virtual environment is set up properly
    setup_virtual_env(options)
   
    # Change this to work with windows
    activate_script = '.woodwork/env/bin/activate'
    
    print("Installing dependencies...")
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
        # Access the requirements directory as a package resource
        requirements_dir = pkg_resources.files('woodwork')/'requirements'
        
        component_requirements = os.path.join(requirements_dir, component, f"{component}.txt")
        try:
            if os.path.isfile(component_requirements):
                subprocess.check_call([f". {activate_script} && pip install -r {component_requirements}"], shell=True)
                print(f"Installed dependencies for {component}.")
        except subprocess.CalledProcessError:
            sys.exit(1)
        
        # Install the component type dependencies
        type_requirements = os.path.join(requirements_dir, component, f"{type}.txt")
        try:
            if os.path.isfile(type_requirements):
                subprocess.check_call([f". {activate_script} && pip install -r {type_requirements}"], shell=True)
                print(f"Installed dependencies for {component}.")
        except subprocess.CalledProcessError:
            sys.exit(1)

    print("Initialization complete.")