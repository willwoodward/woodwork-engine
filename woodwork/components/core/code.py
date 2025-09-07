from woodwork.components.core.core import core
from woodwork.utils import format_kwargs


class code(core):
    def __init__(self, container, repo_url: str, **config):
        format_kwargs(config, container=container, repo_url=repo_url, type="code")
        super().__init__(**config)

        # Required components
        self.docker = container.docker
        self.repo_url = repo_url
        self.local_path = config.get("local_path", "/home/ubuntu/repo")
        self.vector_db = config.get("vector_db")
        self.embedding_model = config.get("embedding_model")
        self.clone_repo()

    def clone_repo(self):
        container = self.docker.get_container()
        check_command = f"test -d {self.local_path}/.git"
        result = container.exec_run(f"/bin/sh -c '{check_command}'")
        if result.exit_code != 0:
            clone_command = f"git clone https://github.com/{self.repo_url}.git {self.local_path}"
            out = container.exec_run(f"/bin/sh -c '{clone_command}'")
            print("Repo cloned: " + out.output.decode("utf-8"))

    def sync_to_vector_db(self):
        if not self.vector_db or not self.embedding_model:
            print("Vector DB or embedding model not configured. Skipping sync.")
            return

        container = self.docker.get_container()
        find_command = f"find {self.local_path} -name '*.py'"
        result = container.exec_run(f"/bin/sh -c '{find_command}'")
        file_paths = result.output.decode("utf-8").strip().splitlines()

        for file_path in file_paths:
            read_command = f"cat {file_path}"
            content = container.exec_run(f"/bin/sh -c '{read_command}'").output.decode("utf-8")

            for chunk in self.chunk_code(content):
                vector = self.embedding_model.get_embedding(chunk)
                self.vector_db.upsert(id=hash(chunk), embedding=vector, metadata={"path": file_path})

    def chunk_code(self, text, max_length=500):
        return [text[i : i + max_length] for i in range(0, len(text), max_length)]

    def create_file(self, path: str):
        container = self.docker.get_container()
        command = f"touch {self.local_path}/{path}"
        result = container.exec_run(f"/bin/sh -c '{command}'")
        return result.output.decode("utf-8")

    def write_file(self, file_path: str, content: str):
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
            # self.sync_to_vector_db()
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
            # self.sync_to_vector_db()
            return result_msg
        else:
            return f"Error writing to file {file_path}: {write_result}"

    def multi_edit(self, file_path: str, edits: list):
        """Apply multiple string replacements atomically to a single file.
        
        Args:
            file_path: Path to the file to edit
            edits: List of dicts with keys: old_string, new_string, replace_all (optional, defaults to False)
        
        Returns:
            Success message or error description
        """
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
        
        # Write using Python's safer approach instead of heredoc
        temp_file = f"{full_path}.tmp"
        try:
            # Write to temporary file first
            write_result = self._safe_write_content(temp_file, modified_content)
            if write_result.startswith("Error"):
                return write_result
            
            # Atomically move temp file to final location
            move_command = f"mv {temp_file} {full_path}"
            move_result = container.exec_run(f"/bin/sh -c '{move_command}'")
            
            if move_result.exit_code == 0:
                # self.sync_to_vector_db()
                return f"Successfully applied {len(edits)} edits with {total_replacements} total replacements to '{file_path}'"
            else:
                return f"Error moving temp file: {move_result.output.decode('utf-8')}"
                
        except Exception as e:
            # Clean up temp file on error
            container.exec_run(f"/bin/sh -c 'rm -f {temp_file}'")
            return f"Error during atomic write: {str(e)}"
    
    def _safe_write_content(self, full_path: str, content: str):
        """Safely write content to a file using base64 encoding to avoid shell issues."""
        import base64
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
    
    def validate_syntax(self, file_path: str, language: str = "auto"):
        """Validate syntax of a file before applying changes.
        
        Args:
            file_path: Path to file to validate
            language: Language to validate (auto-detect if not specified)
            
        Returns:
            True if syntax is valid, error message if invalid
        """
        container = self.docker.get_container()
        full_path = f"{self.local_path}/{file_path}"
        
        # Auto-detect language from file extension
        if language == "auto":
            extension = file_path.split('.')[-1].lower() if '.' in file_path else ""
            language_map = {
                'py': 'python',
                'js': 'javascript', 
                'ts': 'typescript',
                'json': 'json',
                'yaml': 'yaml',
                'yml': 'yaml'
            }
            language = language_map.get(extension, "unknown")
        
        # Validate based on language
        if language == "python":
            # Use Python's compile to check syntax
            check_command = f"python3 -m py_compile {full_path}"
            result = container.exec_run(f"/bin/sh -c '{check_command}'")
            if result.exit_code == 0:
                return True
            else:
                return f"Python syntax error: {result.output.decode('utf-8')}"
        
        elif language == "javascript" or language == "typescript":
            # Use node to check syntax
            check_command = f"node -c {full_path}"
            result = container.exec_run(f"/bin/sh -c '{check_command}'")
            if result.exit_code == 0:
                return True
            else:
                return f"JavaScript syntax error: {result.output.decode('utf-8')}"
        
        elif language == "json":
            # Use jq or python to validate JSON
            check_command = f"python3 -c 'import json; json.load(open(\"{full_path}\"))'"
            result = container.exec_run(f"/bin/sh -c '{check_command}'")
            if result.exit_code == 0:
                return True
            else:
                return f"JSON syntax error: {result.output.decode('utf-8')}"
        
        else:
            # For unknown languages, just return True (no validation)
            return True

    def insert_code_at_line(self, path: str, line_number: int, code: str):
        container = self.docker.get_container()
        escaped_code = code.replace('"', '\\"')
        command = f'sed -i "{line_number}i {escaped_code}" {self.local_path}/{path}'
        result = container.exec_run(f"/bin/sh -c '{command}'")
        self.sync_to_vector_db()
        return result.output.decode("utf-8")

    def ls(self):
        """List all files"""
        container = self.docker.get_container()
        command = f"find {self.local_path} -type f"
        result = container.exec_run(f"/bin/sh -c '{command}'")
        files = result.output.decode("utf-8").strip().splitlines()
        # Return relative paths from repo root
        return [f.replace(f"{self.local_path}/", "") for f in files if f.startswith(self.local_path)]

    def read_file(self, file_path: str, offset: int = 0, limit: int = 2000):
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
            result_lines.append(f"{line_number:6d}\t{line_content}")
        
        return "\n".join(result_lines)

    def search_in_files(self, pattern: str, file_glob: str = "*", context_lines: int = 0, case_insensitive: bool = False):
        """Search for regex patterns in files with optional context lines.
        
        Args:
            pattern: Regex pattern to search for
            file_glob: File pattern to search in (e.g., "*.py", "**/*.js")
            context_lines: Number of context lines before/after matches
            case_insensitive: Whether to ignore case
            
        Returns:
            Search results with file paths, line numbers, and matches
        """
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
            return "\n".join(processed_lines)
        elif result.exit_code == 1:
            return "No matches found"
        else:
            return f"Search error: {output}"

    def find_files(self, pattern: str, path: str = "."):
        """Find files matching glob patterns.
        
        Args:
            pattern: Glob pattern like "*.py", "**/*.js", "src/**/*.py"
            path: Starting directory (relative to repo root)
            
        Returns:
            List of matching file paths (relative to repo root)
        """
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
        """Create a timestamped backup of a file.
        
        Args:
            file_path: Path to file to backup
            
        Returns:
            Backup file path or error message
        """
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
        """Restore a file from backup.
        
        Args:
            file_path: Original file path to restore to
            backup_name: Name of backup file (e.g., "file.py.backup_20231201_143022")
            
        Returns:
            Success message or error
        """
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

    def input(self, function_name: str, inputs: dict):
        functions = {
            "sync": self.sync_to_vector_db,
            "ls": self.ls,
            "create_file": self.create_file,
            "write_file": self.write_file,
            "edit_file": self.edit_file,
            "multi_edit": self.multi_edit,
            "insert_code_at_line": self.insert_code_at_line,
            "read_file": self.read_file,
            "search_in_files": self.search_in_files,
            "find_files": self.find_files,
            "backup_file": self.backup_file,
            "restore_backup": self.restore_backup,
            "validate_syntax": self.validate_syntax,
        }

        func = functions.get(function_name)
        if func:
            return func(**inputs)

    @property
    def description(self):
        return """
        The `code` component allows the agent to read, write, create, and modify code files inside a shared Docker container.
        Note that the current working directory is set to the root of the repository, so all file paths should be relative to the repository root (/home/ubuntu/repo).
        
        BEST PRACTICES FOR ATOMIC OPERATIONS:
        1. ALWAYS read files first to understand current state
        2. Plan ALL changes needed for a task before making any modifications
        3. Use multi_edit() for multiple changes to the same file (prevents broken intermediate states)
        4. Use backup_file() before major refactoring
        5. NEVER make partial changes - complete tasks atomically or don't start
        6. Validate that all target strings exist before applying changes
        
        Functions:
        - ls(): List all files in the repository
        - read_file(file_path, offset=0, limit=2000): Read file with line numbers and optional offset/limit. USE THIS FIRST to understand code structure
        - write_file(file_path, content): Write content to a file, creating directories as needed
        - edit_file(file_path, old_string, new_string, replace_all=False): Replace text in a file with error checking. Use for single edits only
        - multi_edit(file_path, edits): Apply multiple string replacements atomically (edits is list of dicts with old_string, new_string, replace_all keys). PREFERRED for multiple changes
        - create_file(path): Create an empty file
        - insert_code_at_line(path, line_number, code): Insert code at specific line number
        - search_in_files(pattern, file_glob="*", context_lines=0, case_insensitive=False): Search for regex patterns in files
        - find_files(pattern, path="."): Find files matching glob patterns like "*.py" or "**/*.js"
        - backup_file(file_path): Create timestamped backup of a file. Use before major refactoring
        - restore_backup(file_path, backup_name): Restore file from backup
        - validate_syntax(file_path, language="auto"): Check syntax validity before applying changes
        - sync(): Syncs all code to vector DB using provided embedding model
        """
