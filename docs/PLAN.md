# PLAN

## Goal
Agent that investigates ICIJ Offshore Leaks by following connections in FalkorDB and explains the path behind every answer. Track 1. Track 2 only if memory is real and demoable.

## Where we are (update as you go)
Oct 15 evening IST. Done: venv, requirements (falkordb, python-dotenv), docker-compose.yml, smoke_falkordb.py, D11 placeholder folders. Docker Desktop installed. Next: engine running + smoke test green.

## Scope: 3 core demo questions
1. Strongest connection: most informative recorded path between A and B, with the relevance score broken down.
2. Shared officer and non-hub address: which companies share an officer AND a non-hub registered address?
3. Hub-filtered clusters: which groups remain after hubs are excluded or down-weighted, and which exclusions changed the result?
Smoke test only: "who is connected to X within 3 hops?"
Stretch (only if ahead): ownership chain upward from a company; possible identity matches using the existing same_as / probably_same_officer_as edges with their evidence.

## Phases (all times IST). Do not start a phase until the previous gate passes.
- Phase 1, Oct 15 evening to Oct 16 midday:
  - 1a: engine up, smoke test green, change compose ports to 127.0.0.1 (30 min max total).
  - 1b: prepare slice files WITHOUT the database (ID collision analysis D4, load-ready node and edge files, degrees), verify counts.
  - 1c: load into FalkorDB (indexes first), verify counts and directions, record import time and memory.
  - 1d: hub-pruned traversal test and weighted-path support check (30 min max); 2 core graph tools.
  - GATE: demo question 1 answered from a script.
- Phase 2, Oct 16 afternoon to Oct 17 midday: MCP server with 2-3 fixed tools; LangGraph agent; minimal UI showing the path and score. GATE: question 1 works from the UI, end to end.
- Phase 3, Oct 17: questions 2 and 3; light role normalization; start screen with clickable examples and name search; cached answers; deploy attempt; decide on memory (Track 2); multi-client MCP check from opencode (D12, 30 min max).
- Phase 4, Oct 18: FEATURE FREEZE at 12:00. README (setup, graph model, Cypher list, known data quirks), demo video (include the 30-45 s multi-client MCP segment), AI disclosure, name the track(s). Submit by 16:00. Deadline is 23:59.

## Submission checklist
- [ ] Public repo, no secrets or raw data
- [ ] README: setup steps + graph data model
- [ ] Cypher queries / algorithms the product depends on (from QUERIES.md)
- [ ] Demo video
- [ ] Live deployment OR full local setup instructions
- [ ] Track(s) named at submission
- [ ] AI usage disclosed (AI_USAGE.md)
- [ ] ICIJ credited; dataset disclaimer shown in the app
- [ ] Git enabled, repo pushed, .env confirmed not committed
- [ ] Before submitting: set the daily LLM cap back to 100 in .env (public demo protection), restart the server, and confirm the README mentions the cap.

## If behind, cut in this order
Claude Code client demo > Track 2 memory > ownership chain > identity matching > cluster view > live deploy (fall back to local setup + video). Never cut: the working agent, the path explanation, hub-aware traversal.

## Ideas (parking lot, not for code yet)
-