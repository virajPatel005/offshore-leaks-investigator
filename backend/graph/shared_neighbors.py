"""Generic graph tool: common neighbors of two nodes.

Supports "which companies share an officer and a non-hub address"-style
questions: the caller filters the returned neighbors by label. The hub
filter sits inside the traversal pattern; hubs among the common neighbors
are reported separately, never silently dropped.
"""
import math
import os

from falkordb import FalkorDB

HOST = os.getenv("FALKORDB_HOST", "localhost")
PORT = int(os.getenv("FALKORDB_PORT", "6379"))
GRAPH = os.getenv("GRAPH_NAME", "offshore")
QUERY_TIMEOUT_MS = 15000

Q = """MATCH (a {node_id: $x}), (b {node_id: $y})
MATCH (a)-[r1]-(n)-[r2]-(b) WHERE n.degree_core <= $hub AND n.node_id <> $x AND n.node_id <> $y
RETURN n.node_id, n.name, labels(n), n.degree_core, n.sourceID,
type(r1), r1.link, r1.role_category, type(r2), r2.link, r2.role_category LIMIT %d"""
HUB_Q = """MATCH (a {node_id: $x}), (b {node_id: $y})
MATCH (a)-[r1]-(n)-[r2]-(b) WHERE n.degree_core > $hub
RETURN DISTINCT n.node_id, n.name, labels(n), n.degree_core LIMIT %d"""


def _db():
    return FalkorDB(host=HOST, port=PORT).select_graph(GRAPH)


def shared_neighbors(id_a, id_b, hub_threshold=1000, limit=20):
    """Common neighbors grouped by edge-type pair, with rarity weights."""
    limit = max(1, min(int(limit), 100))
    g = _db()
    n_total = g.query("MATCH (n) RETURN count(n) LIMIT 1", timeout=QUERY_TIMEOUT_MS).result_set[0][0]
    cypher = Q % limit
    rows = g.query(cypher, {"x": id_a, "y": id_b, "hub": hub_threshold},
                   timeout=QUERY_TIMEOUT_MS).result_set
    neighbors, grouped = [], {}
    for r in rows:
        deg = r[3] or 0
        neighbors.append({"node_id": r[0], "name": r[1], "labels": r[2], "degree_core": deg,
                          "sourceID": r[4], "weight": math.log((n_total + 1) / (deg + 1)),
                          "via": [{"side": "a", "rel_type": r[5], "link": r[6], "role_category": r[7]},
                                  {"side": "b", "rel_type": r[8], "link": r[9], "role_category": r[10]}]})
        grouped[f"{r[5]}+{r[8]}"] = grouped.get(f"{r[5]}+{r[8]}", 0) + 1
    neighbors.sort(key=lambda n: -n["weight"])
    hub_rows = g.query(HUB_Q % limit, {"x": id_a, "y": id_b, "hub": hub_threshold},
                       timeout=QUERY_TIMEOUT_MS).result_set
    excluded = [{"node_id": r[0], "name": r[1], "labels": r[2], "degree_core": r[3]} for r in hub_rows]
    return {"id_a": id_a, "id_b": id_b, "hub_threshold": hub_threshold,
            "neighbors": neighbors, "grouped_by_edge_type": grouped,
            "excluded_hubs": excluded, "cypher": [cypher, HUB_Q % limit], "note": None}
