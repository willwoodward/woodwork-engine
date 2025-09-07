import logging
import os
import re
import base64
from typing import Optional

from woodwork.components.environments.environment import environment
from woodwork.deployments import Docker
from woodwork.utils import format_kwargs

log = logging.getLogger(__name__)


class coding(environment):
    def __init__(self, repo_url: Optional[str] = None, local_path: str = "/workspace", 
                 dockerfile: Optional[str] = None, image_name: str = "coding-env", 
                 container_name: str = "coding-env", **config):
        format_kwargs(config, repo_url=repo_url, local_path=local_path, 
                     dockerfile=dockerfile, image_name=image_name, 
                     container_name=container_name, type="coding")
        super().__init__(**config)

        self.repo_url = repo_url
        self.local_path = local_path
        self.vector_db = config.get("vector_db")
        self.embedding_model = config.get("embedding_model")
        self.current_directory = local_path
        self.startup_scripts = config.get("startup_scripts", [])
        self._startup_scripts_run = False
        
        # Default dockerfile with minimal essential tools
        default_dockerfile = """
        FROM ubuntu:latest
        RUN apt-get update && apt-get install -y \\
            bash git curl wget vim nano \\
            build-essential \\
            && rm -rf /var/lib/apt/lists/*
        WORKDIR /workspace
        CMD ["tail", "-f", "/dev/null"]
        """
        
        self.docker = Docker(
            image_name=image_name,
            container_name=container_name,
            dockerfile=dockerfile or default_dockerfile,
            container_args={},
            volume_location=".woodwork/coding-env",
            docker_volume_location=local_path,
        )

        log.debug("Initializing coding environment...")
        self.setup_environment()
        log.debug("Coding environment initialized.")

    def setup_environment(self):
        """Setup the coding environment with repository, tools, and scripts."""
        self.docker.init()
        
        # Clone repository if specified
        if self.repo_url:
            self.clone_repo()
        
        # Set up git configuration
        self.setup_git()
        
        # Run custom setup scripts only if not already done
        self.run_setup_scripts_once()

    def setup_git(self):
        """Setup git with basic configuration only if no setup scripts are provided."""
        # If setup scripts are provided, let them handle git configuration
        if self.setup_scripts:
            log.info("Setup scripts provided - skipping default git configuration")
            return
            
        container = self.docker.get_container()
        
        # Check if git is already configured
        result = container.exec_run("/bin/sh -c 'git config --global user.name || echo NOTSET'")
        if b"NOTSET" in result.output:
            # Set basic git configuration only as fallback
            container.exec_run("/bin/sh -c 'git config --global user.name \"Woodwork Agent\"'")
            container.exec_run("/bin/sh -c 'git config --global user.email \"agent@woodwork.dev\"'")
            container.exec_run("/bin/sh -c 'git config --global init.defaultBranch main'")
            log.info("Default git configuration set up")

    def clone_repo(self):
        """Clone the specified repository if it doesn't already exist."""
        container = self.docker.get_container()
        check_command = f"test -d {self.local_path}/.git"
        result = container.exec_run(f"/bin/sh -c '{check_command}'")
        
        if result.exit_code != 0:
            if self.repo_url.startswith(('http://', 'https://')):
                clone_command = f"git clone {self.repo_url} {self.local_path}"
            else:
                # Assume GitHub format like "user/repo"
                clone_command = f"git clone https://github.com/{self.repo_url}.git {self.local_path}"
            
            out = container.exec_run(f"/bin/sh -c '{clone_command}'")
            log.info(f"Repo cloned: {out.output.decode('utf-8')}")

    def execute_command(self, command: str) -> str:
        """Execute a command in the environment."""
        container = self.docker.get_container()

        # Handle directory changes
        match = re.fullmatch(r'\\s*cd\\s+(?:"([^"]+)"|\'([^\']+)\'|(\\S+))?\\s*', command)
        if match:
            directory = match.group(1) or match.group(2) or match.group(3) or ""
            self.change_directory(directory)
            return f"Changed directory to {self.current_directory}"

        # Run startup scripts if they haven't been run in this session
        self._run_startup_scripts_once()

        out = container.exec_run(f'/bin/sh -c "cd {self.current_directory} && {command}"')
        return out.output.decode("utf-8").strip()

    def change_directory(self, new_path):
        """Change the current working directory."""
        if not new_path:
            self.current_directory = self.local_path
            return

        resolved_path = os.path.abspath(os.path.join(self.current_directory, new_path))
        self.current_directory = resolved_path

    def list_files(self, path: str = ".") -> list:
        """List all files in the specified path."""
        container = self.docker.get_container()
        search_path = f"{self.local_path}/{path}" if path != "." else self.local_path
        command = f"find {search_path} -type f"
        result = container.exec_run(f"/bin/sh -c '{command}'")
        
        if result.exit_code == 0:
            files = result.output.decode("utf-8").strip().splitlines()
            # Return relative paths from repo root
            return [f.replace(f"{self.local_path}/", "") for f in files if f.startswith(self.local_path)]
        return []

    def read_file(self, file_path: str, offset: int = 0, limit: int = 2000) -> str:
        """Read file with line numbers and optional offset/limit."""
        container = self.docker.get_container()
        full_path = f"{self.local_path}/{file_path}"
        
        # Check if file exists
        check_command = f"test -f {full_path}"
        check_result = container.exec_run(f"/bin/sh -c '{check_command}'")
        if check_result.exit_code != 0:
            return f"Error: File '{file_path}' not found"
        
        # Read file content
        command = f"cat {full_path}"
        result = container.exec_run(f"/bin/sh -c '{command}'")
        content = result.output.decode("utf-8")
        
        # Handle empty file
        if not content or content.strip() == "":
            return "System reminder: File exists but has empty contents"
        
        # Split content into lines
        lines = content.splitlines()
        
        # Apply line offset and limit
        start_idx = offset
        end_idx = min(start_idx + limit, len(lines))
        
        # Handle case where offset is beyond file length
        if start_idx >= len(lines):
            return f"Error: Line offset {offset} exceeds file length ({len(lines)} lines)"
        
        # Format output with line numbers (cat -n format)
        result_lines = []
        for i in range(start_idx, end_idx):
            line_content = lines[i]
            
            # Truncate lines longer than 2000 characters
            if len(line_content) > 2000:
                line_content = line_content[:2000]
            
            # Line numbers start at 1, so add 1 to the index
            line_number = i + 1
            result_lines.append(f"{line_number:6d}\\t{line_content}")
        
        return "\\n".join(result_lines)

    def write_file(self, file_path: str, content: str) -> str:
        """Write to a file."""
        container = self.docker.get_container()
        full_path = f"{self.local_path}/{file_path}"
        
        # Create directory if it doesn't exist
        dir_path = "/".join(full_path.split("/")[:-1])
        mkdir_command = f"mkdir -p {dir_path}"
        container.exec_run(f"/bin/sh -c '{mkdir_command}'")
        
        # Use safe writing method
        write_result = self._safe_write_content(full_path, content)
        if write_result == "Success":
            return f"Updated file {file_path}"
        else:
            return f"Error writing to file {file_path}: {write_result}"

    def edit_file(self, file_path: str, old_string: str, new_string: str, replace_all: bool = False):
        """Edit a file by replacing old_string with new_string."""
        container = self.docker.get_container()
        full_path = f"{self.local_path}/{file_path}"
        
        # Check if file exists
        check_command = f"test -f {full_path}"
        check_result = container.exec_run(f"/bin/sh -c '{check_command}'")
        if check_result.exit_code != 0:
            return f"Error: File '{file_path}' not found"
        
        # Read current file content
        read_command = f"cat {full_path}"
        read_result = container.exec_run(f"/bin/sh -c '{read_command}'")
        content = read_result.output.decode("utf-8")
        
        # Check if old_string exists in the file
        if old_string not in content:
            return f"Error: String not found in file: '{old_string}'"
        
        # If not replace_all, check for uniqueness
        if not replace_all:
            occurrences = content.count(old_string)
            if occurrences > 1:
                return f"Error: String '{old_string}' appears {occurrences} times in file. Use replace_all=True to replace all instances, or provide a more specific string with surrounding context."
            elif occurrences == 0:
                return f"Error: String not found in file: '{old_string}'"
        
        # Perform the replacement
        if replace_all:
            new_content = content.replace(old_string, new_string)
            replacement_count = content.count(old_string)
            result_msg = f"Successfully replaced {replacement_count} instance(s) of the string in '{file_path}'"
        else:
            new_content = content.replace(old_string, new_string, 1)  # Replace only first occurrence
            result_msg = f"Successfully replaced string in '{file_path}'"
        
        # Use safe writing method
        write_result = self._safe_write_content(full_path, new_content)
        if write_result == "Success":
            return result_msg
        else:
            return f"Error writing to file {file_path}: {write_result}"

    def multi_edit(self, file_path: str, edits: list):
        """Apply multiple string replacements atomically to a single file."""
        container = self.docker.get_container()
        full_path = f"{self.local_path}/{file_path}"
        
        # Check if file exists
        check_command = f"test -f {full_path}"
        check_result = container.exec_run(f"/bin/sh -c '{check_command}'")
        if check_result.exit_code != 0:
            return f"Error: File '{file_path}' not found"
        
        # Create automatic backup before making changes
        backup_result = self.backup_file(file_path)
        if backup_result.startswith("Error"):
            return f"Failed to create backup: {backup_result}"
        
        # Read current file content
        read_command = f"cat {full_path}"
        read_result = container.exec_run(f"/bin/sh -c '{read_command}'")
        original_content = read_result.output.decode("utf-8")
        
        # Validate all edits first before applying any
        for i, edit in enumerate(edits):
            if not isinstance(edit, dict) or 'old_string' not in edit or 'new_string' not in edit:
                return f"Error: Edit {i+1} must be a dict with 'old_string' and 'new_string' keys"
            
            old_string = edit['old_string']
            replace_all = edit.get('replace_all', False)
            
            if old_string not in original_content:
                return f"Error: String not found in file for edit {i+1}: '{old_string}'"
            
            if not replace_all:
                occurrences = original_content.count(old_string)
                if occurrences > 1:
                    return f"Error: Edit {i+1} - String '{old_string}' appears {occurrences} times in file. Use replace_all=True to replace all instances, or provide a more specific string with surrounding context."
        
        # Apply all edits sequentially on a working copy
        modified_content = original_content
        total_replacements = 0
        
        for edit in edits:
            old_string = edit['old_string']
            new_string = edit['new_string']
            replace_all = edit.get('replace_all', False)
            
            if replace_all:
                replacement_count = modified_content.count(old_string)
                modified_content = modified_content.replace(old_string, new_string)
                total_replacements += replacement_count
            else:
                modified_content = modified_content.replace(old_string, new_string, 1)
                total_replacements += 1
        
        # Write using atomic operation
        temp_file = f"{full_path}.tmp"
        try:
            write_result = self._safe_write_content(temp_file, modified_content)
            if write_result.startswith("Error"):
                return write_result
            
            # Atomically move temp file to final location
            move_command = f"mv {temp_file} {full_path}"
            move_result = container.exec_run(f"/bin/sh -c '{move_command}'")
            
            if move_result.exit_code == 0:
                return f"Successfully applied {len(edits)} edits with {total_replacements} total replacements to '{file_path}'"
            else:
                return f"Error moving temp file: {move_result.output.decode('utf-8')}"
                
        except Exception as e:
            # Clean up temp file on error
            container.exec_run(f"/bin/sh -c 'rm -f {temp_file}'")
            return f"Error during atomic write: {str(e)}"

    def _safe_write_content(self, full_path: str, content: str):
        """Safely write content to a file using base64 encoding to avoid shell issues."""
        container = self.docker.get_container()
        
        try:
            # Encode content as base64 to avoid shell escaping issues
            encoded_content = base64.b64encode(content.encode('utf-8')).decode('ascii')
            
            # Write using base64 decoding
            write_command = f"echo '{encoded_content}' | base64 -d > {full_path}"
            result = container.exec_run(f"/bin/sh -c '{write_command}'")
            
            if result.exit_code == 0:
                return "Success"
            else:
                return f"Error writing file: {result.output.decode('utf-8')}"
                
        except Exception as e:
            return f"Error encoding content: {str(e)}"

    def search_in_files(self, pattern: str, file_glob: str = "*", context_lines: int = 0, case_insensitive: bool = False):
        """Search for regex patterns in files with optional context lines."""
        container = self.docker.get_container()
        
        # Build grep command
        grep_flags = ["-n"]  # Show line numbers
        if case_insensitive:
            grep_flags.append("-i")
        if context_lines > 0:
            grep_flags.append(f"-C {context_lines}")
        
        # Escape pattern for shell
        escaped_pattern = pattern.replace("'", "'\"'\"'")
        
        # Build find command for file matching
        if file_glob == "*":
            find_part = f"find {self.local_path} -type f"
        else:
            # Convert glob to find pattern
            if "**" in file_glob:
                # Recursive glob
                find_part = f"find {self.local_path} -type f -name '{file_glob.replace('**/', '')}'"
            else:
                find_part = f"find {self.local_path} -type f -name '{file_glob}'"
        
        # Combine find and grep
        command = f"{find_part} -exec grep {' '.join(grep_flags)} '{escaped_pattern}' {{}} +"
        
        result = container.exec_run(f"/bin/sh -c '{command}'")
        output = result.output.decode("utf-8")
        
        if result.exit_code == 0:
            # Process output to make paths relative
            lines = output.strip().splitlines()
            processed_lines = []
            for line in lines:
                if line.startswith(self.local_path):
                    relative_line = line.replace(f"{self.local_path}/", "", 1)
                    processed_lines.append(relative_line)
                else:
                    processed_lines.append(line)
            return "\\n".join(processed_lines)
        elif result.exit_code == 1:
            return "No matches found"
        else:
            return f"Search error: {output}"

    def find_files(self, pattern: str, path: str = "."):
        """Find files matching glob patterns."""
        container = self.docker.get_container()
        search_path = f"{self.local_path}/{path}" if path != "." else self.local_path
        
        if "**" in pattern:
            # Recursive search
            file_pattern = pattern.replace("**/", "")
            command = f"find {search_path} -type f -name '{file_pattern}'"
        else:
            # Non-recursive search  
            command = f"find {search_path} -maxdepth 1 -type f -name '{pattern}'"
        
        result = container.exec_run(f"/bin/sh -c '{command}'")
        
        if result.exit_code == 0:
            files = result.output.decode("utf-8").strip().splitlines()
            # Return relative paths from repo root
            relative_files = []
            for f in files:
                if f.startswith(self.local_path):
                    relative_files.append(f.replace(f"{self.local_path}/", "", 1))
            return relative_files
        else:
            return []

    def backup_file(self, file_path: str):
        """Create a timestamped backup of a file."""
        container = self.docker.get_container()
        full_path = f"{self.local_path}/{file_path}"
        
        # Check if file exists
        check_command = f"test -f {full_path}"
        check_result = container.exec_run(f"/bin/sh -c '{check_command}'")
        if check_result.exit_code != 0:
            return f"Error: File '{file_path}' not found"
        
        # Create backup with timestamp
        timestamp_command = "date +%Y%m%d_%H%M%S"
        timestamp_result = container.exec_run(f"/bin/sh -c '{timestamp_command}'")
        timestamp = timestamp_result.output.decode("utf-8").strip()
        
        backup_path = f"{full_path}.backup_{timestamp}"
        copy_command = f"cp {full_path} {backup_path}"
        copy_result = container.exec_run(f"/bin/sh -c '{copy_command}'")
        
        if copy_result.exit_code == 0:
            relative_backup = backup_path.replace(f"{self.local_path}/", "", 1)
            return f"Backup created: {relative_backup}"
        else:
            return f"Error creating backup: {copy_result.output.decode('utf-8')}"

    def restore_backup(self, file_path: str, backup_name: str):
        """Restore a file from backup."""
        container = self.docker.get_container()
        full_path = f"{self.local_path}/{file_path}"
        backup_full_path = f"{self.local_path}/{backup_name}"
        
        # Check if backup exists
        check_command = f"test -f {backup_full_path}"
        check_result = container.exec_run(f"/bin/sh -c '{check_command}'")
        if check_result.exit_code != 0:
            return f"Error: Backup file '{backup_name}' not found"
        
        # Copy backup to original location
        copy_command = f"cp {backup_full_path} {full_path}"
        copy_result = container.exec_run(f"/bin/sh -c '{copy_command}'")
        
        if copy_result.exit_code == 0:
            return f"Successfully restored '{file_path}' from backup '{backup_name}'"
        else:
            return f"Error restoring backup: {copy_result.output.decode('utf-8')}"

    def sync_to_vector_db(self):
        """Sync code to vector database if configured."""
        if not self.vector_db or not self.embedding_model:
            return "Vector DB or embedding model not configured. Skipping sync."

        container = self.docker.get_container()
        find_command = f"find {self.local_path} -name '*.py'"
        result = container.exec_run(f"/bin/sh -c '{find_command}'")
        file_paths = result.output.decode("utf-8").strip().splitlines()

        for file_path in file_paths:
            read_command = f"cat {file_path}"
            content = container.exec_run(f"/bin/sh -c '{read_command}'").output.decode("utf-8")

            for chunk in self._chunk_code(content):
                vector = self.embedding_model.get_embedding(chunk)
                self.vector_db.upsert(id=hash(chunk), embedding=vector, metadata={"path": file_path})

        return "Code synced to vector database"

    def run_setup_scripts_once(self):
        """Run setup scripts only if they haven't been run before."""
        container = self.docker.get_container()
        setup_marker = "/workspace/.woodwork_setup_complete"
        
        # Check if the first setup script is to remove the marker (force rerun)
        if self.setup_scripts and self.setup_scripts[0].startswith("rm -f /workspace/.woodwork_setup_complete"):
            log.info("Force setup rerun detected, removing completion marker...")
            container.exec_run(f"/bin/sh -c 'rm -f {setup_marker}'")
        else:
            # Check if setup has already been completed
            check_command = f"test -f {setup_marker}"
            result = container.exec_run(f"/bin/sh -c '{check_command}'")
            
            if result.exit_code == 0:
                log.info("Setup scripts already completed, skipping...")
                return
        
        log.info("Running setup scripts for first time...")
        
        # Prepare environment variables from config
        env_vars = {}
        env_vars.update(self.environment_variables)
        log.info(f"Environment variables for setup: {env_vars}")
        
        # Copy any local setup script files to the container
        self._copy_setup_files()
        
        # Run the setup scripts (file paths only)
        for script_path in self.setup_scripts:
            if isinstance(script_path, str):
                # Execute script file with environment variables
                result = self._execute_script_with_env(script_path, env_vars)
                log.info(f"Setup script result: {result}")
        
        # Mark setup as complete
        container.exec_run(f"/bin/sh -c 'touch {setup_marker}'")
        log.info("Setup scripts completed and marked as done")

    def _copy_setup_files(self):
        """Copy setup script files from host to container if they exist locally."""
        import os
        import tarfile
        import io
        
        container = self.docker.get_container()
        
        # Check for setup script files that need to be copied
        for script_path in self.setup_scripts:
            if isinstance(script_path, str):
                # Extract script filename for local lookup
                script_name = script_path.split('/')[-1]
                local_script_path = script_name  # Look in current directory
                
                if os.path.exists(local_script_path):
                    log.info(f"Copying setup script {local_script_path} to container...")
                    
                    # Read the script content
                    with open(local_script_path, 'r') as f:
                        script_content = f.read()
                    
                    # Create a tar archive in memory
                    tar_stream = io.BytesIO()
                    with tarfile.open(mode='w', fileobj=tar_stream) as tar:
                        tarinfo = tarfile.TarInfo(name=script_name)
                        tarinfo.size = len(script_content.encode('utf-8'))
                        tarinfo.mode = 0o755  # Make executable
                        tar.addfile(tarinfo, io.BytesIO(script_content.encode('utf-8')))
                    
                    tar_stream.seek(0)
                    
                    # Copy to container
                    container.put_archive(path='/workspace', data=tar_stream.read())
                    log.info(f"Successfully copied {script_name} to /workspace/{script_name}")

    def _execute_script_with_env(self, script_path: str, env_vars: dict) -> str:
        """Execute a script file with specific environment variables."""
        container = self.docker.get_container()
        
        # Build environment variable string, properly escaping values
        env_parts = []
        for key, value in env_vars.items():
            if value is not None:
                # Escape single quotes in the value
                escaped_value = str(value).replace("'", "'\"'\"'")
                env_parts.append(f"{key}='{escaped_value}'")
        env_string = " ".join(env_parts)
        
        # Execute script file with environment variables
        full_command = f'cd {self.current_directory} && {env_string} {script_path}'
        log.info(f"Executing script with env: {full_command}")
        out = container.exec_run(f'/bin/sh -c "{full_command}"')
        result = out.output.decode("utf-8").strip()
        log.info(f"Script result (exit_code={out.exit_code}): {result}")
        return result

    def _run_startup_scripts_once(self):
        """Run startup scripts only if they haven't been run in this session."""
        if self._startup_scripts_run or not self.startup_scripts:
            return
            
        log.info("Running startup scripts...")
        
        # Prepare environment variables from config
        env_vars = {}
        env_vars.update(self.environment_variables)
        log.info(f"Environment variables for startup: {env_vars}")
        
        # Copy any local startup script files to the container
        self._copy_startup_files()
        
        # Run the startup scripts (file paths only)
        for script_path in self.startup_scripts:
            if isinstance(script_path, str):
                # Execute script file with environment variables
                result = self._execute_script_with_env(script_path, env_vars)
                log.info(f"Startup script result: {result}")
        
        # Mark startup scripts as run for this session
        self._startup_scripts_run = True
        log.info("Startup scripts completed")

    def _copy_startup_files(self):
        """Copy startup script files from host to container if they exist locally."""
        import os
        import tarfile
        import io
        
        container = self.docker.get_container()
        
        # Check for startup script files that need to be copied
        for script_path in self.startup_scripts:
            if isinstance(script_path, str):
                # Extract script filename for local lookup
                script_name = script_path.split('/')[-1]
                local_script_path = script_name  # Look in current directory
                
                if os.path.exists(local_script_path):
                    log.info(f"Copying startup script {local_script_path} to container...")
                    
                    # Read the script content
                    with open(local_script_path, 'r') as f:
                        script_content = f.read()
                    
                    # Create a tar archive in memory
                    tar_stream = io.BytesIO()
                    with tarfile.open(mode='w', fileobj=tar_stream) as tar:
                        tarinfo = tarfile.TarInfo(name=script_name)
                        tarinfo.size = len(script_content.encode('utf-8'))
                        tarinfo.mode = 0o755  # Make executable
                        tar.addfile(tarinfo, io.BytesIO(script_content.encode('utf-8')))
                    
                    tar_stream.seek(0)
                    
                    # Copy to container
                    container.put_archive(path='/workspace', data=tar_stream.read())
                    log.info(f"Successfully copied {script_name} to /workspace/{script_name}")

    def force_setup_rerun(self):
        """Force setup scripts to run again by removing the completion marker."""
        container = self.docker.get_container()
        setup_marker = "/workspace/.woodwork_setup_complete"
        container.exec_run(f"/bin/sh -c 'rm -f {setup_marker}'")
        log.info("Setup completion marker removed - scripts will run on next initialization")

    def _chunk_code(self, text, max_length=500):
        """Chunk code into smaller pieces for embedding."""
        return [text[i : i + max_length] for i in range(0, len(text), max_length)]

    def close(self):
        """Clean up the environment."""
        if hasattr(self, 'docker'):
            self.docker.close()

    def input(self, function_name: str, inputs: dict):
        """Handle tool interface inputs."""
        functions = {
            "execute_command": self.execute_command,
            "run": self.execute_command,  # Alias for backward compatibility
            "list_files": self.list_files,
            "ls": self.list_files,  # Alias
            "read_file": self.read_file,
            "write_file": self.write_file,
            "edit_file": self.edit_file,
            "multi_edit": self.multi_edit,
            "search_in_files": self.search_in_files,
            "find_files": self.find_files,
            "backup_file": self.backup_file,
            "restore_backup": self.restore_backup,
            "sync_to_vector_db": self.sync_to_vector_db,
            "sync": self.sync_to_vector_db,  # Alias
            "force_setup_rerun": self.force_setup_rerun,
        }

        func = functions.get(function_name)
        if func:
            return func(**inputs)

    @property
    def description(self):
        return """
        The `coding` environment provides a complete development environment with file system access, command-line tools, and version control.
        This environment runs in an isolated Docker container and can be configured with custom setup scripts.
        
        FEATURES:
        - File system operations (read, write, edit, search)
        - Command-line execution with directory state management
        - Git repository cloning and management
        - Custom environment setup via scripts
        - Atomic file editing with backup/restore capabilities
        - Code search and pattern matching
        - Vector database integration for code embeddings
        
        SETUP CONFIGURATION:
        - setup_scripts: List of scripts/commands to run during initialization
        - environment_variables: Environment variables to set
        - repo_url: Git repository to clone (GitHub format "user/repo" or full URL)
        - local_path: Working directory path (default: /workspace)
        - dockerfile: Custom Dockerfile for the environment
        
        Functions:
        - execute_command(command): Execute shell commands with directory state tracking
        - list_files(path="."): List all files in specified path
        - read_file(file_path, offset=0, limit=2000): Read file with line numbers and pagination
        - write_file(file_path, content): Write content to file, creating directories as needed
        - edit_file(file_path, old_string, new_string, replace_all=False): Replace text in file
        - multi_edit(file_path, edits): Apply multiple edits atomically
        - search_in_files(pattern, file_glob="*", context_lines=0, case_insensitive=False): Search patterns in files
        - find_files(pattern, path="."): Find files matching glob patterns
        - backup_file(file_path): Create timestamped backup
        - restore_backup(file_path, backup_name): Restore file from backup
        - sync_to_vector_db(): Sync code to vector database for semantic search
        """