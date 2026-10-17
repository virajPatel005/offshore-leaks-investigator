"""Build load-ready slice files (no DB writes, no import code).

Reads source CSVs from DATA_DIR; with no arguments writes DATA_DIR/prepared/
for the Offshore Leaks slice exactly as before. `--slices "A,B" --out DIR`
builds a multi-dataset graph: nodes with node-file sourceID in the set,
edges kept iff both ends are inside, degrees recomputed over that union.
Degrees follow D2: undirected distinct neighbors over in-slice edges.
"""
import argparse
import csv
import os
import re
import resource
import time

DATA_DIR = os.getenv("DATA_DIR", "/home/viraj/data/icij")
SLICE = "Offshore Leaks"  # dataset-specific default lives here per D11
OUT = os.path.join(DATA_DIR, "prepared")
CORE = {"officer_of", "intermediary_of", "registered_address"}
NODE_FILES = {  # source file -> label set
    "nodes-addresses.csv": "address",
    "nodes-entities.csv": "entity",
    "nodes-intermediaries.csv": "intermediary",
    "nodes-officers.csv": "officer",
    "nodes-others.csv": "other",
}
# D7 taxonomy, first match wins in listed order; raw link is always kept.
ROLE_RULES = (
    ("ownership", ("beneficial owner", "shareholder", "beneficiar", "owner")),
    ("management", ("managing director", "director", "president", "chairman", "manager")),
    ("admin_legal", ("power of attorney", "legal representative", "secretary", "signator",
                     "proxy", "proxies", "attorney", "representative")),
    ("financial_compliance", ("auditor", "audit")),
)


def role_of(link):
    t = (link or "").casefold().strip()
    for cat, keys in ROLE_RULES:
        if any(k in t for k in keys):
            return cat
    return "unknown"


def norm(s):
    return " ".join((s or "").casefold().split())


def safe(s):
    return re.sub(r"[^a-z0-9]+", "_", (s or "").strip().lower()).strip("_")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slices", default=SLICE, help="comma-separated node sourceID values")
    ap.add_argument("--out", default=OUT, help="output directory (must be empty)")
    ap.add_argument("--expect-nodes", type=int, default=278693, help="CHECK value, default = Offshore Leaks")
    ap.add_argument("--expect-edges", type=int, default=562700, help="CHECK value, default = Offshore Leaks")
    args = ap.parse_args()
    slices = {s.strip() for s in args.slices.split(",") if s.strip()}
    out_dir = args.out
    t0 = time.perf_counter()
    if os.path.isdir(out_dir) and os.listdir(out_dir):
        raise SystemExit(f"refusing to mix with existing files in {out_dir}")
    os.makedirs(out_dir, exist_ok=True)
    ids = {t: set() for t in NODE_FILES.values()}  # label set -> slice ids
    for fn, typ in NODE_FILES.items():
        with open(os.path.join(DATA_DIR, fn), newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("sourceID") not in slices:
                    continue
                ids[typ].add(row.get("node_id", ""))
    colliding = ids["officer"] & ids["intermediary"]
    pairs = {nid: [None, None] for nid in colliding}  # id -> [officer row, intermediary row]
    with open(os.path.join(DATA_DIR, "nodes-officers.csv"), newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("sourceID") in slices and row.get("node_id", "") in pairs:
                pairs[row["node_id"]][0] = row
    with open(os.path.join(DATA_DIR, "nodes-intermediaries.csv"), newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("sourceID") in slices and row.get("node_id", "") in pairs:
                pairs[row["node_id"]][1] = row
    inside = set().union(*ids.values())
    only_inter = ids["intermediary"] - ids["officer"]
    only_off = ids["officer"] - ids["intermediary"]

    deg_core, deg_all = {}, {}
    edge_counts, role_counts = {}, {}
    writers = {}

    def bump(store, a, b):
        s = store.get(a)
        if s is None:
            store[a] = {b}
        else:
            s.add(b)

    with open(os.path.join(DATA_DIR, "relationships.csv"), newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            s, e = row.get("node_id_start", ""), row.get("node_id_end", "")
            if s not in inside or e not in inside:
                continue
            r = row.get("rel_type", "")
            rc = role_of(row.get("link"))
            w = writers.get(r)
            if w is None:
                fh = open(os.path.join(out_dir, f"edges_{safe(r) or 'unknown'}.csv"), "w", newline="", encoding="utf-8")
                w = csv.DictWriter(fh, fieldnames=["node_id_start", "node_id_end", "rel_type", "link",
                                                   "role_category", "status", "start_date", "end_date", "sourceID"])
                w.writeheader()
                writers[r] = (w, fh)
            else:
                w = w[0]
            w.writerow({"node_id_start": s, "node_id_end": e, "rel_type": r, "link": row.get("link", ""),
                        "role_category": rc, "status": row.get("status", ""),
                        "start_date": row.get("start_date", ""), "end_date": row.get("end_date", ""),
                        "sourceID": row.get("sourceID", "")})
            edge_counts[r] = edge_counts.get(r, 0) + 1
            role_counts[rc] = role_counts.get(rc, 0) + 1
            bump(deg_all, s, e)
            bump(deg_all, e, s)
            if r in CORE:
                bump(deg_core, s, e)
                bump(deg_core, e, s)
    for _, fh in writers.values():
        fh.close()

    node_counts = {}
    # (label set, member ids, base source file, extra columns)
    for label, members, src in (("address", ids["address"], "nodes-addresses.csv"),
                                ("entity", ids["entity"], "nodes-entities.csv"),
                                ("intermediary", only_inter, "nodes-intermediaries.csv"),
                                ("officer", only_off, "nodes-officers.csv"),
                                ("other", ids["other"], "nodes-others.csv")):
        with open(os.path.join(DATA_DIR, src), newline="", encoding="utf-8") as f:
            rdr = csv.DictReader(f)
            fields = list(rdr.fieldnames) + ["degree_core", "degree_all"]
            out = open(os.path.join(out_dir, f"nodes_{label}.csv"), "w", newline="", encoding="utf-8")
            w = csv.DictWriter(out, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            n = 0
            for row in rdr:
                if row.get("sourceID") not in slices or row.get("node_id", "") not in members:
                    continue
                row["degree_core"] = len(deg_core.get(row["node_id"], ()))
                row["degree_all"] = len(deg_all.get(row["node_id"], ()))
                w.writerow(row)
                n += 1
            out.close()
        node_counts[label] = n
    both_fields = (["node_id", "name", "countries", "country_codes", "sourceID", "valid_until", "note",
                    "status", "internal_id", "address", "officer_name", "intermediary_name", "name_mismatch",
                    "degree_core", "degree_all"])
    out = open(os.path.join(out_dir, "nodes_intermediary_officer.csv"), "w", newline="", encoding="utf-8")
    w = csv.DictWriter(out, fieldnames=both_fields, extrasaction="ignore")
    w.writeheader()
    n = 0
    for nid, (o_row, m_row) in pairs.items():
        o_row, m_row = o_row or {}, m_row or {}
        mismatch = norm(o_row.get("name")) != norm(m_row.get("name"))
        merged = {"node_id": nid, "name": o_row.get("name") or m_row.get("name"),
                  "countries": o_row.get("countries") or m_row.get("countries"),
                  "country_codes": o_row.get("country_codes") or m_row.get("country_codes"),
                  "sourceID": o_row.get("sourceID") or m_row.get("sourceID"), "valid_until": o_row.get("valid_until") or m_row.get("valid_until"),
                  "note": o_row.get("note") or m_row.get("note"),
                  "status": m_row.get("status", ""), "internal_id": m_row.get("internal_id", ""),
                  "address": m_row.get("address", ""),
                  "officer_name": o_row.get("name", "") if mismatch else "",
                  "intermediary_name": m_row.get("name", "") if mismatch else "",
                  "name_mismatch": str(mismatch),
                  "degree_core": len(deg_core.get(nid, ())), "degree_all": len(deg_all.get(nid, ()))}
        w.writerow(merged)
        n += 1
    out.close()
    node_counts["intermediary_officer"] = n

    n_total = sum(node_counts.values())
    e_total = sum(edge_counts.values())
    order = ["address", "entity", "intermediary", "officer", "intermediary_officer", "other"]
    print(f"prepared_dir={out_dir} slices={','.join(sorted(slices))}")
    print("nodes " + " ".join(f"{k}={node_counts.get(k, 0)}" for k in order) + f" total={n_total} CHECK={'OK' if n_total == args.expect_nodes else 'MISMATCH'}")
    print("edges " + " ".join(f"{safe(k)}={v}" for k, v in sorted(edge_counts.items(), key=lambda kv: -kv[1])) + f" total={e_total} CHECK={'OK' if e_total == args.expect_edges else 'MISMATCH'}")
    print("role_category " + " ".join(f"{k}={v}" for k, v in sorted(role_counts.items(), key=lambda kv: -kv[1])))
    rss_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    print(f"peak_rss_mb={rss_mb:.0f} runtime_s={time.perf_counter()-t0:.0f}")


if __name__ == "__main__":
    main()
