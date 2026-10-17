"""MCP server (stdio) wrapping the three read-only graph tools (D8, D12).

Tools never write: the name full-text indexes are created once at startup,
so every tool call is read-only. Each result carries the Cypher used, a
limitations note, and explicit truncation flags when lists are capped.
"""
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Annotated, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from backend.graph.neighbors import get_neighbors
from backend.graph.search_entity import ensure_search_indexes, search_entity
from backend.graph.shared_neighbors import shared_neighbors
from backend.graph.strongest_connection import strongest_connection

BUDGET_S = 20
LIST_CAP = 50

LIMITATIONS = ("Connection relevance only: appearing in this public ICIJ leak data "
               "implies no wrongdoing. Scores rank how informative a recorded connection is, "
               "not likelihood of any conduct. Soft-edge matches are possible matches, not identities.")

server = MCPServer("offshore-investigator", instructions=(
    "Investigate public ICIJ leak data (Offshore Leaks and Panama Papers) in FalkorDB. "
    "Always call search_entity first to resolve a name to node_ids; "
    "strongest_connection and shared_neighbors need node_ids."))


def _bounded(fn, **kw):
    """Run a sync tool with a 20 s budget; structured errors, no tracebacks."""
    with ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(fn, **kw)
        try:
            return fut.result(timeout=BUDGET_S)
        except Exception as ex2:
            return {"error": f"{type(ex2).__name__}: {str(ex2)[:200]}",
                    "limitations": LIMITATIONS}


def _cap(result, key, maxn=LIST_CAP):
    items = result.get(key)
    if isinstance(items, list) and len(items) > maxn:
        result[key] = items[:maxn]
        result[f"{key}_truncated"] = True
        result["note"] = "; ".join(n for n in (result.get("note"), f"{key} capped at {maxn}") if n)
    return result


def _finish(result):
    result.setdefault("limitations", LIMITATIONS)
    for key in ("results", "neighbors", "breakdown", "excluded_hubs"):
        _cap(result, key)
    return result


@server.tool(description=(
    "Find graph nodes by name. Returns candidates with node_id, name, labels, "
    "country_codes, degree_core and sourceID, exact matches first. "
    "Call this FIRST to resolve any person/company name to node_ids; the other "
    "two tools only accept node_ids."))
def search_entity_tool(
    name: Annotated[str, Field(description="Person or company name to look up")],
    label: Annotated[Optional[str], Field(description="One of Entity, Officer, Intermediary; omit for all")] = None,
    country: Annotated[Optional[str], Field(description="Country code filter, e.g. VGB; omit for all")] = None,
    limit: Annotated[int, Field(ge=1, le=50, description="Max candidates (default 10)")] = 10,
) -> dict:
    return _finish(_bounded(search_entity, name=name, label=label, country=country, limit=limit))


@server.tool(description=(
    "Most informative recorded path between two node_ids (use search_entity first "
    "to get them). Returns the path with node names, labels, degrees and edge details, "
    "a per-node relevance-score breakdown, hubs excluded by the threshold, and the Cypher used."))
def strongest_connection_tool(
    source_id: Annotated[str, Field(description="Start node_id from search_entity")],
    target_id: Annotated[str, Field(description="End node_id from search_entity")],
    hub_threshold: Annotated[int, Field(ge=1, le=100000, description="Nodes above this degree_core are excluded (default 1000)")] = 1000,
    max_hops: Annotated[int, Field(ge=1, le=6, description="Longest path to consider (default 4)")] = 4,
) -> dict:
    return _finish(_bounded(strongest_connection, source_id=source_id, target_id=target_id,
                            hub_threshold=hub_threshold, max_hops=max_hops))


@server.tool(description=(
    "Common neighbors of two node_ids (use search_entity first to get them), grouped "
    "by edge-type pair with rarity weights. Use it to find shared officers or shared "
    "non-hub addresses between two companies. Excluded hubs are listed, not hidden."))
def shared_neighbors_tool(
    id_a: Annotated[str, Field(description="First node_id from search_entity")],
    id_b: Annotated[str, Field(description="Second node_id from search_entity")],
    hub_threshold: Annotated[int, Field(ge=1, le=100000, description="Nodes above this degree_core are excluded (default 1000)")] = 1000,
    limit: Annotated[int, Field(ge=1, le=100, description="Max neighbors (default 20)")] = 20,
) -> dict:
    return _finish(_bounded(shared_neighbors, id_a=id_a, id_b=id_b,
                            hub_threshold=hub_threshold, limit=limit))


@server.tool(description=(
    "Immediate neighbours of one node_id (use search_entity first). Expands the "
    "graph around a record: returns neighbour nodes with rel_type and link, hubs "
    "excluded by the threshold and listed, and a truncation note. A node whose own "
    "degree_core exceeds the threshold is a hub and is not expanded unless "
    "allow_hub=true (override). Read-only."))
def get_neighbors_tool(
    node_id: Annotated[str, Field(description="node_id to expand (from search_entity or a path result)")],
    hub_threshold: Annotated[int, Field(ge=1, le=100000, description="Neighbours above this degree_core are excluded (default 1000)")] = 1000,
    limit: Annotated[int, Field(ge=1, le=100, description="Max neighbours to return (default 25)")] = 25,
    allow_hub: Annotated[bool, Field(description="Expand even if the centre node is itself a hub (default false)")] = False,
) -> dict:
    return _finish(_bounded(get_neighbors, node_id=node_id, hub_threshold=hub_threshold,
                            limit=limit, allow_hub=allow_hub))


@server.resource("graph-schema://offshore",
                 description="Graph labels, edge types and degree meaning for this data.",
                 mime_type="text/plain")
def graph_schema() -> str:
    return ("Labels: Address, Entity, Intermediary, Officer "
            "(1,139 nodes carry both Intermediary and Officer labels: one node per ID, D4). "
            "Edge types: officer_of, intermediary_of, registered_address (core, always traversed); "
            "underlying, similar, same_as (soft, included by default, possible matches only). "
            "Results whose links include a soft type set includes_possible_match=true."
            "degree_core = distinct neighbors via core edges; degree_all = via all edge types. "
            "Scores are connection relevance, not wrongdoing likelihood.")


def main():
    ensure_search_indexes()  # one-time schema write; tool calls stay read-only
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
