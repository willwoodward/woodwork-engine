from abc import ABC, abstractmethod
from woodwork.components.component import component
from woodwork.interfaces.tool_interface import tool_interface
from woodwork.utils import format_kwargs


class environment(component, tool_interface, ABC):
    def __init__(self, **config):
        format_kwargs(config, component="environment")
        super().__init__(**config)
        
        self.setup_scripts = config.get("setup_scripts", [])
        self.environment_variables = config.get("environment_variables", {})
        self.working_directory = config.get("working_directory", "/workspace")
        
    @abstractmethod
    def setup_environment(self):
        """Setup the environment with necessary tools and dependencies."""
        pass
    
    @abstractmethod
    def close(self):
        """Clean up the environment."""
        pass
    
    # Optional methods that environments can implement as needed
    def execute_command(self, command: str) -> str:
        """Execute a command in the environment."""
        raise NotImplementedError("Command execution not supported in this environment")
    
    def list_files(self, path: str = ".") -> list:
        """List files in the environment."""
        raise NotImplementedError("File listing not supported in this environment")
    
    def read_file(self, file_path: str, offset: int = 0, limit: int = 2000) -> str:
        """Read a file from the environment."""
        raise NotImplementedError("File reading not supported in this environment")
    
    def write_file(self, file_path: str, content: str) -> str:
        """Write content to a file in the environment."""
        raise NotImplementedError("File writing not supported in this environment")
    
    def run_setup_scripts(self):
        """Run all setup scripts in order."""
        for script in self.setup_scripts:
            if isinstance(script, str):
                # Execute script path or command
                result = self.execute_command(script)
                print(f"Setup script result: {result}")
            elif isinstance(script, dict):
                # Handle script with additional configuration
                script_path = script.get("path") or script.get("command")
                env_vars = script.get("env", {})
                
                # Set environment variables for this script
                for key, value in env_vars.items():
                    self.execute_command(f"export {key}='{value}'")
                
                result = self.execute_command(script_path)
                print(f"Setup script {script_path} result: {result}")