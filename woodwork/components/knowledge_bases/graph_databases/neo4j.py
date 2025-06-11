import logging

from neo4j import GraphDatabase
from openai import OpenAI
from typing import Callable

from woodwork.components.knowledge_bases.graph_databases.graph_database import (
    graph_database,
)
from woodwork.deployments import Docker
from woodwork.helper_functions import format_kwargs

log = logging.getLogger(__name__)


class neo4j(graph_database):
    def __init__(self, uri, user, password, api_key, **config):
        format_kwargs(config, uri=uri, user=user, password=password, api_key=api_key, type="neo4j")
        super().__init__(**config)
        log.debug("Initializing Neo4j Knowledge Base...")

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
                    "NEO4J_dbms_security_procedures_unrestricted": "genai.*",  # Allow unrestricted genai procedures
                    "NEO4J_dbms_security_procedures_allowlist": "genai.*",  # Allowlist genai procedures
                },
            },
            volume_location=".woodwork/neo4j/data",
        )
        self.docker.init()

        self._driver = GraphDatabase.driver(uri, auth=(user, password))
        if not self._connected():
            exit()

        self._api_key = api_key
        self._openai_client = OpenAI()

        log.debug("Neo4j Knowledge Base created.")

    def _connected(self):
        try:
            with self._driver.session() as session:
                session.run("RETURN 1")
                return True
        except Exception:
            return False
        finally:
            self._driver.close()

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
        self.docker.close()

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
