# PROGRESS

Public log. Design decisions live in docs/DECISIONS.md; queries in docs/QUERIES.md.

## Status
| Phase | Gate | Status |
|---|---|---|
| 0 Prep | Docker + FalkorDB + .env ready | done 2026-10-15 |
| 1 Import | Question 1 answered from a script | done 2026-10-16 |
| 2 Agent | Question 1 works from the UI | done 2026-10-17 |
| 3 Depth | Questions 2 and 3, examples, deploy attempt | done 2026-10-18 (deploy not pursued — local-first demo) |
| 4 Ship | README, video, submitted | in progress |

## Milestones
- 2026-10-15: environment + smoke test green (Docker in WSL, Python 3.12 venv, localhost-only ports).
- 2026-10-15: slice analysis — 278,693 nodes / 562,700 internal edges; D4 CONFIRMED (1,139 colliding IDs stored as one dual-label node; 1,139/1,139 identical names + country codes).
- 2026-10-16: LOAD CSV import of `offshore` (4 indexes, ~14 s; CHECK counts OK).
- 2026-10-16: graph tools — `strongest_connection` (per-hop hub predicates, mean rarity score), `search_entity`, `shared_neighbors`; hub filter lives inside the traversal (Q6–Q9 in docs/QUERIES.md).
- 2026-10-16: read-only MCP server (stdio, 20 s budget), LangGraph agent over MCP, FastAPI + web UI; flagship path T2Q1 = 3 hops, score 9.35 (offshore).
- 2026-10-17: UI graph view (Cytoscape 3.34.4 vendored), clickable disambiguation (candidate picks + pins), zoom controls, light/dark themes.
- 2026-10-17: union graph `icij` (Offshore Leaks + Panama Papers, 838,293 / 1,286,362) — same schema, same paths score ≈ +1.10 higher with N; soft-edge flags on every result.
- 2026-10-18: multi-path listing (up to 8 ranked paths + excluded hub reference), help sidebar + curated question sets + neighbour star.
- 2026-10-18: demo cache rebuilt; PART 2 cross-dataset questions verified (MATCHBOX, GLOBAL CAR KING, GALAXY NIGHT ↔ ELFERS).
- 2026-10-18: PEARL OCEAN cross-dataset pair fixed (auto-pair + same-id guards + possible-match wording) and verified on both graphs.
- 2026-10-18: docs pass — every quoted score names its graph + a "Score by graph" table in the README.
- 2026-10-18: publication cleanup (personal files removed, paths genericized, screenshots embedded).

## Bugs found and fixed
- Wrong-graph answers from the agent on `icij`: the MCP subprocess never received `GRAPH_NAME` (SDK safe-env allowlist) — now forwarded explicitly; verified on both graphs.
- LLM hang on rate limits: bounded retries + per-call timeout; the API fails fast with a clear 429/504 message.
- Direct links displayed a bogus score: now `not applicable: direct link, no intermediate nodes` everywhere.
- PEARL OCEAN same-node comparison: a pin matched by name only, so the agent compared a node with itself — fixed with auto-pairing, same-id guards and deterministic possible-match wording.
- Eton soft pair star filter: a shared-neighbours payload could render as a star with a missing centre — the filter now requires a node id and rejects same-id error payloads; soft edges read "possible match" in every graph type.

## Known limits
- Name search cannot resolve address hubs (addresses have no name field); punctuation tokenizes loosely (raw + stripped variants unioned).
- Depth 6 is not safe on hub-blocked pairs (15 s candidate timeout); depth 5 is (<1 s measured).
- No triple-share (officer + address + intermediary) demo pair found yet; no deep Panama-only path pair yet.
- Scores are relative to the loaded graph (N = live node count) — compare within one graph, not across.
- Soft edges are possible matches only — no entity resolution beyond ICIJ's own records.
