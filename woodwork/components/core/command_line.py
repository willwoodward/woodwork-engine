import ast
import importlib
import os

from woodwork.helper_functions import print_debug, format_kwargs
from woodwork.deployments import Docker
from woodwork.components.core.core import core


class command_line(core):
    def __init__(self, **config):
        format_kwargs(config, type="command_line")
        super().__init__(**config)
        print_debug("Configuring Command line...")

        self.docker = Docker(
            image_name="command-line",
            container_name="command-line",
            dockerfile="""
            FROM ubuntu:latest
            RUN apt-get update && apt-get install -y bash
            CMD ["tail", "-f", "/dev/null"]
            """,
            container_args={}
        )
        self.docker.init()

        print_debug("Command line configured.")
    

    def close(self):
        self.docker.close()
    

    def run(self, input: str):
        container = self.docker.get_container()
        out = container.exec_run(input)
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
        return """A command line isolated inside a docker container for use by the agent.
        The function provided is run(input: str), where it executes the command passed as input in a bash terminal.
        To use this, the action is the function name and the inputs are a dictionary of key word arguments for the run function."""
