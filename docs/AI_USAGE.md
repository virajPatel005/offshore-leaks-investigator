# AI USAGE DISCLOSURE

Required by the hackathon. Be specific and honest: the "Reviewed by Viraj" column must describe what a human actually checked or changed.

Tools: opencode (coding agent), models used through it (record the model name per task). Claude used for planning and prompt writing.

| Date | Tool / model | Task | Reviewed by Viraj (what I checked, tested or changed) |
|---|---|---|---|
| 2026-10-15 | opencode / muse-spark | env check + hygiene, compose 127.0.0.1, venv py3.12, smoke green | Pending: verify compose ports + smoke output |
| 2026-10-15 | opencode / opencode/muse-spark-1.3-contributor-free | Phase 1b part 1 slice analysis script + D4 numbers (stdlib only, read-only) | Pending: check the 14-line output and D4 recommendation |
| 2026-10-15 | opencode / opencode/muse-spark-1.3-contributor-free | handoff docs/CONTEXT.md + AGENTS.md update rule + D4 name-comparison script (stdlib only, read-only) | Pending: confirm CONTEXT.md accuracy and the D4 merge recommendation |
| 2026-10-15 | opencode / opencode/muse-spark-1.3-contributor-free | D4 CONFIRMED in DECISIONS.md + slice-file builder prepare_slice.py + loader docs check (no DB writes) | Pending: verify prepared counts and pick loader format |
| 2026-10-16 | opencode / opencode/muse-spark-1.3-contributor-free | Phase 1c LOAD CSV import script + verification + Q1-Q5 registry (graph offshore, 278,693 nodes / 562,700 edges) | Pending: spot-check a Portcullis path in the browser UI |
| 2026-10-16 | opencode / opencode/muse-spark-1.3-contributor-free | Phase 1d traversal measurements + strongest_connection tool + try script + Q6 (no MCP/agent/UI) | Pending: review mean-score choice and per-hop hub pruning |
| 2026-10-16 | opencode / opencode/muse-spark-1.3-contributor-free | Phase 2a hardening + search_entity + shared_neighbors + try_tools + Q7/Q8 (no MCP/agent/UI) | Pending: try the demo pairs and confirm tool output shape |
| 2026-10-16 | opencode / opencode/muse-spark-1.3-contributor-free | Phase 2b MCP server + stdio client check + docs/MCP.md (no agent/UI, external check not run) | Pending: run the empty-folder opencode check (D12) |
| 2026-10-16 | opencode / opencode/muse-spark-1.3-contributor-free | Phase 2c agent (LangGraph+MCP stdio, groq provider) + ask.py, 3 name-based tests (no UI) | Pending: read one runs/*.json and confirm answer quality |
| 2026-10-17 | opencode / opencode/muse-spark-1.3-contributor-free | Phase 2d latency diagnosis (groq 429) + FastAPI/SSE + web UI, verified via UI path (no Q3/deploy/memory) | Pending: click through the UI and confirm readability on video |
| 2026-10-17 | opencode / opencode/muse-spark-1.3-contributor-free | docs/TEST_QUESTIONS.md 20-question graded set (Cypher probes only, no LLM calls) | Pending: run the first-3 questions and grade pass/fail |
| 2026-10-17 | opencode / opencode/muse-spark-1.3-contributor-free | Phase 2e six bugfixes, 4 groq runs (search-only, ambiguity, no-path wording, fresh bypass) | Pending: re-run TEST_QUESTIONS T1Q3/T2Q1/T3Q2 through the UI |
| 2026-10-17 | opencode / opencode/deepseek-v4.1-flash-free | Phase 3a clickable disambiguation (agent candidates + pins, API cache key, UI buttons/onboarding/legend) + path.nodes grounding fix; 4 groq runs + deterministic grounding test | Pending: click the Gary Pepper / Lee, Chung-Han ambiguity buttons in the UI and confirm the pinned answer + "Using:" line |
| 2026-10-17 | opencode / opencode/deepseek-v4.1-flash-free (skills: frontend-design, better-colors, web-design-guidelines) | Phase 3b Cytoscape graph view + chat-thread UI + `get_neighbors` tool/endpoint + dark token palette; dependency approved by Viraj (cytoscape 3.34.4, vendored, MIT). 0 LLM runs; verified via /neighbors latency, 3-question data independence, node --check, contrast measurement, guidelines review | Pending: click a node/expand neighbours in a browser and confirm the graph renders and each card keeps its own graph |