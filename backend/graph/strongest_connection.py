"""Generic graph tool: strongest recorded connection between two nodes.

Method (D3): candidates come from Cypher with a hub predicate on every
intermediate node of an exact-depth chain (iterative deepening, so the first
non-empty depth is the shortest hub-respecting length); the small candidate
set is ranked in Python by mean rarity weight per intermediate node. Endpoints
are fixed by the caller, so only intermediate nodes contribute to the score.
"""
import math
import os

from falkordb import FalkorDB

HOST = os.getenv("FALKORDB_HOST", "localhost")
PORT = int(os.getenv("FALKORDB_PORT", "6379"))
GRAPH = os.getenv("GRAPH_NAME", "offshore")
CANDIDATE_LIMIT = 5
QUERY_TIMEOUT_MS = 15000

def candidate_query(depth, limit):
    """Exact-depth chain with a hub predicate on every intermediate node.

    Unlike WHERE all(n IN nodes(p)) on a variable-length pattern (which the
    engine applies after expanding through hubs), per-hop predicates prune
    hub neighborhoods during expansion, so hub-adjacent queries stay fast.
    Endpoints are exempt: a queried endpoint is never an excluded hub.
    """
    mids = [f"m{i}" for i in range(1, depth)]
    rels = [f"r{i}" for i in range(1, depth + 1)]
    seq = ["(a)"] + [f"({m})" for m in mids] + ["(b)"]
    pattern = seq[0]
    for rel, node in zip(rels, seq[1:]):
        pattern += f"-[{rel}]-{node}"
    where = (" WHERE " + " AND ".join(f"{m}.degree_core <= $hub" for m in mids)) if mids else ""
    nodes = "[x IN [a" + "".join(f", {m}" for m in mids) + ", b] | [x.node_id, x.name, labels(x), x.degree_core, x.sourceID]]"
    edges = "[r IN [" + ", ".join(rels) + "] | [type(r), r.link, r.role_category]]"
    return (f"MATCH (a {{node_id: $s}}), (b {{node_id: $t}}) MATCH {pattern}{where} "
            f"RETURN {nodes} AS nodes, {edges} AS edges LIMIT {limit}")
REF_Q = """MATCH (x {node_id: $s}), (y {node_id: $t})
CALL algo.SPpaths({sourceNode: x, targetNode: y, relDirection: 'both', pathCount: 1})
YIELD path RETURN [[n IN nodes(path) | [n.node_id, n.name, labels(n), n.degree_core]], length(path)]"""
# No maxLen on the reference: bounded SPpaths uses exhaustive DFS enumeration
# (blows up near dense pockets), while unbounded takes the Dijkstra fast path.


def _db():
    return FalkorDB(host=HOST, port=PORT).select_graph(GRAPH)


def _weight(degree, n):
    return math.log((n + 1) / (degree + 1))


def strongest_connection(source_id, target_id, hub_threshold=1000, max_hops=4):
    """Most informative hub-respecting path; see module docstring."""
    max_hops = max(1, int(max_hops))
    g = _db()
    n_total = g.query("MATCH (n) RETURN count(n) LIMIT 1", timeout=QUERY_TIMEOUT_MS).result_set[0][0]
    rows, depth_used, timeout_note = [], None, None
    # Iterative deepening: exact-depth queries prune far better than one
    # open-ended MATCH with ORDER BY, and the first non-empty depth is the
    # shortest hub-respecting length, so no sort is needed.
    for depth in range(1, max_hops + 1):
        cypher = candidate_query(depth, CANDIDATE_LIMIT)
        try:
            rows = g.query(cypher, {"s": source_id, "t": target_id, "hub": hub_threshold},
                           timeout=QUERY_TIMEOUT_MS).result_set
        except Exception:
            timeout_note = f"candidate query timed out at depth {depth} ({QUERY_TIMEOUT_MS}ms)"
            rows = []
            break
        if rows:
            depth_used = depth
            break
    cypher = candidate_query(depth_used or max_hops, CANDIDATE_LIMIT)
    # Unfiltered exact-shortest reference (fast even through hubs) tells us
    # whether the hub filter changed the outcome, and names the hubs on it.
    ref_rows = []
    ref_note = None
    try:
        ref_rows = g.query(REF_Q, {"s": source_id, "t": target_id},
                           timeout=QUERY_TIMEOUT_MS).result_set
    except Exception:
        ref_note = f"reference query timed out ({QUERY_TIMEOUT_MS}ms)"
    ref_nodes, ref_len = ref_rows[0][0] if ref_rows else ([[], None])
    excluded = [{"node_id": r[0], "name": r[1], "labels": r[2], "degree_core": r[3]}
                for r in ref_nodes if r[3] is not None and r[3] > hub_threshold]
    if not rows:
        notes = [n for n in (timeout_note, ref_note) if n]
        notes.append("no hub-respecting path; hubs on reference path listed"
                     if ref_len is not None else "no path within max_hops")
        return {"source_id": source_id, "target_id": target_id, "hub_threshold": hub_threshold,
                "max_hops": max_hops, "path": None, "score": None, "breakdown": [],
                "excluded_hubs": excluded, "reference_length": ref_len, "cypher": cypher,
                "note": "; ".join(notes)}
    best, best_score, best_down = None, None, None
    for nodes, edges in rows:
        down = [{"node_id": r[0], "name": r[1], "degree_core": r[3],
                 "weight": _weight(r[3] or 0, n_total)} for r in nodes[1:-1]]
        # Mean rarity per intermediate node: padding a path with extra hops
        # must not raise its score, so sum (which grows with length) is wrong.
        score = sum(d["weight"] for d in down) / max(1, len(down))
        if best_score is None or score > best_score:
            best, best_score, best_down = (nodes, edges), score, down
    nodes, edges = best
    return {"source_id": source_id, "target_id": target_id, "hub_threshold": hub_threshold,
            "max_hops": max_hops,
            "path": {"length": len(edges),
                     "nodes": [{"node_id": r[0], "name": r[1], "labels": r[2],
                                "degree_core": r[3], "sourceID": r[4]} for r in nodes],
                     "edges": [{"rel_type": r[0], "link": r[1], "role_category": r[2]} for r in edges]},
            "score": best_score, "breakdown": best_down, "excluded_hubs": excluded,
            "reference_length": ref_len, "cypher": cypher,
            "note": "; ".join(n for n in (timeout_note, ref_note) if n) or None}
