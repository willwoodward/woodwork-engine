import logging
import os
import re

from woodwork.components.core.core import core
from woodwork.deployments import Docker
from woodwork.helper_functions import format_kwargs

log = logging.getLogger(__name__)


class command_line(core):
    def __init__(self, **config):
        format_kwargs(config, type="command_line")
        super().__init__(**config)
        log.debug("Configuring Command line...")

        self.docker = Docker(
            image_name="command-line",
            container_name="command-line",
            dockerfile="""
            FROM ubuntu:latest
            RUN apt-get update && apt-get install -y bash
            CMD ["tail", "-f", "/dev/null"]
            """,
            container_args={},
            volume_location=".woodwork/vm",
        )
        self.docker.init()
        self.current_directory = "/"

        log.debug("Command line configured.")

    def change_directory(self, new_path):
        if not new_path:
            self.current_directory = "/"
            return

        resolved_path = os.path.abspath(os.path.join(self.current_directory, new_path))
        self.current_directory = resolved_path

    def close(self):
        self.docker.close()

    def run(self, input: str):
        container = self.docker.get_container()

        # Manage directory state
        match = re.fullmatch(r'\s*cd\s+(?:"([^"]+)"|\'([^\']+)\'|(\S+))?\s*', input)
        if match:
            # Extract the directory (from quoted or unquoted groups)
            directory = match.group(1) or match.group(2) or match.group(3) or ""
            self.change_directory(directory)
            return

        out = container.exec_run(f'/bin/sh -c "cd {self.current_directory} && {input}"')
        return out.output.decode("utf-8").strip()

    def input(self, function_name: str, inputs: dict):
        func = None
        if function_name == "run":
            func = self.run

        if func is None:
            return

        return func(**inputs)

    @property
    def description(self):
        return """
        A command line isolated inside a docker container for use by the agent.
        This also comes with a file system that can be manipulated using the command line.
        If you change directory using `cd`, it will keep track of the current directory, as long as the command does nothing else.
        The function provided is run(input: str), where it executes the command passed as input in a bash terminal.
        To use this, the action is the function name and the inputs are a dictionary of key word arguments for the run function."""
