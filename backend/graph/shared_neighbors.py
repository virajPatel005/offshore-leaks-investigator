"""Generic graph tool: common neighbors of two nodes.

Supports "which companies share an officer and a non-hub address"-style
questions: the caller filters the returned neighbors by label. The hub
filter sits inside the traversal pattern; hubs among the common neighbors
are reported separately, never silently dropped.
"""
import math
import os

from falkordb import FalkorDB

from backend.graph.rel_types import possible_matches

HOST = os.getenv("FALKORDB_HOST", "localhost")
PORT = int(os.getenv("FALKORDB_PORT", "6379"))
GRAPH = os.getenv("GRAPH_NAME", "offshore")
QUERY_TIMEOUT_MS = 15000

Q = """MATCH (a {node_id: $x}), (b {node_id: $y})
MATCH (a)-[r1]-(n)-[r2]-(b) WHERE n.degree_core <= $hub AND n.node_id <> $x AND n.node_id <> $y
RETURN n.node_id, n.name, labels(n), n.degree_core, n.sourceID,
type(r1), r1.link, r1.role_category, r1.status, r1.start_date, r1.end_date, r1.sourceID,
type(r2), r2.link, r2.role_category, r2.status, r2.start_date, r2.end_date, r2.sourceID LIMIT %d"""
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
                          "via": [{"side": "a", "rel_type": r[5], "link": r[6], "role_category": r[7],
                                   "status": r[8], "start_date": r[9], "end_date": r[10], "sourceID": r[11]},
                                  {"side": "b", "rel_type": r[12], "link": r[13], "role_category": r[14],
                                   "status": r[15], "start_date": r[16], "end_date": r[17], "sourceID": r[18]}]})
        grouped[f"{r[5]}+{r[12]}"] = grouped.get(f"{r[5]}+{r[12]}", 0) + 1
    neighbors.sort(key=lambda n: -n["weight"])
    hub_rows = g.query(HUB_Q % limit, {"x": id_a, "y": id_b, "hub": hub_threshold},
                       timeout=QUERY_TIMEOUT_MS).result_set
    excluded = [{"node_id": r[0], "name": r[1], "labels": r[2], "degree_core": r[3]} for r in hub_rows]
    soft = possible_matches(e for n in neighbors for e in n["via"])
    note = None
    if soft:
        note = ("shown link(s) include possible-match edge(s) (" + ", ".join(soft)
                + "): records are linked, identity is not confirmed")
    return {"id_a": id_a, "id_b": id_b, "hub_threshold": hub_threshold,
            "neighbors": neighbors, "grouped_by_edge_type": grouped,
            "includes_possible_match": bool(soft), "possible_match_edges": soft,
            "excluded_hubs": excluded, "cypher": [cypher, HUB_Q % limit], "note": note}
