import importlib.resources as pkg_resources
import logging
import os
import subprocess
import sys

log = logging.getLogger(__name__)

REQUIREMENTS_DIR = pkg_resources.files("woodwork") / "parser" / "requirements"


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

    # Remove ALL site-packages from sys.path except the one we're about to add
    # This prevents conflicts with parent venv or system packages
    original_paths = sys.path.copy()
    sys.path[:] = [p for p in sys.path if "site-packages" not in p]

    # Add the project virtual environment site-packages
    site_packages = os.path.join(
        venv_path,
        "lib",
        f"python{sys.version_info.major}.{sys.version_info.minor}",
        "site-packages",
    )
    sys.path.insert(0, site_packages)

    removed_paths = [p for p in original_paths if "site-packages" in p]
    log.debug("Virtual environment activated. Removed all site-packages paths: %s", removed_paths)


def get_components() -> list[tuple[str, str]]:
    """Extract components from main.ww file.

    Uses the shared parsing logic from config_parser to ensure consistency.

    Returns:
        List of (component, type) tuples. Example: [('llm', 'openai'), ('input', 'keyword_voice')]
    """
    from woodwork.config.tokenizer import get_declarations, parse_component_declaration

    components = set()
    with open(os.getcwd() + "/main.ww", "r") as f:
        lines = f.read()

        # Use the same declaration extraction as the main parser
        entries = get_declarations(lines)

        for entry, line_number in entries:
            variable, component, type_name = parse_component_declaration(entry)
            components.add((component, type_name))

    return list(components)


def parse_requirements_file(requirements_set, file_path):
    if os.path.isfile(file_path):
        log.debug(f"Found requirements file: {file_path}")
        with open(file_path, "r") as f:
            for line in f:
                # Remove any comments or empty lines
                cleaned_line = line.strip()
                if cleaned_line and not cleaned_line.startswith("#"):
                    requirements_set.add(cleaned_line)
                    log.debug(f"  Added requirement: {cleaned_line}")
    else:
        log.debug(f"Requirements file not found: {file_path}")


def get_requirements(components: list, temp_requirements_file: str):
    requirements_set = set()

    # Install dependencies
    # Dependencies stored in requirements/{component}/{type}
    for component, type in components:
        log.debug(f"Processing component: {component}, type: {type}")

        # Access the requirements directory as a package resource
        component_requirements = os.path.join(REQUIREMENTS_DIR, component, f"{component}.txt")
        log.debug(f"Looking for component requirements: {component_requirements}")
        try:
            parse_requirements_file(requirements_set, component_requirements)
        except subprocess.CalledProcessError:
            sys.exit(1)

        # Install the component type dependencies
        type_requirements = os.path.join(REQUIREMENTS_DIR, component, f"{type}.txt")
        log.debug(f"Looking for type requirements: {type_requirements}")
        try:
            parse_requirements_file(requirements_set, type_requirements)
        except subprocess.CalledProcessError:
            sys.exit(1)

    log.debug(f"Collected requirements: {sorted(requirements_set)}")

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
    from rich.console import Console

    console = Console()

    # Make sure the virtual environment is set up properly
    setup_virtual_env(options)

    # Change this to work with windows
    activate_script = ".woodwork/env/bin/activate"
    temp_requirements_file = ".woodwork/requirements.txt"

    console.print("Installing dependencies...", style="dim", highlight=False)
    if options["all"]:
        get_all_requirements(REQUIREMENTS_DIR, temp_requirements_file)
    else:
        components = get_components()
        console.print(f"Detected components: {components}", style="dim", highlight=False)
        get_requirements(components, temp_requirements_file)

    # Install requirements from temporary file
    try:
        subprocess.check_call(
            [f". {activate_script} && uv pip install -r {temp_requirements_file}"],
            shell=True,
        )
        console.print("Installed all combined dependencies.", style="dim", highlight=False)
    except subprocess.CalledProcessError:
        sys.exit(1)
    finally:
        # Clean up temporary requirements file
        if os.path.exists(temp_requirements_file):
            os.remove(temp_requirements_file)

    # Now run init() methods on all components

    console.print("Initialization complete.", style="dim", highlight=False)
