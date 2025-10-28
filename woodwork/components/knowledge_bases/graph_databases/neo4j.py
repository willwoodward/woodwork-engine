import logging

from neo4j import GraphDatabase
from openai import OpenAI
from typing import Callable, Optional

from woodwork.components.knowledge_bases.graph_databases.graph_database import (
    graph_database,
)
from woodwork.deployments import Docker
from woodwork.utils import format_kwargs, get_optional
from woodwork.utils.errors.errors import WoodworkError

log = logging.getLogger(__name__)


class neo4j(graph_database):
    def __init__(self, uri: str, user: str, password: str, **config):
        format_kwargs(config, uri=uri, user=user, password=password, type="neo4j")
        super().__init__(**config)
        log.debug("Initializing Neo4j Knowledge Base...")

        # Attempt to create Docker integration if possible, but do not raise at import/init time.
        # This keeps test collection and other imports from failing in environments without Docker.
        self.docker: Optional[Docker] = None
        try:
            try:
                self.docker = Docker(
                    image_name="custom-neo4j",
                    container_name="neo4j-container",
                    dockerfile="""
                    FROM neo4j:latest
                    ENV NEO4J_AUTH=neo4j/testpassword
                    EXPOSE 7474 7687
                    CMD ["neo4j"]
                    """,
                    container_args={
                        "ports": {
                            "7474/tcp": 7474,
                            "7687/tcp": 7687,
                        },
                        "environment": {
                            "NEO4J_AUTH": "neo4j/testpassword",
                            "NEO4J_PLUGINS": '["genai"]',
                            "NEO4J_dbms_security_procedures_unrestricted": "genai.*",
                            "NEO4J_dbms_security_procedures_allowlist": "genai.*",
                        },
                    },
                    volume_location=".woodwork/neo4j/data",
                )
                # Try to init, but catch any WoodworkError that indicates Docker isn't available.
                try:
                    self.docker.init()
                except WoodworkError as e:
                    log.warning("Docker init failed or not available; continuing without Docker: %s", e)
                    self.docker = None
            except Exception as e:
                # Any failure constructing the Docker helper should not block initialization.
                log.debug("Skipping Docker setup for neo4j (not available or failed to create): %s", e)
                self.docker = None

        # Any unexpected exception should be caught and logged; do not raise here.
        except Exception as e:  # noqa: BLE001 - defensive catch to prevent import-time crashes
            log.debug("Docker integration skipped due to error: %s", e)
            self.docker = None

        # Attempt to create a Neo4j driver, but if we can't, set it to None and continue.
        self._driver = None
        try:
            self._driver = GraphDatabase.driver(uri, auth=(user, password))
            if not self._connected():
                log.warning("Could not verify Neo4j connection to %s; continuing with driver=None", uri)
                # Close driver if connected-check failed
                try:
                    if self._driver is not None:
                        self._driver.close()
                except Exception:
                    pass
                self._driver = None
        except Exception as e:
            log.warning("Neo4j driver initialization failed (likely no server available): %s", e)
            self._driver = None

        self._api_key = get_optional(config, "api_key")
        self._openai_client = None

        if self._api_key:
            try:
                # lazily create OpenAI client if API key is available; allow failures to be raised later
                self._openai_client = OpenAI()
            except Exception as e:
                log.warning("Failed to initialize OpenAI client: %s", e)
                self._openai_client = None

        log.debug("Neo4j Knowledge Base created (docker=%s, driver=%s).", bool(self.docker), bool(self._driver))

    def set_api_key(self, api_key: str):
        try:
            self._openai_client = OpenAI(api_key=api_key)
            self._api_key = api_key
        except Exception as e:
            raise WoodworkError(f"Failed to initialize OpenAI client: {e}")

    def _connected(self) -> bool:
        # If no driver is available, we are not connected.
        if self._driver is None:
            return False
        try:
            with self._driver.session() as session:
                session.run("RETURN 1")
                return True
        except Exception as e:
            log.error(f"Neo4j connection check failed: {e}")
            return False

    def init_vector_index(self, index_name, label, property):
        if self._driver is None:
            raise WoodworkError("Neo4j driver is not initialized; cannot create vector index.")

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
        try:
            if self._driver is not None:
                self._driver.close()
        except Exception:
            pass
        try:
            if self.docker is not None:
                self.docker.close()
        except Exception:
            pass

    def run(self, query, parameters=None):
        if self._driver is None:
            raise WoodworkError("Neo4j driver is not initialized; cannot run queries.")
        with self._driver.session() as session:
            result = session.run(query, parameters)
            return result.data()

    def query(self, query):
        return

    def embed(self, label, property):
        if self._openai_client is None:
            raise WoodworkError("OpenAI client not initialized; cannot embed.")

        response = self._openai_client.embeddings.create(input=label, model="text-embedding-ada-002")

        # Extract the embedding (a list of 1536 numbers)
        embedding = response.data[0].embedding

        query = f"""CALL db.index.vector.queryNodes('embeddings', 10, {embedding})
        YIELD node AS node, score
        RETURN elementId(node) AS nodeID, node.{property} AS {property}, node.inputs AS inputs, score"""

        return self.run(query)

    def delete_vectors(self, ids):
        raise NotImplementedError()

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
            similarity_search(prompt, label, property): returns nodes labelled label with similar text in the property property.
            run(query): runs a cypher query on the graph.
        """

    def input(self, function_name: str, inputs: dict) -> str | None:
        func: Callable | None = None

        if function_name == "similarity_search":
            func = self.similarity_search
        if function_name == "run":
            func = self.run
        if func is None:
            return None

        return str(func(**inputs))
