"""D4 name-comparison for colliding IDs (read-only, no DB, no import code).

Colliding ID = node_id present in BOTH nodes-officers.csv and
nodes-intermediaries.csv with node sourceID == SLICE.
Degrees reuse the D2 definition: undirected distinct neighbors over
core internal edges only (both endpoints in the slice).
"""
import csv
import os
import resource
import time

DATA_DIR = os.getenv("DATA_DIR", os.path.expanduser("~/data/icij"))
SLICE = "Offshore Leaks"  # dataset-specific constant lives here per D11
CORE = {"officer_of", "intermediary_of", "registered_address"}
HUB_DEGREE = 1000


def norm(s):
    return " ".join((s or "").casefold().split())


def clean(s, n=45):
    return (s or "").strip().replace("|", "/")[:n]


def main():
    t0 = time.perf_counter()
    off, inter = {}, {}
    for fn, store in (("nodes-officers.csv", off), ("nodes-intermediaries.csv", inter)):
        with open(os.path.join(DATA_DIR, fn), newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("sourceID") != SLICE:
                    continue
                store[row.get("node_id", "")] = row
    colliding = sorted(set(off) & set(inter), key=lambda x: (0, int(x)) if x.isdigit() else (1, x))
    same = diff = empty = 0
    cc_same = cc_diff = 0
    shown = 0
    differ_ids = []
    for nid in colliding:
        o, m = off[nid], inter[nid]
        if not (o.get("name") or "").strip() or not (m.get("name") or "").strip():
            empty += 1
        if norm(o.get("name")) == norm(m.get("name")):
            same += 1
        else:
            diff += 1
            differ_ids.append(nid)
            if shown < 5:  # at most 5 examples, nothing more
                print(f"differ {nid} | {clean(o.get('name'))} | {clean(m.get('name'))}")
                shown += 1
        if (o.get("country_codes") or "").strip() == (m.get("country_codes") or "").strip():
            cc_same += 1
        else:
            cc_diff += 1
    slice_ids = set()
    for fn in ("nodes-addresses.csv", "nodes-entities.csv", "nodes-intermediaries.csv",
               "nodes-officers.csv", "nodes-others.csv"):
        with open(os.path.join(DATA_DIR, fn), newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("sourceID") == SLICE:
                    slice_ids.add(row.get("node_id", ""))
    coll_set = set(colliding)
    neigh = {nid: set() for nid in colliding}
    with open(os.path.join(DATA_DIR, "relationships.csv"), newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("rel_type") not in CORE:
                continue
            s, e = row.get("node_id_start", ""), row.get("node_id_end", "")
            if s in coll_set and e in slice_ids:
                neigh[s].add(e)
            if e in coll_set and s in slice_ids:
                neigh[e].add(s)
    big = [(nid, len(neigh[nid])) for nid in differ_ids if len(neigh[nid]) > HUB_DEGREE]
    big.sort(key=lambda kv: -kv[1])
    print(f"colliding_ids={len(colliding)} names_identical={same} names_differ={diff} either_empty={empty}")
    print(f"country_codes match={cc_same} differ={cc_diff}")
    print("sourceID match={} differ=0 (both rows in-slice by construction)".format(len(colliding)))
    print(f"differ_with_degree_over_{HUB_DEGREE}={len(big)} " + " ".join(f"{nid}:{d}" for nid, d in big[:5]))
    rss_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    print(f"peak_rss_mb={rss_mb:.0f} runtime_s={time.perf_counter()-t0:.0f}")


if __name__ == "__main__":
    main()
