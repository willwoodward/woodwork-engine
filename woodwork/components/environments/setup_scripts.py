"""
Setup script utilities for environment components.
Provides common setup patterns and script management.
"""

import logging
import json
from typing import List, Dict, Union, Callable

log = logging.getLogger(__name__)


class SetupScriptManager:
    """Manages and executes setup scripts for environments."""
    
    def __init__(self, environment):
        self.environment = environment
        
    def create_python_setup(self, requirements_file: str = "requirements.txt", 
                          python_version: str = "3.9") -> str:
        """Generate a Python environment setup script."""
        return f"""#!/bin/bash
# Python development environment setup
echo "Setting up Python {python_version} environment..."

# Install Python and pip
apt-get update
apt-get install -y python{python_version} python{python_version}-pip python{python_version}-venv

# Create virtual environment
python{python_version} -m venv /workspace/venv
source /workspace/venv/bin/activate

# Install requirements if they exist
if [ -f "{requirements_file}" ]; then
    pip install -r {requirements_file}
    echo "Requirements installed from {requirements_file}"
fi

# Make venv activation persistent
echo 'source /workspace/venv/bin/activate' >> ~/.bashrc

echo "Python environment setup complete!"
"""

    def create_node_setup(self, node_version: str = "18") -> str:
        """Generate a Node.js environment setup script."""
        return f"""#!/bin/bash
# Node.js development environment setup
echo "Setting up Node.js {node_version} environment..."

# Install Node.js
curl -fsSL https://deb.nodesource.com/setup_{node_version}.x | bash -
apt-get install -y nodejs

# Install yarn
npm install -g yarn

# Install dependencies if package.json exists
if [ -f "package.json" ]; then
    npm install
    echo "Dependencies installed from package.json"
fi

echo "Node.js environment setup complete!"
"""

    def create_docker_setup(self) -> str:
        """Generate Docker setup script."""
        return """#!/bin/bash
# Docker setup
echo "Setting up Docker..."

# Install Docker
apt-get update
apt-get install -y apt-transport-https ca-certificates curl gnupg lsb-release
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io

# Install Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

echo "Docker setup complete!"
"""

    def create_git_setup(self, user_name: str = "Woodwork Agent", 
                        user_email: str = "agent@woodwork.dev") -> str:
        """Generate Git configuration setup script."""
        return f"""#!/bin/bash
# Git setup
echo "Configuring Git..."

git config --global user.name "{user_name}"
git config --global user.email "{user_email}"
git config --global init.defaultBranch main
git config --global pull.rebase false
git config --global core.editor nano

echo "Git configuration complete!"
"""

    def create_database_setup(self, db_type: str = "postgresql") -> str:
        """Generate database setup script."""
        if db_type.lower() == "postgresql":
            return """#!/bin/bash
# PostgreSQL setup
echo "Setting up PostgreSQL..."

apt-get update
apt-get install -y postgresql postgresql-contrib
systemctl start postgresql
systemctl enable postgresql

echo "PostgreSQL setup complete!"
"""
        elif db_type.lower() == "mysql":
            return """#!/bin/bash
# MySQL setup
echo "Setting up MySQL..."

apt-get update
apt-get install -y mysql-server
systemctl start mysql
systemctl enable mysql

echo "MySQL setup complete!"
"""
        elif db_type.lower() == "mongodb":
            return """#!/bin/bash
# MongoDB setup
echo "Setting up MongoDB..."

wget -qO - https://www.mongodb.org/static/pgp/server-6.0.asc | apt-key add -
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu focal/mongodb-org/6.0 multiverse" | tee /etc/apt/sources.list.d/mongodb-org-6.0.list
apt-get update
apt-get install -y mongodb-org
systemctl start mongod
systemctl enable mongod

echo "MongoDB setup complete!"
"""
        else:
            return f"# Unsupported database type: {db_type}"

    def create_custom_setup(self, commands: List[str], description: str = "Custom setup") -> str:
        """Create a custom setup script from a list of commands."""
        script_lines = [
            "#!/bin/bash",
            f"# {description}",
            f'echo "Running {description}..."',
            "",
        ]
        
        for command in commands:
            script_lines.append(command)
        
        script_lines.extend([
            "",
            f'echo "{description} complete!"'
        ])
        
        return "\\n".join(script_lines)

    def save_and_execute_script(self, script_content: str, script_name: str) -> str:
        """Save a script to the environment and execute it."""
        script_path = f"/workspace/setup_scripts/{script_name}"
        
        # Create scripts directory
        self.environment.execute_command("mkdir -p /workspace/setup_scripts")
        
        # Write script
        write_result = self.environment.write_file(f"setup_scripts/{script_name}", script_content)
        if "Error" in write_result:
            return f"Failed to write script: {write_result}"
        
        # Make executable
        self.environment.execute_command(f"chmod +x {script_path}")
        
        # Execute script
        result = self.environment.execute_command(f"bash {script_path}")
        
        log.info(f"Executed setup script {script_name}: {result}")
        return result


def get_common_setups() -> Dict[str, Callable]:
    """Return a dictionary of common setup script generators."""
    manager = SetupScriptManager(None)  # Will be set when used
    
    return {
        "python": manager.create_python_setup,
        "node": manager.create_node_setup,
        "nodejs": manager.create_node_setup,
        "docker": manager.create_docker_setup,
        "git": manager.create_git_setup,
        "postgresql": lambda: manager.create_database_setup("postgresql"),
        "mysql": lambda: manager.create_database_setup("mysql"),
        "mongodb": lambda: manager.create_database_setup("mongodb"),
    }


def parse_setup_config(setup_config: Union[str, List, Dict]) -> List[Dict]:
    """Parse various setup configuration formats into a standardized format."""
    if isinstance(setup_config, str):
        # Single script path or command
        return [{"type": "command", "command": setup_config}]
    
    elif isinstance(setup_config, list):
        # List of scripts/commands
        parsed = []
        for item in setup_config:
            if isinstance(item, str):
                parsed.append({"type": "command", "command": item})
            elif isinstance(item, dict):
                parsed.append(item)
        return parsed
    
    elif isinstance(setup_config, dict):
        # Single script configuration
        return [setup_config]
    
    else:
        return []