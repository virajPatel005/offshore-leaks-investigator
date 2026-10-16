"""CLI runner for strongest_connection (Phase 1d Part 2 check)."""
import argparse
import sys

sys.path.insert(0, "backend")

from graph.strongest_connection import strongest_connection

PAIRS = [("108040", "217870"), ("185676", "123355"), ("123328", "123329")]


def show(res):
    print(f"{res['source_id']} -> {res['target_id']} hub<={res['hub_threshold']} hops<={res['max_hops']}")
    if res["path"] is None:
        print(f"  no path ({res['note']}); reference_length={res['reference_length']}")
    else:
        chain = " -> ".join(n["name"] or n["node_id"] for n in res["path"]["nodes"])
        print(f"  len={res['path']['length']} score={res['score']:.2f} chain={chain[:160]}")
        for d in res["breakdown"]:
            print(f"    +{d['weight']:.2f} {d['name'] or d['node_id']} (deg {d['degree_core']})")
    for h in res["excluded_hubs"]:
        print(f"  hub-excluded: {h['name'] or h['node_id']} (deg {h['degree_core']})")
    if res["note"]:
        print(f"  note: {res['note']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source")
    ap.add_argument("--target")
    ap.add_argument("--hub-threshold", type=int, default=1000)
    ap.add_argument("--max-hops", type=int, default=4)
    args = ap.parse_args()
    pairs = [(args.source, args.target)] if args.source and args.target else PAIRS
    for s, t in pairs:
        show(strongest_connection(s, t, args.hub_threshold, args.max_hops))


if __name__ == "__main__":
    main()
