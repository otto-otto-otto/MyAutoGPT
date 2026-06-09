"""Core agent-graph serialisation helpers for the builder panel."""

import logging

from backend.data.graph import get_graph

logger = logging.getLogger(__name__)


async def get_agent_as_json(
    graph_id: str,
    user_id: str | None,
) -> dict | None:
    """Fetch the latest active graph for *graph_id* and return a dict
    suitable for rendering as XML in the builder context.

    Returns ``None`` when the graph does not exist or the caller lacks access.
    """
    try:
        graph = await get_graph(
            graph_id,
            version=None,  # latest active
            user_id=user_id,
            for_export=True,
        )
    except Exception as exc:
        logger.debug("Failed to fetch graph %s: %s", graph_id, exc)
        return None

    if graph is None:
        return None

    return {
        "version": getattr(graph, "version", 1),
        "name": getattr(graph, "name", None),
        "description": getattr(graph, "description", None),
        "nodes": [node.model_dump() for node in getattr(graph, "nodes", []) or []],
        "links": [link.model_dump() for link in getattr(graph, "links", []) or []],
    }
