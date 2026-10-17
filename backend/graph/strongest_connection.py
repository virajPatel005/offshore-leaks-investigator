"""Generic graph tool: strongest recorded connection between two nodes.

Method (D3): candidates come from Cypher with a hub predicate on every
intermediate node of an exact-depth chain (iterative deepening, so the first
non-empty depth is the shortest hub-respecting length); the small candidate
set is ranked in Python by mean rarity weight per intermediate node. Endpoints
are fixed by the caller, so only intermediate nodes contribute to the score.
The same candidate rows also feed the ranked `paths` list (D17): one spare row
over the cap reveals truncation, and no deeper queries are run for it.
"""
import math
import os

from falkordb import FalkorDB

from backend.graph.rel_types import possible_matches

HOST = os.getenv("FALKORDB_HOST", "localhost")
PORT = int(os.getenv("FALKORDB_PORT", "6379"))
GRAPH = os.getenv("GRAPH_NAME", "offshore")
PATHS_CAP = 8
# The candidate rows are the same single query per depth as before; the spare
# row only reveals that more candidates exist than the cap shows.
CANDIDATE_LIMIT = PATHS_CAP + 1
QUERY_TIMEOUT_MS = 15000
DIRECT_NOTE = "not applicable: direct link, no intermediate nodes"

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
    edges = "[r IN [" + ", ".join(rels) + "] | [type(r), r.link, r.role_category, r.status, r.start_date, r.end_date, r.sourceID]]"
    return (f"MATCH (a {{node_id: $s}}), (b {{node_id: $t}}) MATCH {pattern}{where} "
            f"RETURN {nodes} AS nodes, {edges} AS edges LIMIT {limit}")
REF_Q = """MATCH (x {node_id: $s}), (y {node_id: $t})
CALL algo.SPpaths({sourceNode: x, targetNode: y, relDirection: 'both', pathCount: 1})
YIELD path RETURN [n IN nodes(path) | [n.node_id, n.name, labels(n), n.degree_core, n.sourceID]] AS nodes_out,
[r IN relationships(path) | [type(r), r.link, r.role_category, r.status, r.start_date, r.end_date, r.sourceID]] AS edges_out,
length(path) AS hops"""
# No maxLen on the reference: bounded SPpaths uses exhaustive DFS enumeration
# (blows up near dense pockets), while unbounded takes the Dijkstra fast path.


def _db():
    return FalkorDB(host=HOST, port=PORT).select_graph(GRAPH)


def _weight(degree, n):
    return math.log((n + 1) / (degree + 1))


def _node_dicts(rows, hub_threshold=None):
    out = []
    for r in rows:
        d = {"node_id": r[0], "name": r[1], "labels": r[2], "degree_core": r[3], "sourceID": r[4]}
        if hub_threshold is not None:
            d["is_hub"] = r[3] is not None and r[3] > hub_threshold
        out.append(d)
    return out


def _edge_dicts(rows):
    return [{"rel_type": r[0], "link": r[1], "role_category": r[2],
             "status": r[3], "start_date": r[4], "end_date": r[5],
             "sourceID": r[6]} for r in rows]


def strongest_connection(source_id, target_id, hub_threshold=1000, max_hops=4):
    """Most informative hub-respecting path + the ranked `paths` list; see module docstring."""
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
    ref_nodes, ref_edges, ref_len = ref_rows[0] if ref_rows else ([], [], None)
    excluded = [{"node_id": r[0], "name": r[1], "labels": r[2], "degree_core": r[3]}
                for r in ref_nodes if r[3] is not None and r[3] > hub_threshold]
    # Rank every candidate row from the first non-empty depth (they are already
    # in memory, so the list costs no extra traversal), best first. Distinct =
    # different node sequence or different relationship sequence.
    paths, seen = [], set()
    for nodes, edges in rows:
        key = (tuple(r[0] for r in nodes), tuple(r[0] for r in edges))
        if key in seen:
            continue
        seen.add(key)
        down = [{"node_id": r[0], "name": r[1], "degree_core": r[3],
                 "weight": _weight(r[3] or 0, n_total)} for r in nodes[1:-1]]
        if down:
            # Mean rarity per intermediate node: padding a path with extra hops
            # must not raise its score, so sum (which grows with length) is wrong.
            score, score_note = sum(d["weight"] for d in down) / len(down), None
        else:
            # Direct link: no intermediate nodes, so nothing to rank; a numeric
            # score would be meaningless (not 0.0).
            score, score_note = None, DIRECT_NOTE
        path_edges = _edge_dicts(edges)
        soft = possible_matches(path_edges)
        paths.append({"length": len(edges), "score": score, "score_note": score_note,
                      "includes_possible_match": bool(soft), "possible_match_edges": soft,
                      "nodes": _node_dicts(nodes), "edges": path_edges, "_down": down})
    paths.sort(key=lambda p: (p["score"] is None, -(p["score"] or 0.0)))
    truncated = len(paths) > PATHS_CAP
    paths = paths[:PATHS_CAP]
    if not rows:
        notes = [n for n in (timeout_note, ref_note) if n]
        blocked = ref_len is not None
        notes.append("no hub-respecting path; hubs on reference path listed" if blocked
                     else "no path within max_hops")
        reference_path = None
        if blocked:
            hub_names = [str(r[1] or r[0]) for r in ref_nodes
                         if r[3] is not None and r[3] > hub_threshold]
            reference_path = {
                "length": ref_len, "excluded": True,
                "nodes": _node_dicts(ref_nodes, hub_threshold), "edges": _edge_dicts(ref_edges),
                "note": "excluded: the unfiltered shortest path runs through hub(s) "
                        + ", ".join(hub_names) + "; it is not counted as an informative connection"}
        return {"source_id": source_id, "target_id": target_id, "hub_threshold": hub_threshold,
                "max_hops": max_hops, "path": None, "score": None, "breakdown": [],
                "includes_possible_match": False, "possible_match_edges": [],
                "paths": [], "paths_truncated": False, "reference_path": reference_path,
                "excluded_hubs": excluded, "reference_length": ref_len, "cypher": cypher,
                "note": "; ".join(notes)}
    best = paths[0]
    best_down = best.pop("_down")
    for p in paths[1:]:
        p.pop("_down", None)
    notes = [n for n in (timeout_note, ref_note) if n]
    if truncated:
        notes.append(f"more hub-respecting paths exist than the top {PATHS_CAP} shown")
    if best["score_note"]:
        notes.append("score " + best["score_note"])
    if best["possible_match_edges"]:
        notes.append("path includes possible-match edge(s) (" + ", ".join(best["possible_match_edges"])
                     + "): records are linked, identity is not confirmed")
    return {"source_id": source_id, "target_id": target_id, "hub_threshold": hub_threshold,
            "max_hops": max_hops,
            "path": {"length": best["length"], "nodes": best["nodes"], "edges": best["edges"]},
            "score": best["score"], "score_note": best["score_note"], "breakdown": best_down,
            "includes_possible_match": best["includes_possible_match"],
            "possible_match_edges": best["possible_match_edges"],
            "paths": paths, "paths_truncated": truncated, "reference_path": None,
            "excluded_hubs": excluded,
            "reference_length": ref_len, "cypher": cypher,
            "note": "; ".join(notes) or None}
