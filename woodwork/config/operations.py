"""High-level operations on parsed components (embed, clear, workflow management)."""

import logging

from woodwork.config.factory import _get_task_master

log = logging.getLogger(__name__)


def embed_all():
    """Trigger embedding initialization on all knowledge base components."""
    from woodwork.components.knowledge_bases.knowledge_base import KnowledgeBase

    for tool in _get_task_master()._tools:
        if isinstance(tool, KnowledgeBase):
            tool.embed_init()


def clear_all():
    """Clear all data from knowledge base components."""
    from woodwork.components.knowledge_bases.knowledge_base import KnowledgeBase

    for tool in _get_task_master()._tools:
        if isinstance(tool, KnowledgeBase):
            tool.clear_all()


def delete_action_plan(id: str):
    """Delete a cached action plan by ID from all agents."""
    from woodwork.components.agents.agent import Agent

    for tool in _get_task_master()._tools:
        if isinstance(tool, Agent):
            tool._cache.run(f"""MATCH (n)-[:NEXT*]->(m)
                WHERE elementId(n) = "{id}"
                DETACH DELETE n
                DETACH DELETE m""")

    log.info(f"Successfully removed workflow with ID: {id}")


def find_action_plan(query: str):
    """Find cached action plans similar to a query string."""
    from woodwork.components.agents.agent import Agent

    for tool in _get_task_master()._tools:
        if isinstance(tool, Agent):
            similar_prompts = tool._cache.similarity_search(query, "Prompt", "value")
            num_results = min(len(similar_prompts), 10)

            print(f"Here are the top {num_results} most similar results:")
            for i in range(num_results):
                result = similar_prompts[i]
                print(f"{result['value']} {result['nodeID']}")
