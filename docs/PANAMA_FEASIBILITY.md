# PANAMA PAPERS FEASIBILITY (read-only check, 2026-10-17)

Scope: can a Panama Papers + Offshore Leaks union graph ship next to the existing
`offshore` graph without touching any current behaviour? Nothing was loaded, prepared
or edited; no LLM calls. Method: stdlib-only scripts in /tmp reading the public CSVs
in DATA_DIR (single pass, 14 s), scaling from the measured Offshore Leaks numbers
(278,693 nodes / 562,700 core edges / 97 MB prepared / 537 MB FalkorDB / 21 s prepare /
14 s import), plus a code audit (grep + file:line).

## A. Data (measured)

### A1. Node rows and slices
| slice | Entity | Officer | Intermediary | Address | other | rows | unique nodes |
|---|---|---|---|---|---|---|---|
| Offshore Leaks | 105,516 | 107,190 | 9,526 | 57,600 | 0 | 279,832 | 278,693 |
| Panama Papers | 213,634 | 238,402 | 14,110 | 93,454 | 0 | 559,600 | 559,600 |

Union unique nodes: **838,293**. The 1,139-row difference for Offshore is exactly the
known D4 dual-file set (officer+intermediary files, one node each). **No node_id is
shared between the two slices** (279,832 + 559,600 − 838,293 = 1,139).

### A2. Edges by endpoint membership
- both ends in Panama: **721,822**
- both ends in Offshore: **562,700** (matches the loaded graph)
- both ends in the union: **1,286,362** (core internal; plus 52,105 soft, see A5)
- crossing Offshore ↔ Panama: **1,840**, by rel_type: `same_as` 1,234 + `similar` 606.
  **Every crossing edge is a soft type — there are zero core edges across slices.**

### A3. D4 collision check (Panama)
Colliding IDs (present in both nodes-officers.csv and nodes-intermediaries.csv with
sourceID = "Panama Papers"): **0**. Nothing to normalize/compare; no differing examples.

### A4. degree_core percentiles, union graph (undirected distinct neighbors, core edges)
| node type | n | p50 | p90 | p99 | max |
|---|---|---|---|---|---|
| Address | 151,054 | 1 | 2 | 8 | 37,338 |
| Entity | 319,150 | 2 | 5 | 11 | 1,007 |
| Intermediary | 23,636 | 3 | 14 | 211 | 36,254 |
| Officer | 344,453 | 2 | 2 | 7 | 4,240 |

(Offshore's 1,139 merged nodes fall into the Intermediary bucket here because the
script folds categories per file; Panama has no merged IDs.)
Top hubs (union): unnamed Address 37,338; Portcullis TrustNet (BVI) Limited 36,254;
**ORION HOUSE SERVICES (HK) LIMITED 7,016 (Panama)**; Unitrust Corporate Services 5,700;
unnamed Address 5,699.
Nodes with degree > hub_threshold (1,000): **Offshore 39, Panama 23**.

### A5. Soft edges, union-internal
`similar` 46,761 + `same_as` 4,106 + `underlying` 1,238 = **52,105**.

## B. Resources (estimates, scaled from measured Offshore numbers)

### B6. Disk and memory
- WSL free space: **927 GB** (`df /home`). Prepared-union estimate ≈ 97 MB × (2.18 M
  rows / 0.85 M rows) ≈ **250 MB** (range 230–280 MB) — non-issue.
- Docker total memory: **7.608 GiB**. FalkorDB union estimate ≈ 537 MB × 2.57 ≈
  **1.4 GB** (range 1.2–1.7 GB). Fits comfortably; the union graph could even coexist
  with `offshore` (~1.9 GB combined) in the same container.

### B7. Prepare and import time
- prepare: 21 s measured; the script already reads all six CSVs (filters by sourceID),
  so read cost is constant — union write volume is 2.6× → estimate **~35 s**.
- import: 14 s measured for 562,700 edges + 278,693 nodes → union ratio 2.4× (edge
  dominant) → estimate **~35 s**. Total build **under 1.5 min**.

## C. Code audit (file:line, exact issue)

### C8. Hardcoded slice / dataset / graph names
- `scripts/prepare_slice.py:14` — `SLICE = "Offshore Leaks"` (the one real gate)
- `scripts/analyze_slice.py:14` — same constant (dev-only)
- `scripts/check_collisions.py:14` — same constant (dev-only)
- `backend/agent/agent.py:25` — SYSTEM prompt: "the public ICIJ Offshore Leaks graph"
- `backend/agent/agent.py:36` — LIMITATIONS: "this public ICIJ Offshore Leaks data"
- `backend/mcp_server/server.py:25` — LIMITATIONS same wording
- `backend/mcp_server/server.py:29` — server name "offshore-investigator"
- `backend/mcp_server/server.py:30` — instructions "the public ICIJ Offshore Leaks graph"
- `backend/mcp_server/server.py:120` — resource URI `graph-schema://offshore`
- `backend/app/main.py:35` — FastAPI title "offshore-investigator" (cosmetic)
- `web/index.html` — 4 cosmetic "Offshore" strings (banner/labels)

### C9. GRAPH_NAME and the cache key
The tools, MCP server and API already read `GRAPH_NAME` (default "offshore"):
`backend/graph/neighbors.py:16`, `search_entity.py:13`, `strongest_connection.py:16`,
`shared_neighbors.py:15`, `scripts/load_graph.py:16`, `smoke_falkordb.py:15`,
`backend/app/main.py:152`. `.env.example:8` already carries `GRAPH_NAME=offshore`.
**Gap: `backend/app/main.py:63 cache_key()` includes only question + pins — NOT the
graph name.** Switching GRAPH_NAME would serve cached Offshore answers for the union
graph. Change: prefix the key with `GRAPH_NAME` (one line; existing entries stay valid
for the default graph).

### C10. What works unchanged, what needs a change
- `hub_threshold=1000` predicates: unchanged (23 extra Panama hubs; same query logic).
- Fulltext indexes: built per graph at MCP/search startup — works; index time scales
  with rows (seconds, fine).
- `degree_core`: comes from the prepared files, so the **union build must recompute it
  over union-internal core edges** (loader needs no change).
- No change needed: tools, MCP tool schemas, UI graph rendering, grounding checks.

### C11. Proposed minimal change list (10 items)
1. `prepare_slice.py`: `--slices "Offshore Leaks,Panama Papers"` (or `--union`) + `--out`
   directory; degrees recomputed over the union core edges.
2. `analyze_slice.py` / `check_collisions.py`: same slice parameter (dev-only, can defer).
3. `load_graph.py`: `--prepared DIR` (or `PREPARED_DIR` env) so the union loads into the
   graph named by `GRAPH_NAME` — `offshore` stays untouched.
4. `main.py:63`: include `GRAPH_NAME` in `cache_key()`.
5. `agent.py`: dataset-agnostic SYSTEM + LIMITATIONS wording ("public ICIJ leak data").
6. `mcp_server/server.py`: instructions/resource URI graph-aware.
7. `web/index.html`: banner/labels mention both datasets (4 spots).
8. Generate the union demo cache once (5 chip questions; one fresh run each).
9. Re-run `scripts/check_ask.py` + the ★ TEST_QUESTIONS items against the union graph.
10. Docs: DECISIONS entry for the union graph, README/QUERIES note (both datasets).

## D. Risks and decision

### D12. What could change
- ★ demo pairs: **nothing** — verified no crossing edge touches any demo node
  (checked 123345, 170362, 172841, 172843, 108052, 123363, 108040, 298260, 51221,
  133819, 108197) and all crossing edges are soft, which are excluded from
  `degree_core`; hub classification and scores of Offshore nodes are therefore
  unchanged, and the deterministic tools return identical paths/scores.
- Key demo names exist only in Offshore (checked: MIRALEY 1, GALAXY 1, TO.CE.CO 1,
  Braggle 1, ASIAN DRAGON 1, Tsai Eng-Meng 1, Blue Bottle 1; Gary Pepper 2 and
  Portcullis variants 5–7 are all Offshore) → candidate lists do not grow.
- General pairs (non-★) could gain shorter soft-chain routes through Panama, extra
  shared neighbors, or extra name-search candidates. Cached answers must be per-graph
  (C9 fix) or a union question could silently serve an Offshore answer.

### D13. Estimate and rollback
- Hours: prepare/load/verify 1 h; code touchpoints (items 1–7) 1 h; union cache +
  check_ask + ★ re-grade 1–1.5 h; docs 0.5 h → **3.5–4 h total**.
- Rollback: nothing existing is modified — `offshore` graph, prepared folder and cache
  stay as-is; `GRAPH_NAME=offshore` restores the status quo; the union graph can be
  dropped with `Graph.delete()`.
- If it exceeds 90 minutes: cut in this order — (a) no union demo cache / cross-leak
  answer (keep union as a backstage graph + docs), (b) defer web copy (item 7),
  (c) defer the dev scripts (item 2).

### D14. Recommendation: **GO (scoped)**
Reasons: resources fit with huge margin (1.4 GB of 7.6 GiB, 250 MB disk, <1.5 min
build); zero core-edge cross-talk means the current demo behaviour is provably
untouched; 721,822 new Panama edges + 1,840 cross-slice soft links and 52,105 soft
edges add a genuine "follow the leaks / possible match" story for Track 1; the change
surface is ~7 small edits. Guardrails: keep `offshore` as the default graph and demo
fallback; land the union behind the GRAPH_NAME switch; hard stop at the 90-minute
checkpoint — if the union cache and ★ re-grade are not green by then, demo on
`offshore` and present the union as a backstage capability.

Not measured (time box): per-node duplicate-name counts across the full union beyond
the demo names, and index build wall-time on the union (both expected trivial).
