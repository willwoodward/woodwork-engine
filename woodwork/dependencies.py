import re
import os
import subprocess
import sys
import importlib.resources as pkg_resources

from woodwork.helper_functions import print_debug


def setup_virtual_env(options):
    isolated = options["isolated"]

    # Create the virtual environment
    if not os.path.exists(".woodwork/env"):
        print_debug("Setting up a virtual environment...")

        if isolated:
            subprocess.check_call([sys.executable, "-m", "venv", ".woodwork/env"])
        else:
            subprocess.check_call(
                [
                    sys.executable,
                    "-m",
                    "venv",
                    ".woodwork/env",
                    "--system-site-packages",
                ]
            )

    # Else, enforce the current global packages flag
    with open(os.getcwd() + "/.woodwork/env/pyvenv.cfg", "r") as f:
        lines = f.read()

        if not isolated:
            lines = lines.replace(
                "include-system-site-packages = false",
                "include-system-site-packages = true",
            )
        if isolated:
            lines = lines.replace(
                "include-system-site-packages = true",
                "include-system-site-packages = false",
            )

    with open(os.getcwd() + "/.woodwork/env/pyvenv.cfg", "w") as f:
        f.write(lines)


def activate_virtual_environment():
    # Path to the virtual environment
    venv_path = os.path.join(os.getcwd(), ".woodwork", "env")

    if not os.path.exists(venv_path):
        init({"isolated": False})

    # Check if we're already in the virtual environment
    if sys.prefix == venv_path:
        print_debug("Virtual environment is already active.")
        return

    # Execute the activation script
    # activate_script = os.path.join(venv_path, "bin", "activate")
    # cmd = f"source {activate_script}"

    # Run the command in the virtual environment
    subprocess.run('/bin/bash -c "source .woodwork/env/bin/activate"', shell=True, check=True)

    # Adjust sys.path to prioritize the virtual environment
    site_packages = os.path.join(
        venv_path,
        "lib",
        f"python{sys.version_info.major}.{sys.version_info.minor}",
        "site-packages",
    )
    sys.path.insert(0, site_packages)

    print_debug("Virtual environment activated.")


def parse_requirements(requirements_set, file_path):
    if os.path.isfile(file_path):
        with open(file_path, "r") as f:
            for line in f:
                # Remove any comments or empty lines
                cleaned_line = line.strip()
                if cleaned_line and not cleaned_line.startswith("#"):
                    requirements_set.add(cleaned_line)


def init(options={"isolated": False}):
    # Make sure the virtual environment is set up properly
    setup_virtual_env(options)

    # Change this to work with windows
    activate_script = ".woodwork/env/bin/activate"

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
    requirements_set = set()

    # Install dependencies
    # Dependencies stored in requirements/{component}/{type}
    for component, type in components:
        # Access the requirements directory as a package resource
        requirements_dir = pkg_resources.files("woodwork") / "requirements"

        component_requirements = os.path.join(requirements_dir, component, f"{component}.txt")
        try:
            parse_requirements(requirements_set, component_requirements)
        except subprocess.CalledProcessError:
            sys.exit(1)

        # Install the component type dependencies
        type_requirements = os.path.join(requirements_dir, component, f"{type}.txt")
        try:
            parse_requirements(requirements_set, type_requirements)
        except subprocess.CalledProcessError:
            sys.exit(1)

    # Write combined unique requirements to a temporary file
    temp_requirements_file = ".woodwork/requirements.txt"
    with open(temp_requirements_file, "w") as f:
        for requirement in sorted(requirements_set):
            f.write(f"{requirement}\n")

    try:
        subprocess.check_call(
            [f". {activate_script} && pip install -r {temp_requirements_file}"],
            shell=True,
        )
        print("Installed all combined dependencies.")
    except subprocess.CalledProcessError:
        sys.exit(1)
    finally:
        # Clean up temporary requirements file
        if os.path.exists(temp_requirements_file):
            os.remove(temp_requirements_file)

    print("Initialization complete.")


# This function is for testing
def init_all(options={"isolated": False}):
    # Make sure the virtual environment is set up properly
    setup_virtual_env(options)

    # Change this to work with windows
    activate_script = ".woodwork/env/bin/activate"

    print("Installing dependencies...")
    root_folder = "woodwork/requirements"
    temp_requirements_file = ".woodwork/requirements.txt"
    compile_requirements(root_folder, temp_requirements_file)
    print("Compiled all requirements")

    try:
        subprocess.check_call(
            [f". {activate_script} && pip install -r {temp_requirements_file}"],
            shell=True,
        )
        print("Installed all combined dependencies.")
    except subprocess.CalledProcessError:
        sys.exit(1)
    finally:
        # Clean up temporary requirements file
        if os.path.exists(temp_requirements_file):
            os.remove(temp_requirements_file)

    print("Initialization complete.")


# Also used for testing


def compile_requirements(root_dir, output_file):
    # Set to store unique requirements
    all_requirements = set()

    # Walk through the directory structure
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            file_path = os.path.join(root, file)
            with open(file_path, "r") as f:
                for line in f:
                    requirement = line.strip()
                    if requirement and not requirement.startswith("#"):  # Exclude comments and blank lines
                        all_requirements.add(requirement)

    # Write the compiled requirements to the output file
    with open(output_file, "w") as f:
        for requirement in sorted(all_requirements):  # Sort for consistency
            f.write(requirement + "\n")

    print(f"Compiled requirements saved to {output_file}")


def get_subdirectories(path: str) -> list[str]:
    entries = os.listdir(path)

    # Filter the entries to include only directories
    return [entry for entry in entries if os.path.isdir(os.path.join(path, entry))]


def install_all():
    print("Installing all dependencies...")

    setup_virtual_env({"isolated": True})

    # Change this to work with windows
    activate_script = ".woodwork/env/bin/activate"

    # Access the requirements directory as a package resource
    requirements_dir = pkg_resources.files("woodwork") / "requirements"

    components = get_subdirectories(requirements_dir)
    requirements_set = set()

    for component in components:
        component_requirements = os.path.join(requirements_dir, component, f"{component}.txt")
        try:
            parse_requirements(requirements_set, component_requirements)
        except subprocess.CalledProcessError:
            sys.exit(1)

        # Install the component type dependencies
        type_requirements = os.path.join(requirements_dir, component, f"{type}.txt")
        try:
            parse_requirements(requirements_set, type_requirements)
        except subprocess.CalledProcessError:
            sys.exit(1)

    # Write combined unique requirements to a temporary file
    os.makedirs(".woodwork", exist_ok=True)
    temp_requirements_file = ".woodwork/requirements.txt"
    with open(temp_requirements_file, "w") as f:
        for requirement in sorted(requirements_set):
            f.write(f"{requirement}\n")

    try:
        subprocess.check_call(
            [f". {activate_script} && pip install -r {temp_requirements_file}"],
            shell=True,
        )
        print("Installed all combined dependencies.")
    except subprocess.CalledProcessError:
        sys.exit(1)
    finally:
        # Clean up temporary requirements file
        if os.path.exists(temp_requirements_file):
            os.remove(temp_requirements_file)

    activate_virtual_environment()
    print("Initialization complete.")
