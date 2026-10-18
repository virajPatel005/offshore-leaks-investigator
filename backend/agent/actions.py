"""Deterministic UI actions over two nodes picked in the graph; no LLM involved.

The UI lets the user select two nodes and click "Strongest connection" or
"What do these share?". Both call the existing graph tools directly (Q6 / Q8)
and wrap the result in the same envelope the agent returns, so the thread has
one card shape and the trace panel still explains the query behind the answer.
"""
from backend.agent.agent import LIMITATIONS
from backend.graph.neighbors import get_node
from backend.graph.shared_neighbors import shared_neighbors
from backend.graph.strongest_connection import strongest_connection

HUB_THRESHOLD = 1000
MAX_HOPS = 4
SHARED_LIMIT = 20


def _name(n):
    return n.get("display_name") or n.get("name") or str(n["node_id"])


def _slim(n):
    return {"node_id": n["node_id"], "name": n.get("name"), "labels": n.get("labels") or [],
            "display_name": n.get("display_name"), "degree_core": n.get("degree_core") or 0,
            "country_codes": n.get("country_codes"), "sourceID": n.get("sourceID")}


def _missing(a_id, b_id, a, b):
    gone = [i for i, n in ((a_id, a), (b_id, b)) if not n]
    return f"no node with node_id {', '.join(gone)}" if gone else None


def strongest_action(a_id, b_id):
    """Q6 over two client-picked node ids, rendered as a thread card."""
    if str(a_id) == str(b_id):
        return {"error": "pick two different nodes"}
    a, b = get_node(a_id), get_node(b_id)
    err = _missing(a_id, b_id, a, b)
    if err:
        return {"error": err}
    res = strongest_connection(a_id, b_id, HUB_THRESHOLD, MAX_HOPS)
    path = res.get("path") or {}
    nodes, hops = path.get("nodes") or [], path.get("length")
    if nodes:
        mids = [_name(n) for n in nodes[1:-1]]
        answer = (f"Recorded path from {_name(a)} to {_name(b)}: {hops} hop(s)"
                  + (f" via {', '.join(mids)}" if mids else " (direct link)"))
        if res.get("score") is None and res.get("score_note"):
            answer += f". Score: {res['score_note']}."
        else:
            answer += (f". Connection relevance score {res['score']:.2f} "
                       "(higher = rarer, more informative link).")
        n_paths = len(res.get("paths") or [])
        if n_paths > 1:
            answer += (f" {n_paths} recorded paths ranked, strongest first"
                       + ("; the Paths panel shows 4 at a time, others on the next page."
                          if n_paths > 4 else ", all shown in the Paths panel."))
        if res.get("paths_truncated"):
            answer += " More paths exist than the top 8 shown."
    else:
        answer = f"No hub-respecting path within {MAX_HOPS} hops between {_name(a)} and {_name(b)}."
        if res.get("reference_length"):
            hubs = ", ".join(_name(h) for h in res.get("excluded_hubs") or [])
            answer += (f" An unfiltered reference path exists at {res['reference_length']} hops"
                       + (f" through {hubs}." if hubs else "."))
            answer += (" It is excluded from the ranking and not counted as an informative"
                       " connection.")
    trace = [{"step": 1, "tool": "strongest_connection_tool",
              "args": {"source_id": a_id, "target_id": b_id,
                       "hub_threshold": HUB_THRESHOLD, "max_hops": MAX_HOPS},
              "result_summary": {"path_found": bool(nodes), "hops": hops,
                                 "score": round(res["score"], 3) if res.get("score") is not None else None,
                                 "n_paths": len(res.get("paths") or []),
                                 "excluded_hubs": len(res.get("excluded_hubs") or [])},
              "cypher": res.get("cypher")}]
    return {"question": f"Strongest connection between {_name(a)} and {_name(b)}",
            "answer": answer, "mode": "strongest", "replay": True, "deterministic": True,
            "evidence_path": {"nodes": nodes, "edges": path.get("edges") or []} if nodes else {},
            "score": res.get("score"), "score_note": res.get("score_note"),
            "score_breakdown": res.get("breakdown") or [],
            "paths": res.get("paths") or [], "paths_truncated": bool(res.get("paths_truncated")),
            "reference_path": res.get("reference_path"),
            "excluded_hubs": res.get("excluded_hubs") or [], "shared": [],
            "trace": trace, "candidates": [], "cached": False, "limitations": LIMITATIONS}


def shared_action(a_id, b_id):
    """Q8 over two client-picked node ids, rendered as a thread card."""
    if str(a_id) == str(b_id):
        return {"error": "pick two different nodes"}
    a, b = get_node(a_id), get_node(b_id)
    err = _missing(a_id, b_id, a, b)
    if err:
        return {"error": err}
    res = shared_neighbors(a_id, b_id, HUB_THRESHOLD, SHARED_LIMIT)
    nbrs, hubs = res.get("neighbors") or [], res.get("excluded_hubs") or []
    if nbrs:
        names = ", ".join(_name(n) for n in nbrs[:5])
        more = f" and {len(nbrs) - 5} more" if len(nbrs) > 5 else ""
        answer = (f"{len(nbrs)} shared neighbour(s) above the hub filter between "
                  f"{_name(a)} and {_name(b)}: {names}{more}.")
    elif hubs:
        answer = (f"No affordable shared neighbour: all {len(hubs)} common neighbour(s) are "
                  f"high-degree hubs (degree > {HUB_THRESHOLD}).")
    else:
        answer = f"No shared neighbour within one hop between {_name(a)} and {_name(b)}."
    nodes = [_slim(a)] + [_slim(n) for n in nbrs] + [_slim(b)]
    edges = []
    for n in nbrs:
        for via in n.get("via") or []:
            edges.append({"rel_type": via.get("rel_type"), "link": via.get("link"),
                          "role_category": via.get("role_category"), "status": via.get("status"),
                          "start_date": via.get("start_date"), "end_date": via.get("end_date"),
                          "sourceID": via.get("sourceID"),
                          "source_id": a_id if via.get("side") == "a" else n["node_id"],
                          "target_id": n["node_id"] if via.get("side") == "a" else b_id})
    trace = [{"step": 1, "tool": "shared_neighbors_tool",
              "args": {"id_a": a_id, "id_b": b_id, "hub_threshold": HUB_THRESHOLD,
                       "limit": SHARED_LIMIT},
              "result_summary": {"shared_neighbors": len(nbrs), "excluded_hubs": len(hubs),
                                 "grouped_by_edge_type": res.get("grouped_by_edge_type") or {}},
              "cypher": res.get("cypher")}]
    shared = [{"node_id": n["node_id"], "name": n.get("name"), "labels": n.get("labels") or [],
               "degree_core": n.get("degree_core"), "weight": n.get("weight"),
               "via": [(v.get("rel_type"), v.get("side")) for v in n.get("via") or []]}
              for n in nbrs]
    return {"question": f"What {_name(a)} and {_name(b)} share",
            "answer": answer, "mode": "shared", "replay": False, "deterministic": True,
            "evidence_path": {"nodes": nodes, "edges": edges},
            "score": None, "score_breakdown": [], "excluded_hubs": hubs, "shared": shared,
            "trace": trace, "candidates": [], "cached": False, "limitations": LIMITATIONS}
