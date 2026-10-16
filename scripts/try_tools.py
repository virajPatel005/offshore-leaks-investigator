"""Run all three graph tools on fixed demo pairs; print a short summary."""
import sys
import time

sys.path.insert(0, "backend")

from graph.search_entity import search_entity
from graph.shared_neighbors import shared_neighbors
from graph.strongest_connection import strongest_connection

PAIRS = [("123345", "170362"), ("108190", "21573"), ("108052", "123363")]


def main():
    t0 = time.perf_counter()
    for s, t in PAIRS:
        r = strongest_connection(s, t)
        p = f"len={r['path']['length']} score={r['score']:.2f}" if r["path"] else f"no-path ({r['note']})"
        print(f"strongest {s}->{t}: {p}; hubs-excluded={len(r['excluded_hubs'])}")
    r = search_entity("Portcullis", limit=3)
    print(f"search 'Portcullis': {[x['name'][:38] for x in r['results']]}")
    r = search_entity("Portcullis", country="VGB", limit=3)
    print(f"search 'Portcullis' VGB: {[(x['name'][:30], x['country_codes']) for x in r['results']]}")
    s = shared_neighbors("108040", "217870")
    print(f"shared 108040+217870: {len(s['neighbors'])} {s['grouped_by_edge_type']} hubs={len(s['excluded_hubs'])}")
    for n in s["neighbors"]:
        print(f"  {(n['name'] or n['node_id'])[:40]} {n['labels']} deg={n['degree_core']} w={n['weight']:.2f}")
    print(f"tools_total_s={time.perf_counter() - t0:.1f}")


if __name__ == "__main__":
    main()
