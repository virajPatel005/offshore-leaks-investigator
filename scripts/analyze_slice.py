"""Read-only slice analysis for D4 (no DB, no import code).

Slice = nodes whose node-file sourceID == SLICE ("Offshore Leaks");
an edge is internal when BOTH endpoint IDs are in the slice.
Degree = undirected distinct neighbors over core internal edges only.
"""
import csv
import math
import os
import resource
import time

DATA_DIR = os.getenv("DATA_DIR", os.path.expanduser("~/data/icij"))
SLICE = "Offshore Leaks"  # dataset-specific constant lives here per D11
CORE = {"officer_of", "intermediary_of", "registered_address"}
NODE_FILES = {  # file -> short type label
    "nodes-addresses.csv": "address",
    "nodes-entities.csv": "entity",
    "nodes-intermediaries.csv": "intermediary",
    "nodes-officers.csv": "officer",
    "nodes-others.csv": "other",
}


def pct(sorted_vals, p):
    if not sorted_vals:
        return 0
    k = min(len(sorted_vals) - 1, max(0, math.ceil(p / 100 * len(sorted_vals)) - 1))
    return sorted_vals[k]


def main():
    t0 = time.perf_counter()
    per_type = {t: set() for t in NODE_FILES.values()}
    name_of = {}
    for fn, typ in NODE_FILES.items():
        with open(os.path.join(DATA_DIR, fn), newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("sourceID") != SLICE:
                    continue
                nid = row.get("node_id", "")
                per_type[typ].add(nid)
                if nid not in name_of:  # first-seen display name wins
                    disp = (row.get("name") or "").strip() or (row.get("address") or "").strip()
                    name_of[nid] = (disp[:60].replace("|", "/"), typ)
    all_ids = set().union(*per_type.values())
    off, inter = per_type["officer"], per_type["intermediary"]
    colliding = off & inter
    inter_only = inter - off
    off_only = off - inter

    total = internal = mismatch_off = mismatch_inter = 0
    touch_total = 0
    touch_by_rel = {}
    neigh = {}  # nid -> set of distinct neighbors (core internal, undirected)
    with open(os.path.join(DATA_DIR, "relationships.csv"), newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            total += 1
            s, e, r = row.get("node_id_start", ""), row.get("node_id_end", ""), row.get("rel_type", "")
            if s not in all_ids or e not in all_ids:
                continue
            internal += 1
            if s in colliding or e in colliding:
                touch_total += 1
                touch_by_rel[r] = touch_by_rel.get(r, 0) + 1
            if r == "officer_of" and s in inter_only:
                mismatch_off += 1
            elif r == "intermediary_of" and s in off_only:
                mismatch_inter += 1
            if r in CORE:  # undirected distinct neighbors
                ns = neigh.get(s)
                if ns is None:
                    neigh[s] = {e}
                else:
                    ns.add(e)
                ne = neigh.get(e)
                if ne is None:
                    neigh[e] = {s}
                else:
                    ne.add(s)

    deg = {nid: len(v) for nid, v in neigh.items()}
    for nid in all_ids:  # isolated slice nodes have degree 0
        if nid not in deg:
            deg[nid] = 0
    type_of = {}
    for typ, ids in per_type.items():
        for nid in ids:
            type_of.setdefault(nid, []).append(typ)
    print(f"slice={SLICE} data_dir={DATA_DIR}")
    counts = " ".join(f"{t}={len(per_type[t])}" for t in ("address", "entity", "intermediary", "officer", "other"))
    print(f"nodes_in_slice {counts} unique={len(all_ids)}")
    print(f"edges scanned={total} internal_both_ends={internal}")
    print(f"D4 ids_in_both_officer_and_intermediary={len(colliding)} edges_touching={touch_total}")
    print("D4_touch_by_rel " + " ".join(f"{k}={v}" for k, v in sorted(touch_by_rel.items(), key=lambda kv: -kv[1])))
    print(f"mismatch officer_of_from_intermediary_only={mismatch_off} intermediary_of_from_officer_only={mismatch_inter}")
    for typ in ("address", "entity", "intermediary", "officer"):
        vals = sorted(deg[n] for n in per_type[typ]) if per_type[typ] else []
        print(f"deg_core {typ} n={len(vals)} p50={pct(vals,50)} p90={pct(vals,90)} p99={pct(vals,99)} max={vals[-1] if vals else 0}")
    top5 = sorted(deg.items(), key=lambda kv: kv[1], reverse=True)[:5]
    for nid, d in top5:
        nm, tp = name_of.get(nid, ("", "?"))
        extra = "+".join(type_of.get(nid, [tp]))
        print(f"hub {nm} | {extra} | degree={d}")
    rss_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    print(f"peak_rss_mb={rss_mb:.0f} runtime_s={time.perf_counter()-t0:.0f}")


if __name__ == "__main__":
    main()
