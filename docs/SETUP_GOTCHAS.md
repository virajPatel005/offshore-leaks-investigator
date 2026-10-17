# SETUP GOTCHAS — FalkorDB + union graph (`icij`)

Prerequisites-list companion (link this from the README prerequisites; README itself not written yet).

1) Volume mounts at BOTH paths — why.
   The falkordb image persists data in `/var/lib/falkordb/data` (it symlinks
   `/data/data` there). With only `/data` mounted, a container recreate silently
   loses every graph. `docker-compose.yml` therefore mounts `falkordb-data`
   at both `/data` and `/var/lib/falkordb/data`. Verify after any recreate:
   `curl -s http://127.0.0.1:8000/health`  → must show nodes > 0.

2) `--drop` wipes the full-text name indexes.
   After ANY `scripts/load_graph.py --drop` reload, run `ensure_search_indexes()`
   (backend/graph/search_entity.py) for that graph, or name search returns 0 hits:
   `PYTHONPATH=. .venv/bin/python runs/ensure_idx.py` and, for the union,
   `GRAPH_NAME=icij PYTHONPATH=. .venv/bin/python runs/ensure_idx.py`

3) LOAD CSV reads only from the import root.
   `file://../x`, absolute paths and mounts nested under a `:ro` parent all fail.
   The import root is `DATA_DIR/import_root` with hardlinks of `prepared/*` at
   the root and `prepared_icij/*` under `icij/`. After regenerating a prepared
   folder, refresh the hardlinks:
   `cp -l /home/viraj/data/icij/prepared/* /home/viraj/data/icij/import_root/`
   `cp -l /home/viraj/data/icij/prepared_icij/* /home/viraj/data/icij/import_root/icij/`

4) Query TIMEOUT is 1000 ms by default (image `FALKORDB_ARGS`).
   Raise before a bulk load (resets on every recreate):
   `docker exec offshore-investigator-falkordb-1 redis-cli GRAPH.CONFIG SET TIMEOUT 600000`
   Loads: offshore `graph=offshore` defaults (278,693 / 562,700);
   union `GRAPH_NAME=icij .venv/bin/python scripts/load_graph.py --drop --prepared icij --expect-nodes 838293 --expect-edges 1286362`

5) /health before a demo.
   `docker compose ps` and `curl -s http://127.0.0.1:8000/health` (expect `nodes` ≥ 278693).
   Server start (it must survive the shell): `tmux new-session -d -s uvicorn '.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 >> runs/uvicorn.log 2>&1'`

6) Never recreate the container without re-checking the graphs.
   `docker compose up -d` recreates on config change; then ALWAYS re-run
   `/health`, and if nodes=0 reload from the prepared folders (items 3–4 above)
   and re-run `ensure_search_indexes()` (item 2). The default graph stays `offshore`.
