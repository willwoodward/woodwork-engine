import importlib.resources as pkg_resources
import logging
import os
import re
import subprocess
import sys

log = logging.getLogger(__name__)


def setup_virtual_env(options):
    isolated = options["isolated"]

    # Create the virtual environment
    if not os.path.exists(".woodwork/env"):
        log.debug("Setting up a virtual environment...")

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

    venvUsesGlobal(not isolated)


def venvUsesGlobal(glob=False):
    with open(os.getcwd() + "/.woodwork/env/pyvenv.cfg", "r") as f:
        lines = f.read()

        if glob:
            lines = lines.replace(
                "include-system-site-packages = false",
                "include-system-site-packages = true",
            )
        else:
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
        init({"isolated": False, "all": False})

    # Check if we're already in the virtual environment
    if sys.prefix == venv_path:
        log.debug("Virtual environment is already active.")
        return

    # Activate the venv
    subprocess.run('/bin/bash -c "source .woodwork/env/bin/activate"', shell=True, check=True)

    # Adjust sys.path to prioritize the virtual environment
    site_packages = os.path.join(
        venv_path,
        "lib",
        f"python{sys.version_info.major}.{sys.version_info.minor}",
        "site-packages",
    )
    sys.path.insert(0, site_packages)
    log.debug("Virtual environment activated.")


def get_components() -> list[tuple[str, str]]:
    components = set()
    with open(os.getcwd() + "/main.ww", "r") as f:
        lines = f.read()

        entry_pattern = r".+=.+\{[\s\S]*?\}"
        entries = re.findall(entry_pattern, lines)

        for entry in entries:
            component = entry.split("=")[1].split(" ")[1].strip()
            type = entry.split(component)[1].split("{")[0].strip()
            components.add((component, type))

    return list(components)


def parse_requirements_file(requirements_set, file_path):
    if os.path.isfile(file_path):
        with open(file_path, "r") as f:
            for line in f:
                # Remove any comments or empty lines
                cleaned_line = line.strip()
                if cleaned_line and not cleaned_line.startswith("#"):
                    requirements_set.add(cleaned_line)


def get_requirements(components: list, temp_requirements_file: str):
    requirements_set = set()

    # Install dependencies
    # Dependencies stored in requirements/{component}/{type}
    for component, type in components:
        # Access the requirements directory as a package resource
        requirements_dir = pkg_resources.files("woodwork") / "requirements"

        component_requirements = os.path.join(requirements_dir, component, f"{component}.txt")
        try:
            parse_requirements_file(requirements_set, component_requirements)
        except subprocess.CalledProcessError:
            sys.exit(1)

        # Install the component type dependencies
        type_requirements = os.path.join(requirements_dir, component, f"{type}.txt")
        try:
            parse_requirements_file(requirements_set, type_requirements)
        except subprocess.CalledProcessError:
            sys.exit(1)

    # Write combined unique requirements to a temporary file
    with open(temp_requirements_file, "w") as f:
        for requirement in sorted(requirements_set):
            f.write(f"{requirement}\n")


def get_all_requirements(root_dir, output_file):
    # Set to store unique requirements
    all_requirements = set()

    # Walk through the directory structure
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            file_path = os.path.join(root, file)
            parse_requirements_file(all_requirements, file_path)

    # Write the compiled requirements to the output file
    with open(output_file, "w") as f:
        for requirement in sorted(all_requirements):  # Sort for consistency
            f.write(requirement + "\n")


def init(options={"isolated": False, "all": False}):
    # Make sure the virtual environment is set up properly
    setup_virtual_env(options)

    # Change this to work with windows
    activate_script = ".woodwork/env/bin/activate"
    temp_requirements_file = ".woodwork/requirements.txt"

    print("Installing dependencies...")
    if options["all"]:
        get_all_requirements(pkg_resources.files("woodwork") / "requirements", temp_requirements_file)
    else:
        components = get_components()
        get_requirements(components, temp_requirements_file)

    # Install requirements from temporary file
    try:
        subprocess.check_call(
            [f". {activate_script} && uv pip install -r {temp_requirements_file}"],
            shell=True,
        )
        print("Installed all combined dependencies.")
    except subprocess.CalledProcessError:
        sys.exit(1)
    finally:
        # Clean up temporary requirements file
        if os.path.exists(temp_requirements_file):
            os.remove(temp_requirements_file)

    # Now run init() methods on all components

    print("Initialization complete.")
