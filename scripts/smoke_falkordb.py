"""Smoke test: FalkorDB reachable, create/query/delete tiny graph.

Uses only FALKORDB_HOST / FALKORDB_PORT / GRAPH_NAME from env
(with safe defaults). Test graph is separate (`<graph>_smoke`)
so the real graph is never touched.
"""
import os

from dotenv import load_dotenv

load_dotenv()  # optional local .env, defaults below work without it

HOST = os.getenv("FALKORDB_HOST", "localhost")
PORT = int(os.getenv("FALKORDB_PORT", "6379"))
GRAPH = os.getenv("GRAPH_NAME", "offshore")
SMOKE_GRAPH = f"{GRAPH}_smoke"


def main() -> None:
    from falkordb import FalkorDB

    db = FalkorDB(host=HOST, port=PORT)
    g = db.select_graph(SMOKE_GRAPH)
    # clean any leftover from a previous interrupted run
    try:
        g.delete()
        g = db.select_graph(SMOKE_GRAPH)
    except Exception:
        pass

    g.query("CREATE (:SmokeTest {name: 'alice'})-[:CONNECTED_TO]->(:SmokeTest {name: 'bob'})")
    res = g.query(
        "MATCH (a:SmokeTest {name: 'alice'})-[r:CONNECTED_TO]->(b:SmokeTest) RETURN a.name, b.name LIMIT 5"
    )
    rows = [(r[0], r[1]) for r in res.result_set]
    assert ("alice", "bob") in rows, f"unexpected rows: {rows}"
    g.delete()
    print(f"SMOKE OK host={HOST} port={PORT} graph={SMOKE_GRAPH} rows={rows}")


if __name__ == "__main__":
    main()
