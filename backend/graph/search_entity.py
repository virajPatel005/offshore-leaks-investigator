"""Generic graph tool: name search over Entity/Officer/Intermediary nodes.

Uses FalkorDB full-text indexes (one per label); exact matches sort first.
All filters run engine-side; results are size-capped.
"""
import os
import re

from falkordb import FalkorDB

HOST = os.getenv("FALKORDB_HOST", "localhost")
PORT = int(os.getenv("FALKORDB_PORT", "6379"))
GRAPH = os.getenv("GRAPH_NAME", "offshore")
LABELS = ("Entity", "Officer", "Intermediary")
QUERY_TIMEOUT_MS = 15000
_indexed = False


def _db():
    return FalkorDB(host=HOST, port=PORT).select_graph(GRAPH)


def ensure_search_indexes(g=None):
    """Create name full-text indexes if missing (idempotent)."""
    global _indexed
    if _indexed:
        return
    g = g or _db()
    for label in LABELS:
        try:
            g.query(f"CREATE FULLTEXT INDEX FOR (n:{label}) ON (n.name)")
        except Exception as ex:
            if "already index" not in str(ex).lower():
                raise
    _indexed = True


Q = """CALL db.idx.fulltext.queryNodes('%s', $q) YIELD node, score
RETURN node.node_id, node.name, labels(node), node.country_codes,
node.degree_core, node.sourceID, score LIMIT %d"""
Q_COUNTRY = """CALL db.idx.fulltext.queryNodes('%s', $q) YIELD node, score
WHERE ANY(c IN split(node.country_codes, ',') WHERE trim(c) = $country)
RETURN node.node_id, node.name, labels(node), node.country_codes,
node.degree_core, node.sourceID, score LIMIT %d"""


def search_entity(name, label=None, country=None, limit=10):
    """Name candidates with node_id, labels, country, degree; exact first."""
    limit = max(1, min(int(limit), 50))
    country = (country or "").strip()
    labels = (label,) if label else LABELS
    if any(l not in LABELS for l in labels):
        raise ValueError(f"label must be one of {LABELS}")
    g = _db()
    ensure_search_indexes(g)
    per_label = max(limit, 10)
    found, cypher = [], []
    for lab in labels:
        # Country predicate is a separate query shape: a single WHERE with an
        # empty-string comparison filtered out every row (no short-circuit on
        # missing properties), so the branch stays in Python, not in Cypher.
        qq = (Q_COUNTRY if country else Q) % (lab, per_label)
        cypher.append(qq)
        rows = g.query(qq, {"q": name, "country": country}, timeout=QUERY_TIMEOUT_MS).result_set
        found.extend({"node_id": r[0], "name": r[1], "labels": r[2], "country_codes": r[3],
                      "degree_core": r[4], "sourceID": r[5], "_score": r[6] or 0} for r in rows)
    norm = (name or "").casefold().strip()
    # Exact match first, then prefix, then full-text score; de-dupe by node_id.
    seen, ranked = set(), []
    for tier in (0, 1, 2):
        tier_rows = [r for r in found if r["node_id"] not in seen and (
            (r["name"] or "").casefold().strip() == norm if tier == 0 else
            (r["name"] or "").casefold().strip().startswith(norm) if tier == 1 else True)]
        tier_rows.sort(key=lambda r: -r["_score"])
        for r in tier_rows:
            seen.add(r["node_id"])
            ranked.append(r)
    for r in ranked:
        del r["_score"]
    return {"query": name, "label": label, "country": country or None,
            "results": ranked[:limit], "cypher": cypher}
