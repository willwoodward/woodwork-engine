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
            """,
            container_args={}
        )

        print_debug("Command line configured.")
    

    def run(self, input: str):
        self.docker.exec_run(input)


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
