# PROGRESS

Newest entries at the top. The agent appends here; Viraj reads it at the start of each work block.

## Status
| Phase | Gate | Status |
|---|---|---|
| 0 Prep | Docker + FalkorDB + .env ready | done 2026-10-15 20:00 IST |
| 1 Import | Question 1 answered from a script | |
| 2 Agent | Question 1 works from the UI | |
| 3 Depth | Questions 2 and 3, examples, deploy attempt | |
| 4 Ship | README, video, submitted | |

## Log
<!-- YYYY-MM-DD HH:MM IST | task | result | next -->
- 2026-10-16 21:11 IST | Phase 2c agent (no UI) | backend/llm/client.py (provider switch, 8-call budget) + backend/agent/agent.py (LangGraph decide-act over MCP stdio, grounding check, runs/ JSON) + ask.py; Q1 len3 score9.35 3calls/61s clean, Q2 hub story 4-6calls/61s clean, Q3 no-record 2calls/2s clean; no wrong tool choices | Phase 3 questions 2+3 + UI
- 2026-10-16 20:29 IST | Phase 2b MCP server (no agent/UI) | backend/mcp_server/server.py on SDK v2 (mcp==2.3.0): 3 tools + graph-schema resource, stdio, 20s budget, truncation flags, limitations note; stdio check: 3 tools listed, resource 421 chars, calls 1610/1787/1093 chars; docs/MCP.md with empty-folder config, external check NOT run | LangGraph agent
- 2026-10-16 20:17 IST | Phase 2a tools (no MCP/agent/UI) | hardened strongest_connection (unbounded SPpaths ref after bounded-DFS 60s timeout; all guarded with notes); search_entity (fulltext Entity/Officer/Intermediary, exact-first) + shared_neighbors (hub filter inside, hubs listed); try_tools.py 3.4s all green; Q7/Q8 registered | Phase 2b MCP server
- 2026-10-16 19:46 IST | Phase 1d traversal test + strongest_connection tool | undirected shortestPath unsupported + directed misses edges (NULL ~35ms); var-length hub filter times out 60s at 36k hub; SPpaths both/pathCount1 30-95ms exact shortest. Tool: backend/graph/strongest_connection.py (per-hop hub predicates, iterative deepening, mean D3 score, SPpaths hub-changed reference) + try_strongest.py green on 3 pairs; Q6 registered | Phase 2 MCP server
- 2026-10-16 19:10 IST | Phase 1c LOAD CSV import (graph offshore) | scripts/load_graph.py: 4 indexes, 5 node files + merged dual-label, 6 edge files; unique nodes 278,693 OK, edges 562,700 OK, dirs OK, Portcullis core degree 37,338 OK, ~14s, container ~537MB; Q1-Q5 in QUERIES.md | Phase 1d hub-pruned traversal + weighted-path check, then 2 graph tools
- 2026-10-15 20:49 IST | D4 CONFIRMED (a) + Phase 1b part 2 slice files (no DB) | D4 in DECISIONS.md; scripts/prepare_slice.py stdlib-only wrote 12 files to DATA_DIR/prepared (6 nodes + 6 edges, degree_core/all stored, role_category per D7, dates raw); nodes 278,693 CHECK OK, edges 562,700 CHECK OK, 305MB/21s | Viraj picks loader format, then Phase 1c import
- 2026-10-15 20:24 IST | D4 name-comparison check (read-only, no DB) | scripts/check_collisions.py stdlib-only, 5-line output: 1139/1139 identical normalized names, country_codes 1139/1139 match, 0 differing hub-sized IDs, 118MB/11s | Viraj confirms D4, then Phase 1b part 2 slice files
- 2026-10-15 20:12 IST | Phase 1b part 1 slice analysis (read-only, no DB) | scripts/analyze_slice.py stdlib-only, 14-line output: 278,693 unique slice nodes, 562,700 internal edges, 1,139 colliding IDs touching 53,011 edges, in-slice mismatch 0/0, peak 307MB/12s | Viraj confirms D4 option, then Phase 1b part 2 slice files
- 2026-10-15 20:00 IST | env check + hygiene + Phase 1a smoke green | WSL Ubuntu, Docker 29.8.2 reachable, .venv py3.12.13, compose ports 127.0.0.1 only, docs/ moved, DATA_DIR set, smoke OK; prior 17:35 STUCK resolved (Docker now in WSL) | Phase 1b slice files without DB
- 2026-10-15 17:35 IST | Phase 1 task 1 env setup (partial) | venv+requirements+compose+placeholders+smoke script written; Docker missing so engine start + smoke run blocked | Viraj installs Docker Desktop, then rerun compose up + smoke

## STUCK 2026-10-15 17:35 IST — FalkorDB engine start + smoke run
- Goal: `docker compose up -d` then smoke_falkordb.py create/query/delete tiny graph.
- Attempts (each with result):
  1. `docker --version`, `docker compose version`, `docker info` -> `docker` not recognized; no Docker Desktop service/exe found. Result: engine absent.
  2. Wrote smoke_falkordb.py (env-only config, no secrets) and ran it with .venv (falkordb 1.8.0 installed) -> ConnectionRefusedError WinError 10061; `docker compose up -d` fails same root cause. Result: blocked, no server.
- Exact error / evidence: `docker : The term 'docker' is not recognized...`; `ConnectionRefusedError: [WinError 10061]` from redis connection to localhost:6379.
- Top 2 hypotheses:
  1. Docker Desktop simply not installed on this machine (most likely).
  2. Installed but not on PATH / service not running (less likely; ProgramFiles path check negative).
- Options (include "cut scope" and "simpler workaround"), with time cost:
  - A. Viraj installs Docker Desktop for Windows + WSL2 backend, restarts, reruns two commands (~20-30 min incl. download).
  - B. Simpler workaround: run FalkorDB via FalkorDB Cloud free instance and point FALKORDB_HOST at it for smoke only (~10 min, needs network + account; local compose stays for later).
  - C. Cut scope: defer engine-dependent verification; continue with file-only tasks until Docker ready (0 min now, smoke debt carried).
- Recommendation: A (local Docker is the guaranteed baseline per D9); C meanwhile — nothing else attempted until Viraj decides.

## STUCK report template
- Goal:
- Attempts (each with result):
- Exact error / evidence:
- Top 2 hypotheses:
- Options (include "cut scope" and "simpler workaround"), with time cost:
- Recommendation:
