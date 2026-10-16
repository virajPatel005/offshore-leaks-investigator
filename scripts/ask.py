"""Ask the investigator agent: python scripts/ask.py "question"."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.agent.agent import run


def main():
    if len(sys.argv) < 2:
        raise SystemExit('usage: python scripts/ask.py "question"')
    t0 = time.perf_counter()
    res = run(sys.argv[1])
    print(f"WALL_S={time.perf_counter() - t0:.0f}")
    print("ANSWER:", res["answer"])
    nodes = res["evidence_path"].get("nodes", [])
    print("PATH:", " -> ".join((n.get("name") or n.get("node_id", "?"))[:60] for n in nodes) or "(none)")
    for d in res["score_breakdown"]:
        print(f"SCORE +{d['weight']:.2f} {(d['name'] or d['node_id'])[:50]} (deg {d['degree_core']})")
    print("HUBS:", [h.get("name") or h.get("node_id") for h in res["excluded_hubs"]] or "none")
    for t in res["trace"]:
        print(f"TRACE {t['step']}: {t['tool']} {t['args']} -> {t['result_summary']}")
    print("GROUNDING:", res["grounding"], "| LLMCALLS:", res["llm_calls"], "| PROVIDER:", res["provider"])


if __name__ == "__main__":
    main()
