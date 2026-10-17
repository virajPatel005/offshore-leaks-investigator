"""Generic graph tool: expand one node's immediate neighbours.

Read-only and used by the UI "Expand neighbours" action (and available over
MCP). The hub predicate sits on the NEIGHBOUR inside the pattern, so hubs are
excluded during expansion and listed explicitly instead of silently dropped.
A centre node whose own degree_core exceeds the threshold is itself a hub: its
fan-out (up to ~37k) is uninformative, so it is NOT expanded unless the caller
explicitly passes allow_hub=True (the UI override).
"""
import os

from falkordb import FalkorDB

HOST = os.getenv("FALKORDB_HOST", "localhost")
PORT = int(os.getenv("FALKORDB_PORT", "6379"))
GRAPH = os.getenv("GRAPH_NAME", "offshore")
QUERY_TIMEOUT_MS = 15000
HUB_LIST_LIMIT = 25

Q_CENTER = """MATCH (a {node_id: $id}) RETURN a.node_id, a.name, labels(a), a.degree_core,
a.country_codes, a.sourceID LIMIT 1"""
Q_MAIN = """MATCH (a {node_id: $id})-[r]-(n) WHERE n.degree_core <= $hub
RETURN n.node_id, n.name, labels(n), n.country_codes, n.degree_core, n.sourceID,
type(r), r.link, r.role_category, r.status, r.start_date, r.end_date, r.sourceID LIMIT %d"""
Q_COUNT = """MATCH (a {node_id: $id})-[r]-(n) RETURN count(DISTINCT n)"""
Q_HUB = """MATCH (a {node_id: $id})-[r]-(n) WHERE n.degree_core > $hub
RETURN DISTINCT n.node_id, n.name, labels(n), n.degree_core LIMIT %d"""


def _db():
    return FalkorDB(host=HOST, port=PORT).select_graph(GRAPH)


def get_node(node_id):
    """Display fields for one node; None when the id is not in the graph."""
    row = _db().query(Q_CENTER, {"id": node_id}, timeout=QUERY_TIMEOUT_MS).result_set
    if not row:
        return None
    r = row[0]
    return {"node_id": r[0], "name": r[1], "labels": r[2] or [], "degree_core": r[3] or 0,
            "country_codes": r[4], "sourceID": r[5]}


def get_neighbors(node_id, hub_threshold=1000, limit=25, allow_hub=False):
    """Immediate neighbours of node_id, hub-filtered and size-capped."""
    limit = max(1, min(int(limit), 100))
    g = _db()
    center = g.query(Q_CENTER, {"id": node_id}, timeout=QUERY_TIMEOUT_MS).result_set
    if not center:
        return {"node_id": node_id, "error": f"no node with node_id {node_id}", "neighbors": [],
                "excluded_hubs": [], "cypher": [Q_CENTER]}
    cid, cname, clabels, cdeg, ccc, csid = center[0]
    cdeg = cdeg or 0
    is_hub = cdeg > hub_threshold
    base = {"node_id": cid, "name": cname, "labels": clabels, "degree_core": cdeg,
            "country_codes": ccc, "sourceID": csid,
            "hub_threshold": hub_threshold, "allow_hub": bool(allow_hub), "is_hub": is_hub,
            "neighbors": [], "excluded_hubs": [], "cypher": [Q_CENTER]}
    if is_hub and not allow_hub:
        base["note"] = (f"hub: neighbours not expanded by default ({cname} has degree_core {cdeg} "
                        f"> {hub_threshold}); override with allow_hub")
        return base
    total = g.query(Q_COUNT, {"id": node_id}, timeout=QUERY_TIMEOUT_MS).result_set[0][0]
    cypher = Q_MAIN % limit
    rows = g.query(cypher, {"id": node_id, "hub": hub_threshold},
                   timeout=QUERY_TIMEOUT_MS).result_set
    neighbors = [{"node_id": r[0], "name": r[1], "labels": r[2], "country_codes": r[3],
                  "degree_core": r[4] or 0, "sourceID": r[5],
                  "rel_type": r[6], "link": r[7], "role_category": r[8],
                  "status": r[9], "start_date": r[10], "end_date": r[11], "rel_sourceID": r[12]}
                 for r in rows]
    hub_rows = g.query(Q_HUB % HUB_LIST_LIMIT, {"id": node_id, "hub": hub_threshold},
                       timeout=QUERY_TIMEOUT_MS).result_set
    excluded = [{"node_id": r[0], "name": r[1], "labels": r[2], "degree_core": r[3]} for r in hub_rows]
    notes = []
    if is_hub:
        notes.append(f"hub override: showing up to {limit} of {total} neighbours, high-degree ones still filtered")
    if total > len(neighbors):
        notes.append(f"showing {len(neighbors)} of {total} neighbours (limit {limit})")
    base.update({"neighbors": neighbors, "excluded_hubs": excluded, "total_neighbors": total,
                 "shown": len(neighbors), "cypher": [Q_CENTER, cypher, Q_COUNT, Q_HUB % HUB_LIST_LIMIT],
                 "note": "; ".join(notes) or None})
    return base
