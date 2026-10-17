"""Load a prepared slice into FalkorDB via Cypher LOAD CSV.

Order: indexes on node_id per label, then nodes (one file per label set),
then edges one rel_type at a time. File names are ours (safe to inline);
row values stay in the row map. Degrees stored as integers.
`--prepared DIR` reads the CSVs from a subfolder of the container import root
(e.g. prepared_icij mounted as import/icij); default reads the import root.
"""
import argparse
import os
import subprocess
import time

from dotenv import load_dotenv

load_dotenv()

GRAPH = os.getenv("GRAPH_NAME", "offshore")
HOST = os.getenv("FALKORDB_HOST", "localhost")
PORT = int(os.getenv("FALKORDB_PORT", "6379"))
CONTAINER = os.getenv("FALKORDB_CONTAINER", "offshore-investigator-falkordb-1")

LABELS = ("Address", "Entity", "Intermediary", "Officer")
# label set -> (prepared file, Cypher label pattern, property columns)
NODE_LOADS = (
    ("nodes_address.csv", ":Address", ["address", "name", "countries", "country_codes",
                                       "sourceID", "valid_until", "note"]),
    ("nodes_entity.csv", ":Entity", ["name", "original_name", "former_name", "jurisdiction",
                                     "jurisdiction_description", "company_type", "address", "internal_id",
                                     "incorporation_date", "inactivation_date", "struck_off_date", "dorm_date",
                                     "status", "service_provider", "ibcRUC", "country_codes", "countries",
                                     "sourceID", "valid_until", "note"]),
    ("nodes_intermediary.csv", ":Intermediary", ["name", "status", "internal_id", "address", "countries",
                                                "country_codes", "sourceID", "valid_until", "note"]),
    ("nodes_officer.csv", ":Officer", ["name", "countries", "country_codes", "sourceID",
                                       "valid_until", "note"]),
)
EDGE_FILES = (  # (prepared file, relationship type as stored in rel_type)
    ("edges_officer_of.csv", "officer_of"),
    ("edges_registered_address.csv", "registered_address"),
    ("edges_intermediary_of.csv", "intermediary_of"),
    ("edges_underlying.csv", "underlying"),
    ("edges_similar.csv", "similar"),
    ("edges_same_as.csv", "same_as"),
)
# Indexes are per label, but edge endpoints arrive without labels, so each
# endpoint is resolved with one indexed OPTIONAL MATCH per label + coalesce.
EDGE_Q = """LOAD CSV WITH HEADERS FROM 'file://{csv}' AS row
OPTIONAL MATCH (a1:Address {{node_id: row.node_id_start}})
OPTIONAL MATCH (a2:Entity {{node_id: row.node_id_start}})
OPTIONAL MATCH (a3:Intermediary {{node_id: row.node_id_start}})
OPTIONAL MATCH (a4:Officer {{node_id: row.node_id_start}})
OPTIONAL MATCH (b1:Address {{node_id: row.node_id_end}})
OPTIONAL MATCH (b2:Entity {{node_id: row.node_id_end}})
OPTIONAL MATCH (b3:Intermediary {{node_id: row.node_id_end}})
OPTIONAL MATCH (b4:Officer {{node_id: row.node_id_end}})
WITH row, coalesce(a1, a2, a3, a4) AS a, coalesce(b1, b2, b3, b4) AS b
WHERE a IS NOT NULL AND b IS NOT NULL
CREATE (a)-[r:{typ} {{link: row.link, role_category: row.role_category, status: row.status, start_date: row.start_date, end_date: row.end_date, sourceID: row.sourceID}}]->(b)"""


def props(cols):
    return ", ".join([f"{c}: row.{c}" for c in cols])


def run(g, q, params=None):
    t0 = time.perf_counter()
    res = g.query(q, params or {})
    return res, time.perf_counter() - t0


def verify(g, t_all, expect_nodes=278693, expect_edges=562700):
    # Label counts overlap by design (D4): the merged nodes carry two labels,
    # so per-label sums exceed the unique-node total by exactly 1,139.
    print(f"graph={GRAPH}")
    counts = [(l, g.query(f"MATCH (n:{l}) RETURN count(n) LIMIT 1").result_set[0][0]) for l in LABELS]
    unique = g.query("MATCH (n) RETURN count(n) LIMIT 1").result_set[0][0]
    print("nodes " + " ".join(f"{l}={c}" for l, c in counts) + f" unique={unique} CHECK={'OK' if unique == expect_nodes else 'MISMATCH'}")
    ecounts = [(t, g.query(f"MATCH ()-[r:{t}]->() RETURN count(r) LIMIT 1").result_set[0][0]) for _, t in EDGE_FILES]
    e_total = sum(c for _, c in ecounts)
    print("edges " + " ".join(f"{t}={c}" for t, c in ecounts) + f" total={e_total} CHECK={'OK' if e_total == expect_edges else 'MISMATCH'}")
    dirs = []
    for _, t in EDGE_FILES:
        a, b = g.query(f"MATCH (x)-[r:{t}]->(y) RETURN labels(x), labels(y) LIMIT 1").result_set[0]
        dirs.append(f"{t}:" + "+".join(a) + "->" + "+".join(b))
    print("dirs " + " ".join(dirs))
    pid = g.query("MATCH (a:Address) WHERE a.degree_core = 37338 RETURN a.node_id LIMIT 1").result_set[0][0]
    deg = g.query("MATCH (a:Address {node_id: $id})-[r:officer_of|intermediary_of|registered_address]-(n) RETURN count(DISTINCT n) LIMIT 1", {"id": pid}).result_set[0][0]
    print(f"portcullis node_id={pid} core_degree={deg} CHECK={'OK' if deg == 37338 else 'MISMATCH'}")
    print(f"import_total_s={time.perf_counter() - t_all:.0f}")
    try:
        mem = subprocess.run(["docker", "stats", "--no-stream", "--format", "{{.MemUsage}}", CONTAINER],
                             capture_output=True, text=True, timeout=30).stdout.strip()
        print(f"falkordb_mem={mem or 'unavailable'}")
    except Exception as ex:
        print(f"falkordb_mem=unavailable ({ex})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--drop", action="store_true", help="delete the graph and reload")
    ap.add_argument("--verify-only", action="store_true", help="skip loading, only verify")
    ap.add_argument("--prepared", default="", help="subfolder of the import root holding the prepared CSVs")
    ap.add_argument("--expect-nodes", type=int, default=278693, help="CHECK value, default = Offshore Leaks")
    ap.add_argument("--expect-edges", type=int, default=562700, help="CHECK value, default = Offshore Leaks")
    args = ap.parse_args()
    prefix = (args.prepared.strip("/") + "/") if args.prepared.strip("/") else ""
    from falkordb import FalkorDB

    db = FalkorDB(host=HOST, port=PORT)
    g = db.select_graph(GRAPH)
    t_all = time.perf_counter()
    if args.verify_only:
        verify(g, t_all, args.expect_nodes, args.expect_edges)
        return
    if args.drop:
        g.delete()
        g = db.select_graph(GRAPH)
        print("dropped graph")
    else:
        n0 = g.query("MATCH (n) RETURN count(n) LIMIT 1").result_set[0][0]
        if n0:
            raise SystemExit(f"graph {GRAPH} already has {n0} nodes; rerun with --drop")
    for label in LABELS:
        _, dt = run(g, f"CREATE INDEX FOR (n:{label}) ON (n.node_id)")
        print(f"index {label}.node_id {dt:.1f}s")
    for csv, labels, cols in NODE_LOADS:
        _, dt = run(g, f"LOAD CSV WITH HEADERS FROM 'file://{prefix}{csv}' AS row "
                       f"CREATE (n{labels} {{node_id: row.node_id, {props(cols)}, "
                       "degree_core: toInteger(row.degree_core), degree_all: toInteger(row.degree_all)})")
        print(f"nodes {csv} {dt:.1f}s")
    _, dt = run(g, "LOAD CSV WITH HEADERS FROM 'file://" + prefix + "nodes_intermediary_officer.csv' AS row\n"
                   "CREATE (n:Intermediary:Officer {node_id: row.node_id, name: row.name, countries: row.countries,\n"
                   "country_codes: row.country_codes, sourceID: row.sourceID, valid_until: row.valid_until, note: row.note,\n"
                   "status: row.status, internal_id: row.internal_id, address: row.address,\n"
                   "officer_name: row.officer_name, intermediary_name: row.intermediary_name,\n"
                   "name_mismatch: row.name_mismatch = 'True',\n"
                   "degree_core: toInteger(row.degree_core), degree_all: toInteger(row.degree_all)})")
    print(f"nodes nodes_intermediary_officer.csv {dt:.1f}s")
    for csv, typ in EDGE_FILES:
        _, dt = run(g, EDGE_Q.format(csv=prefix + csv, typ=typ))
        print(f"edges {csv} {dt:.1f}s")
    print(f"load_total_s={time.perf_counter() - t_all:.0f}")

    # --- verification (keep to 15 lines) ---
    verify(g, t_all, args.expect_nodes, args.expect_edges)


if __name__ == "__main__":
    main()
