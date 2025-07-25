from abc import ABC, abstractmethod
import os
import shutil
from langchain_community.document_loaders import PyPDFLoader
import pathspec
import json
import hashlib


from woodwork.components.component import component
from woodwork.interfaces.tool_interface import tool_interface
from woodwork.helper_functions import format_kwargs


class knowledge_base(component, tool_interface, ABC):
    def __init__(self, **config):
        format_kwargs(config, component="knowledge_base")
        super().__init__(**config)
        self.cache_path = ".woodwork/embedding_index.json"
        self.embedded_files = self.load_cache()

    def load_cache(self):
        if os.path.exists(self.cache_path):
            with open(self.cache_path, "r") as f:
                return json.load(f)
        return {}

    def save_cache(self):
        os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
        with open(self.cache_path, "w") as f:
            json.dump(self.embedded_files, f, indent=2)

    def hash_file_content(self, content: str):
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def should_embed(self, file_path: str, rel_path: str):
        try:
            with open(file_path, "r") as f:
                content = f.read()
            if not content.strip():
                return False, None  # Skip empty files

            file_hash = self.hash_file_content(content)
            mtime = os.path.getmtime(file_path)

            cached = self.embedded_files.get(rel_path)
            if cached and cached["mtime"] == mtime and cached["hash"] == file_hash:
                return False, None  # Already embedded

            # Update cache entry
            self.embedded_files[rel_path] = {
                "mtime": mtime,
                "hash": file_hash,
            }
            return True, content
        except Exception as e:
            print(f"Failed to check file {file_path}: {e}")
            return False, None

    def embed_file(self, file_path: str, base_dir: str):
        rel_path = os.path.relpath(file_path, base_dir)

        # Read content and check if embedding needed
        should_embed, content = self.should_embed(file_path, rel_path)
        if not should_embed:
            print(f"Skipping embed for {rel_path}, no changes detected")
            return

        print(f"Embedding file: {rel_path}")
        if file_path.endswith(".pdf"):
            loader = PyPDFLoader(file_path)
            documents = loader.load()
            full_text = "\n".join([doc.page_content for doc in documents])
            vector_ids = self.embed(full_text, rel_path)
        else:
            if content and content.strip():
                vector_ids = self.embed(content, rel_path)
            else:
                return  # skip empty files

        # Save vector IDs for deletion/updating later
        self.embedded_files[rel_path]["vector_ids"] = vector_ids
        self.save_cache()

    def load_gitignore(self, path: str):
        gitignore_path = os.path.join(path, ".gitignore")
        if os.path.exists(gitignore_path):
            with open(gitignore_path, "r") as f:
                return pathspec.PathSpec.from_lines("gitwildmatch", f)
        return None

    def embed_init(self):
        if self._file_to_embed is not None and os.path.exists(self._file_to_embed):
            base_dir = (
                self._file_to_embed if os.path.isdir(self._file_to_embed) else os.path.dirname(self._file_to_embed)
            )
            spec = self.load_gitignore(base_dir)

            if os.path.isfile(self._file_to_embed):
                rel_path = os.path.relpath(self._file_to_embed, base_dir)
                if not spec or not spec.match_file(rel_path):
                    self.embed_file(self._file_to_embed, base_dir)

            elif os.path.isdir(self._file_to_embed):
                for root, dirs, files in os.walk(self._file_to_embed):
                    dirs[:] = [d for d in dirs if d not in {".git", "__pycache__", ".venv", "node_modules"}]

                    for file in files:
                        file_path = os.path.join(root, file)
                        rel_path = os.path.relpath(file_path, base_dir)
                        if not spec or not spec.match_file(rel_path):
                            self.embed_file(file_path, base_dir)

        existing_files = set()
        for root, _, files in os.walk(base_dir):
            for file in files:
                existing_files.add(os.path.relpath(os.path.join(root, file), base_dir))

        deleted_files = [path for path in self.embedded_files if path not in existing_files]

        # Delete vector DB entries
        for path in deleted_files:
            entry = self.embedded_files[path]
            ids_to_delete = entry.get("vector_ids", [])
            self.delete_vectors(ids_to_delete)

        # Remove from cache
        for path in deleted_files:
            del self.embedded_files[path]
        self.save_cache()

    def clear_all(self):
        if os.path.exists(self._path):
            shutil.rmtree(self._path)

    @abstractmethod
    def query(self, query):
        pass

    @abstractmethod
    def delete_vectors(self, ids):
        """
        Delete vectors from the knowledge base.
        This method should be implemented by subclasses to handle vector deletion.
        """
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
