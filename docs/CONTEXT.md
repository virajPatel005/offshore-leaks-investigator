# CONTEXT — handoff (living summary; PROGRESS.md stays the log)

## Current state
- Phase: 1 (Import). 1a done (engine + smoke green). 1b part 1 done (read-only slice analysis).
- Last completed: D4 name-comparison check via scripts/check_collisions.py (5-line output, 11s, 118MB).
- Next: Viraj confirms D4; then Phase 1b part 2 (slice files).
- Blocked: nothing. D4 decision is PENDING — do NOT write it into DECISIONS.md yet.

## How to run things
- venv: `.venv` (system Python 3.12: `/usr/bin/python3.12 -m venv .venv`); `.venv/bin/pip install -r requirements.txt` (falkordb, python-dotenv).
- Engine: `docker compose up -d` (FalkorDB, `127.0.0.1:6379` + `127.0.0.1:3000` only); verify with `docker compose ps`.
- Smoke: `.venv/bin/python scripts/smoke_falkordb.py` → `SMOKE OK ...` (throwaway `<graph>_smoke` graph, created + deleted).
- DATA_DIR=/home/viraj/data/icij (outside repo, ~600 MB CSVs). Never copy raw data into the repo; `*.csv` is gitignored.
- Scripts (analysis ones are read-only, stdlib only): `smoke_falkordb.py` (engine reachability); `analyze_slice.py` (slice counts, D4 collisions, core degrees); `check_collisions.py` (name/country comparison for colliding IDs).

## Key decisions (decision | evidence | status)
- WSL Ubuntu + local Docker baseline | Docker 29.8.2 reachable in WSL (D9) | confirmed
- Python 3.12 venv, not 3.14 | 3.12.13 available and stable | confirmed
- Localhost-only compose ports | `127.0.0.1:6379/3000` in compose ps | confirmed
- Offshore Leaks slice first | 278,693 unique nodes; 562,700 internal edges (D5) | confirmed
- D4 lean (a) one node per ID, both labels | 1,139 colliding IDs (0.4%); 53,011 touched edges = 9.4% (43,304 officer_of + 8,450 intermediary_of + 1,193 registered_address + 64 soft); incl. Portcullis TrustNet (BVI) Ltd degree 36,254; in-slice mismatch 0/0; name check: 1139/1139 identical normalized names, 1139/1139 country_codes match, 0 differing | PENDING Viraj confirm
- Degree = undirected distinct neighbors, core edges only | address p50=1/p99=6/max=37338; entity 4/14/449; intermediary 3/150/36254; officer 2/11/36254 | method confirmed, numbers recorded

## Data quirks (running list)
- 519k relationship rows have empty sourceID → slice by NODE sourceID, ignore relationship sourceID.
- ~700 free-text role variants; some mojibake; dates DD-MMM-YYYY; many empty fields.
- 7,183 officer_of edges start from intermediary-only IDs globally, but 0/0 inside the Offshore Leaks slice.
- nodes-others.csv has no Offshore Leaks rows.

## Gotchas and fixes
- falkordb 1.8.0: delete a test graph via `Graph.delete()` (`db.select_graph(name).delete()`); the client has no `delete_graph`.
- `git commit -m "..."` message truncates through wsl quoting → write message to a file, `commit -F <file>`, then remove the file.
- Keep outputs small: summaries only, never dump raw CSV rows (max 3 lines per file).

## Open questions
- D4 final: (a) vs (b) — awaiting name check + Viraj.
- Frontend choice (Phase 2); Track 2 memory in/out (Phase 3).
