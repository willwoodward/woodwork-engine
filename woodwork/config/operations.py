"""High-level operations on parsed components (embed, clear, workflow management)."""

import logging

from woodwork.deploy.registry import get_registry

log = logging.getLogger(__name__)


def _get_components():
    """Return all registered components."""
    registry = get_registry()
    return list(registry._components.values()) if hasattr(registry, "_components") else []


def embed_all():
    """Trigger embedding initialization on all knowledge base components."""
    from woodwork.components.knowledge_bases.knowledge_base import KnowledgeBase

    for comp in _get_components():
        if isinstance(comp, KnowledgeBase):
            comp.embed_init()


def clear_all():
    """Clear all data from knowledge base components."""
    from woodwork.components.knowledge_bases.knowledge_base import KnowledgeBase

    for comp in _get_components():
        if isinstance(comp, KnowledgeBase):
            comp.clear_all()


def delete_action_plan(id: str):
    """Delete a cached action plan by ID from all agents."""
    from woodwork.components.agents.agent import Agent

    for comp in _get_components():
        if isinstance(comp, Agent):
            comp._cache.run(f"""MATCH (n)-[:NEXT*]->(m)
                WHERE elementId(n) = "{id}"
                DETACH DELETE n
                DETACH DELETE m""")

    log.info("Successfully removed workflow with ID: %s", id)


def find_action_plan(query: str):
    """Find cached action plans similar to a query string."""
    from woodwork.components.agents.agent import Agent

    for comp in _get_components():
        if isinstance(comp, Agent):
            similar_prompts = comp._cache.similarity_search(query, "Prompt", "value")
            num_results = min(len(similar_prompts), 10)
            log.info("Here are the top %d most similar results:", num_results)
            for i in range(num_results):
                result = similar_prompts[i]
                log.info("%s %s", result["value"], result["nodeID"])
