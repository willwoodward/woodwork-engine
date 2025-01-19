from neo4j import GraphDatabase
from openai import OpenAI
import os
import docker
import io
import time

from woodwork.helper_functions import print_debug, format_kwargs
from woodwork.components.knowledge_bases.graph_databases.graph_database import (
    graph_database,
)


class neo4j(graph_database):
    def __init__(self, uri, user, password, api_key, **config):
        format_kwargs(config, uri=uri, user=user, password=password, api_key=api_key, type="neo4j")
        super().__init__(**config)
        print_debug("Initialising Neo4j Knowledge Base...")

        self._local_init()

        self._driver = GraphDatabase.driver(uri, auth=(user, password))
        if not self._connected():
            exit()

        self._api_key = api_key
        self._openai_client = OpenAI()

        print_debug("Neo4j Knowledge Base created.")

    def _connected(self):
        try:
            with self._driver.session() as session:
                session.run("RETURN 1")
                return True
        except Exception:
            return False
        finally:
            self._driver.close()

    def _ensure_data_directory(self, path):
        """Ensure the data directory exists."""
        if not os.path.exists(path):
            os.makedirs(path)
            print_debug(f"Created data directory at {path}")
        else:
            print_debug(f"Data directory already exists at {path}")

    def _build_docker_image(self, client, image_name):
        """Build the Docker image."""
        print_debug("Building Docker image...")

        dockerfile_content = """
        FROM neo4j:latest
        ENV NEO4J_AUTH=neo4j/testpassword
        EXPOSE 7474 7687
        CMD ["neo4j"]
        """

        client.images.build(fileobj=io.BytesIO(dockerfile_content.encode("utf-8")), tag=image_name)
        print_debug(f"Successfully built image: {image_name}")

    def _run_docker_container(self, client, image_name, container_name, path):
        """Run the Neo4j Docker container."""
        print_debug("Running Docker container...")

        # Check if the container already exists
        try:
            container = client.containers.get(container_name)
            print_debug(f"Container '{container_name}' already exists. Starting it...")
            container.start()
        except docker.errors.NotFound:
            print_debug(f"Container '{container_name}' not found. Creating a new one...")
            client.containers.run(
                image_name,
                name=container_name,
                ports={
                    "7474/tcp": 7474,
                    "7687/tcp": 7687,
                },
                environment={
                    "NEO4J_AUTH": "neo4j/testpassword",
                    "NEO4J_PLUGINS": '["genai"]',
                    "NEO4J_dbms_security_procedures_unrestricted": "genai.*",  # Allow unrestricted genai procedures
                    "NEO4J_dbms_security_procedures_allowlist": "genai.*",  # Allowlist genai procedures
                },
                volumes={
                    os.path.abspath(path): {
                        "bind": "/data",
                        "mode": "rw",
                    }
                },
                detach=True,
            )
            time.sleep(15)
        print_debug(f"Neo4j container '{container_name}' is running.")

    def _local_init(self):
        self._ensure_data_directory(".woodwork/neo4j/data")
        client = docker.from_env()
        self._build_docker_image(client, "custom-neo4j")
        self._run_docker_container(client, "custom-neo4j", "neo4j-container", ".woodwork/neo4j/data")

    def init_vector_index(self, index_name, label, property):
        query = f"""
        CREATE VECTOR INDEX {index_name} IF NOT EXISTS
        FOR (a:{label})
        ON a.{property}
        OPTIONS {{ indexConfig: {{
            `vector.dimensions`: 1536,
            `vector.similarity_function`: 'cosine'
        }} }};
        """

        return self.run(query)

    def close(self):
        self._driver.close()

    def run(self, query, parameters=None):
        with self._driver.session() as session:
            result = session.run(query, parameters)
            return result.data()

    def query(self, query):
        return

    def embed(self, label, property):
        query = f"""MATCH (a:{label})
        WHERE a.embedding IS null
        WITH a, genai.vector.encode(a.{property}, "OpenAI", {{ token: \"{self._api_key}\" }}) AS embedding
        CALL db.create.setNodeVectorProperty(a, 'embedding', embedding);"""

        return self.run(query)

    def similarity_search(self, prompt, label, property):
        response = self._openai_client.embeddings.create(input=prompt, model="text-embedding-ada-002")

        # Extract the embedding (a list of 1536 numbers)
        embedding = response.data[0].embedding

        query = f"""CALL db.index.vector.queryNodes('embeddings', 10, {embedding})
        YIELD node AS node, score
        RETURN elementId(node) AS nodeID, node.{property} AS {property}, node.inputs AS inputs, score"""

        return self.run(query)

    @property
    def embedding_model(self):
        return

    @property
    def retriever(self):
        return

    @property
    def description(self):
        return """
            A graph database that can be added to, queried and cleared. The query language is Cypher.
            The following functions can be used as actions, with inputs as a dictionary of kwargs:
            similarity_search(prompt, label, proptery): returns nodes labelled label with similar text in the property property.
            run(query): runs a cypher query on the graph.
        """

    def input(self, function_name: str, inputs: dict) -> str:
        func = None

        if function_name == "similarity_search":
            func = self.similarity_search
        if function_name == "run":
            func = self.run

        return str(func(**inputs))
