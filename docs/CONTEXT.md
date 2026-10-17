# CONTEXT — handoff (living summary; PROGRESS.md stays the log)

## Current state
- Phase: 2 done; Phase 3a (UI clarity + clickable disambiguation) done; Phase 3b (Cytoscape graph + chat-thread UI + neighbour expansion) done.
- Last completed: Phase 3b — Cytoscape.js 3.34.4 vendored in `web/vendor/` (D14); graph view replaced the SVG (label colours, log-size by degree_core, hub double-border, dashed soft edges "possible match", step-by-step path replay, click a trace step to highlight its nodes, node side card); new read-only tool `get_neighbors` (graph layer + MCP + `GET /neighbors`) with in-query hub filter and a hub-centre guard/override; chat thread keeps every card with its own graph; single dark token palette (contrast measured).
- Next: re-grade the fixed items against TEST_QUESTIONS, then deployment/memory decision (Phase 3).

## How to run things
- venv: `.venv` (system Python 3.12: `/usr/bin/python3.12 -m venv .venv`); `.venv/bin/pip install -r requirements.txt` (falkordb, python-dotenv).
- Engine: `docker compose up -d` (FalkorDB, `127.0.0.1:6379` + `127.0.0.1:3000` only); verify with `docker compose ps`.
- Smoke: `.venv/bin/python scripts/smoke_falkordb.py` → `SMOKE OK ...` (throwaway `<graph>_smoke` graph, created + deleted).
- DATA_DIR=/home/viraj/data/icij (outside repo, ~600 MB CSVs). Never copy raw data into the repo; `*.csv` is gitignored.
- Scripts (analysis ones are read-only, stdlib only): `smoke_falkordb.py` (engine reachability); `analyze_slice.py` (slice counts, D4 collisions, core degrees); `check_collisions.py` (name/country comparison for colliding IDs); `prepare_slice.py` (writes the 12 load-ready files to DATA_DIR/prepared); `load_graph.py` (LOAD CSV import, `--drop` to reload, `--verify-only` to recheck).

## Key decisions (decision | evidence | status)
- WSL Ubuntu + local Docker baseline | Docker 29.8.2 reachable in WSL (D9) | confirmed
- Python 3.12 venv, not 3.14 | 3.12.13 available and stable | confirmed
- Localhost-only compose ports | `127.0.0.1:6379/3000` in compose ps | confirmed
- Offshore Leaks slice first | 278,693 unique nodes; 562,700 internal edges (D5) | confirmed
- D4 CONFIRMED (a) one node per ID, both labels | 1,139 colliding IDs (0.4%); 53,011 touched edges = 9.4%; incl. #2 hub Portcullis TrustNet (BVI) Ltd degree 36,254; 1139/1139 identical names + country_codes; mismatch 0/0 | CONFIRMED 2026-10-15; officer_name/intermediary_name only when differ + name_mismatch flag; Offshore Leaks only, re-run per slice; label counts overlap
- Degree = undirected distinct neighbors, core edges only | address p50=1/p99=6/max=37338; entity 4/14/449; intermediary 3/150/36254; officer 2/11/36254 | method confirmed, numbers recorded
- Slice files in DATA_DIR/prepared (6 nodes incl. merged set, 6 edges by rel_type) | counts match source analysis exactly; degree_core/all stored; role_category ownership=112397 management=119467 admin_legal=16322 financial=207 unknown=314307; dates raw strings | confirmed
- Loader: LOAD CSV used (not bulk-loader: no new dep, dual-label control, explainable queries) | 4 node_id indexes, CREATE fast path, 8-seek OPTIONAL MATCH endpoint resolution, full load ~14s | confirmed, Q1-Q5 registered
- Tool strongest_connection(s, t, hub, hops): exact-depth chains with per-intermediate hub predicates + iterative deepening; score = mean D3 rarity over intermediates; unbounded algo.SPpaths (Dijkstra) as unfiltered reference — bounded SPpaths uses DFS enumeration and timed out 60s, so it is never used with maxLen | confirmed, Q6 registered
- Tools search_entity (fulltext name index per label, exact-first, size-capped) + shared_neighbors (hub filter inside pattern, hubs listed, grouped by edge-type pair) | confirmed, Q7/Q8 registered
- MCP server stdio, SDK v2 pinned (mcp==2.3.0; v1 API renamed); name indexes at startup so calls stay read-only; 20s budget, truncation flags, limitations note | stdio check green; empty-folder external check NOT run | confirmed
- Agent ask.py (LangGraph decide-act, MCP stdio tools, groq): grounding checks ids/names/quotes against tool results (degrees + question echo + link terms exempt); MAX_LLM_CALLS_PER_RUN=8; runs/run-*.json per run | Q1/Q2/Q3 green | confirmed
- API+UI: POST /ask, GET /ask/stream (SSE steps+final), GET /health, runs/cache.json with cached flag; 300s timeout, 20/min rate, 100/day LLM cap (env); plain HTML/JS + hand SVG (zero-dep, offline-proof) | UI path verified | confirmed
- Ask API envelope: every response echoes rid + question; UI discards non-latest rids and aborts superseded fetches/streams; live always uses fresh=1 (bypass, still writes cache); cached badge only when echo matches box; scripts/check_ask.py asserts it.
- Agent output carries top-level score (mean D3 rarity over intermediates; null = no path); grounding also covers degrees, question echo, link terms, country codes + name/code table, with name-token exemption.
- Clickable disambiguation (D13): a search name with >1 exact match becomes a structured `candidates` row set (for_name, node_id, name, labels, country_codes, degree_core, sourceID); the API takes `pins` {name: node_id}, the agent feeds a pinned id straight to the path tools and hard-skips re-searching that name; unpinned cache key stays the plain question text (old cache valid), pinned runs get their own key. Grounding collects ids/names/degrees from `path.nodes` too (path endpoints are tool output).
- Graph view (D14): Cytoscape.js 3.34.4 vendored at `web/vendor/cytoscape.min.js` (MIT, no CDN, offline); the UI is a chat thread where each question+answer is a card with its own Cytoscape instance (older cards keep their graphs); interactions are client-side, only `GET /neighbors` hits the backend. `get_neighbors(node_id, hub_threshold=1000, limit=25, allow_hub=False)` is the only new tool, read-only and registered as Q9; the hub predicate is on the neighbour, and a hub centre is not expanded unless `allow_hub`. Palette is one dark cool-slate token set shared by graph/cards/banner.

## Data quirks (running list)
- 519k relationship rows have empty sourceID → slice by NODE sourceID, ignore relationship sourceID.
- ~700 free-text role variants; some mojibake; dates DD-MMM-YYYY; many empty fields.
- 7,183 officer_of edges start from intermediary-only IDs globally, but 0/0 inside the Offshore Leaks slice.
- nodes-others.csv has no Offshore Leaks rows (prepared nodes_other.csv is header-only, 0 rows).
- role_category unknown dominates (314k/563k) because registered_address + intermediary_of links carry no role text — expected, raw link preserved for recompute.

## Gotchas and fixes
- falkordb 1.8.0: delete a test graph via `Graph.delete()` (`db.select_graph(name).delete()`); the client has no `delete_graph`.
- `git commit -m "..."` message truncates through wsl quoting → write message to a file, `commit -F <file>`, then remove the file.
- FalkorDB shortestPath() is directed-only and MATCH-scoped (WITH/RETURN form); undirected var-length MATCH with WHERE all() filters after hub expansion (60s timeout at 36k hub) — prune with per-hop predicates instead. Bounded algo.SPpaths also uses DFS enumeration (timed out 60s); unbounded takes the Dijkstra fast path — never pass maxLen to the reference call.
- MCP v2 Tool uses input_schema (snake_case); empty-string short-circuit missing-property filters fail silently — branch query shapes in Python; "already indexed" (not "already exists") is the idempotent fulltext message.
- RediSearch: quoted phrases with punctuation raise syntax errors (never quote user input); commas/hyphens tokenize loosely (one query hit 50 noise rows) — union raw + punctuation-stripped variants, exact-first.
- pkill -f matches your own shell cmdline (suicide, empty output) — use a bracket pattern; stale uvicorn on :8000 shows "address already in use" in runs/uvicorn.log. The bracket trick still fails if the SAME command line also starts uvicorn (the literal "uvicorn backend.app.main" in the start half matches): run the kill and the start as SEPARATE commands, then confirm with /health.
- 61s agent runs = Groq 429 OTPM-1000 retries on qwen3-27b on_demand (code itself ~0.5s: startup 0.5s, search 0.0s, strongest 0.2s, trivial LLM 0.7s) — provider/model cause, not worked around; cache sidesteps repeats.
- Address records carry street text in the address field with empty names — name search cannot resolve hub addresses; test set documents this instead of routing around it.
- Docker Desktop can be fully down (no daemon): relaunch the per-user exe, then `docker compose up -d`; background servers need setsid to survive the shell (nohup alone died).
- WSL `docker` CLI depends on Desktop's per-distro integration: if `wsl docker` fails but Windows `docker` works, re-enable Ubuntu integration (or restart Desktop); containers created while it was off can carry empty bind mounts → `--force-recreate` after fixing.
- Keep outputs small: summaries only, never dump raw CSV rows (max 3 lines per file).
- Multi-line `python - <<'EOF'` heredocs get mangled going PowerShell -> wsl (parentheses/quotes break); write the snippet to a file under the gitignored `runs/` and run it, then delete it.
- Cytoscape style selectors need data-mapped colours to exist on every element (node and edge both carry `bg`/`edgeColor`/`softColor` etc.); breadthfirst needs `roots` set before `buildGraph` or it has no anchor.

## Open questions
- Frontend choice (Phase 2); Track 2 memory in/out (Phase 3).
