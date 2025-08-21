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

        print_debug("Synced code to vector DB.")

    def chunk_code(self, text, max_length=500):
        return [text[i : i + max_length] for i in range(0, len(text), max_length)]

    def create_file(self, path: str):
        container = self.docker.get_container()
        command = f"touch {self.local_path}/{path}"
        result = container.exec_run(f"/bin/sh -c '{command}'")
        return result.output.decode("utf-8")

    def write_file(self, path: str, content: str):
        container = self.docker.get_container()
        escaped_content = content.replace('"', '\\"')
        command = f'echo "{escaped_content}" > {self.local_path}/{path}'
        result = container.exec_run(f"/bin/sh -c '{command}'")
        # self.sync_to_vector_db()
        return result.output.decode("utf-8")

    def insert_code_at_line(self, path: str, line_number: int, code: str):
        container = self.docker.get_container()
        escaped_code = code.replace('"', '\\"')
        command = f'sed -i "{line_number}i {escaped_code}" {self.local_path}/{path}'
        result = container.exec_run(f"/bin/sh -c '{command}'")
        self.sync_to_vector_db()
        return result.output.decode("utf-8")

    def read_file(self, path: str):
        container = self.docker.get_container()
        command = f"cat {self.local_path}/{path}"
        result = container.exec_run(f"/bin/sh -c '{command}'")
        return result.output.decode("utf-8")

    def input(self, function_name: str, inputs: dict):
        functions = {
            "sync": self.sync_to_vector_db,
            "create_file": self.create_file,
            "write_file": self.write_file,
            "insert_code_at_line": self.insert_code_at_line,
            "read_file": self.read_file,
        }

        func = functions.get(function_name)
        if func:
            return func(**inputs)

    @property
    def description(self):
        return """
        The `code` component allows the agent to read, write, create, and modify code files inside a shared Docker container.
        Note that the current working directory is set to the root of the repository, so all file paths should be relative to the repository root (/home/ubuntu/repo).
        Functions:
        - create_file(path)
        - write_file(path, content)
        - insert_code_at_line(path, line_number, code)
        - read_file(path)
        - sync(): syncs all code to vector DB using provided embedding model
        """
