from abc import ABC, abstractmethod
import os
import shutil
from langchain_community.document_loaders import PyPDFLoader
import pathspec


from woodwork.components.component import component
from woodwork.interfaces.tool_interface import tool_interface
from woodwork.helper_functions import format_kwargs


class knowledge_base(component, tool_interface, ABC):
    def __init__(self, **config):
        format_kwargs(config, component="knowledge_base")
        super().__init__(**config)

    def embed_file(self, file_path: str):
        print(f"Embedding file: {file_path}")
        if file_path.endswith(".pdf"):
            loader = PyPDFLoader(file_path)
            documents = loader.load()
            full_text = "\n".join([doc.page_content for doc in documents])
            self.embed(full_text)
        else:
            with open(file_path, "r") as file:
                content = file.read()
                if content.strip():  # Skips empty or whitespace-only files
                    self.embed(content)

    def load_gitignore(self, path: str):
        gitignore_path = os.path.join(path, '.gitignore')
        if os.path.exists(gitignore_path):
            with open(gitignore_path, 'r') as f:
                return pathspec.PathSpec.from_lines('gitwildmatch', f)
        return None

    def embed_init(self):
        if self._file_to_embed is not None and os.path.exists(self._file_to_embed):
            base_dir = (
                self._file_to_embed
                if os.path.isdir(self._file_to_embed)
                else os.path.dirname(self._file_to_embed)
            )
            spec = self.load_gitignore(base_dir)

            if os.path.isfile(self._file_to_embed):
                rel_path = os.path.relpath(self._file_to_embed, base_dir)
                if not spec or not spec.match_file(rel_path):
                    self.embed_file(self._file_to_embed)

            elif os.path.isdir(self._file_to_embed):
                for root, dirs, files in os.walk(self._file_to_embed):
                    # Skip .git and similar folders
                    dirs[:] = [d for d in dirs if d not in {".git", "__pycache__", ".venv", "node_modules"}]

                    for file in files:
                        file_path = os.path.join(root, file)
                        rel_path = os.path.relpath(file_path, base_dir)
                        if not spec or not spec.match_file(rel_path):
                            self.embed_file(file_path)


    def clear_all(self):
        if os.path.exists(self._path):
            shutil.rmtree(self._path)

    @abstractmethod
    def query(self, query):
        pass

    @property
    @abstractmethod
    def retriever(self):
        # Each knowledge base should come with a default retriever. For use with LLMs.
        pass

    @property
    @abstractmethod
    def embedding_model(self):
        # Each knowledge base should come with a default embedding model.
        return self._embedding_model
