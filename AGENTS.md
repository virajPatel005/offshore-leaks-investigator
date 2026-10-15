# AGENTS.md — rules for the coding agent
Read this fully at the start of every session. Details live in docs/ — open them only when needed.

## 1. Project
- Hackathon: WeMakeDevs x FalkorDB "Graph Hacks". Window: 2026-10-15 00:01 IST to 2026-10-18 23:59 IST.
- Track: 1 (Agents That Act on Connected Data). Track 2 only if per-investigator memory ends up real and demoable.
- Product: an agent that investigates the public ICIJ Offshore Leaks data by following connections in a FalkorDB graph, ranks connections with an explainable rarity-weighted relevance score, and shows the path behind every answer.
- Owner: Viraj (student). He codes with you and must be able to explain every query and design choice to judges.
- Default stack (ask before changing): Python, FalkorDB (Docker), a Python MCP server exposing fixed graph tools, a LangGraph agent, FastAPI backend, lightweight web UI.
- Plan: docs/PLAN.md | Decisions: docs/DECISIONS.md | Progress log: docs/PROGRESS.md | Queries: docs/QUERIES.md | AI disclosure: docs/AI_USAGE.md | Handoff: docs/CONTEXT.md

## 2. Hard rules (breaking these can disqualify the project)
1. DATE GATE. Run `date`. Before 2026-10-15 00:01 IST do read-only analysis and notes only: no import script, no agent, no app code, no git init.
2. FalkorDB is the primary datastore and the graph must do real work. Test: if removing FalkorDB leaves a feature working, that feature is wrong. No other database as source of truth. Small in-memory helpers on query results are fine.
3. Data: only the public ICIJ Offshore Leaks CSVs at DATA_DIR (outside the repo). Never copy raw data into the repo. Never add private or personal data.
4. Secrets: never open or read .env (use .env.example for variable names). Never print, log, or commit a key. Before every commit run `git status` and confirm no .env or data files are staged. If a key may have leaked, stop and tell Viraj.
5. Disclosure: after each major task append one line to docs/AI_USAGE.md.
6. Explain: after each task give Viraj a 3-5 line "why": what you did, why this design, one alternative, how to verify. No dead code, no unexplained generated blobs.
7. Neutral language: the data names real people, and appearing in it implies no wrongdoing. Never say "suspicious" or "criminal". Say "connection relevance" and "possible match".

## 3. How to work
- One task at a time from docs/PLAN.md. Say which task you are starting.
- Small steps, small files. Comments only for non-obvious *why*.
- Verify before saying done: run it and show a result summary of at most 15 lines. "Should work" is not done.
- Ask first before: adding a dependency, changing the graph model, overriding docs/DECISIONS.md, anything that costs money, deleting files.
- No scope creep. New ideas go to the Ideas list in docs/PLAN.md, not into code.
- Commit after each working milestone with a clear message. Never push unless asked.
- After every task, update docs/CONTEXT.md (current state + any new decision, quirk or gotcha) so a newcomer can continue without chat history.
- End each task with a DONE report: changed / how verified / why / next.

## 4. Time boxes and the stuck rule
You cannot judge elapsed time well, so count attempts. An attempt is a DIFFERENT change tried toward the goal; retrying the same thing does not count. Run `date` at task start and after your 2nd failure.

| Task | Stop at |
|---|---|
| setup / config / small fix | 10 min or 2 failed attempts |
| bug | 20 min or 3 failed attempts, each on a different hypothesis |
| one new tool or feature | 45 min |
| import or performance tuning | 30 min per approach |

When a limit is hit: STOP. Do not try "one more thing". Append a STUCK report to docs/PROGRESS.md and post it in chat, then wait for Viraj's decision. The report contains: goal; every attempt and its result; exact error or evidence; top 2 hypotheses; 2-3 options with time cost (always include "cut scope" and "simpler workaround"); your recommendation.

Never do any of these to get unstuck: fake or mock data to pass a check, disable the hub filter or a validation, raise timeouts without limit, delete or weaken tests, quietly change requirements.

End-to-end first: do not polish a phase before the demo path of the current phase works.

## 5. Token and cost discipline
- Never cat, print, or read large files (the raw CSVs total ~600 MB). Use `head -n 5`, `wc -l`, or scripts that print summaries. Keep any command output under ~50 lines (pipe through head/tail).
- Do not re-read files you just wrote. Show diffs or summaries, not whole files.
- Product LLM calls during development use LLM_PROVIDER from .env (groq or openrouter). Never use the OpenAI key in tests, loops, or evals unless Viraj says "OpenAI OK" (final demo only).
- Hard-cap every loop that calls an LLM (MAX_LLM_CALLS_PER_RUN).
- Prefer deterministic code. The LLM only (a) picks a tool and (b) turns structured results into a plain-language explanation. Pathfinding, filtering and scoring are Cypher plus code.
- Cache LLM output for the demo examples.

## 6. Graph rules (reasoning in docs/DECISIONS.md)
- Core edges: officer_of, intermediary_of, registered_address. Soft edges (similar, same_name_as, same_as, same_id_as, same_company_as, probably_same_officer_as, ...) stay separate types, are opt-in, and are always labeled "possible match".
- Keep the raw link text, a normalized role category (unknown stays unknown), rel_type, dates, and sourceID on every edge.
- Store distinct-neighbor degree on nodes at import. The hub filter must be INSIDE the traversal (the query pattern), never only a Python post-filter. High degree does not mean fake; it means a link is less informative.
- Every query: parameterized, depth-bounded, LIMITed, with a timeout, and registered in docs/QUERIES.md.
- Every answer returns: the path, relationship types, source records, node degrees, relevance score, limitations, and any excluded hubs that changed the result.
- MCP tools are read-only, return size-capped results, and have names/descriptions written for another model to choose from. No write tools.
- Keep ingestion, graph core, tool/MCP layer and agent/UI as separate modules (D11). No dataset-specific logic in scoring or tools.
- Never invent edges. Never turn a possible match into a confirmed identity.
- Node-ID overlap (officers vs intermediaries): follow decision D4. Never pick a record by relationship type alone.

## 7. Done means
Runs end to end | explained to Viraj | queries registered | docs/PROGRESS.md and docs/AI_USAGE.md updated | no secrets staged | the demo path still works.