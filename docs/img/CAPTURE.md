# SCREENSHOT CAPTURE LIST (docs/img/)

The README references these files. Capture each in the UI, save as the exact
filename below, and prefer the dark theme + a maximised window (~1280×800 or
wider). The graph card, thread card and "How I got here" panel should all be
visible where possible.

**Servers and graphs** (check `GET /health` before capturing — the response
must name the right graph): port **8000** serves the default **`offshore`**
graph; port **8001** serves the union (**`icij`**, Offshore Leaks + Panama
Papers) and is started with
`GRAPH_NAME=icij .venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8001`
(`/health` should answer `"graph": "icij", "nodes": 838293`). Stop the 8001
server after capturing rows 2 and 6.

| # | File | Capture this | Port / graph and notes |
|---|---|---|---|
| 1 | `ui-clean-pair.png` | Ask: *What is the strongest recorded connection between GALAXY ASIA LIMITED. and TO.CE.CO LIMITED.?* | **8000 / offshore** — the flagship card: graph, score ≈ 9.35 (offshore), path chips |
| 2 | `ui-hub-blocked.png` | Ask: *What is the strongest recorded connection between MAGN DEVELOPMENT LIMITED and MASS FAITH GROUP LTD.?* | **8001 / icij** — "Excluded hubs" block naming ORION HOUSE SERVICES (HK) LIMITED, degree 7,016 |
| 3 | `ui-ambiguous.png` | Ask: *Find Gary Pepper. Then: what is the strongest recorded connection between Gary Pepper and Giltbridge Trading Limited?* | **8000 / offshore** — the candidate buttons with labels/countries/degrees |
| 4 | `ui-trace.png` | Any answered card → the "How I got here" panel expanded | **8000 / offshore** — tool steps with parameters and result summaries |
| 5 | `ui-expand.png` | On the flagship card: click a node, then "Expand neighbours"; click an edge | **8000 / offshore** — node/edge side cards, expansion edges drawn |
| 6 | `ui-panama-pair.png` | Ask: *Are "PEARL OCEAN HOLDING LIMITED" on the Panama Papers and on Offshore Leaks the same company?* | **8001 / icij** — the dashed `same_as` edge + "possible match" chip |
| 7 | `ui-soft-edge.png` | Ask: *Is "Eton Consultants Group Ltd" the same company as "Eton Consultants Group Limited"?* | **8000 / offshore** — the one dashed `similar` edge, possible-match wording in the answer |
| 8 | `mcp-external-client.png` | The verified external MCP client (see docs/MCP.md): run the documented `opencode run` command from a plain Windows terminal | no server screenshot (terminal) — tool calls + the correct answer (cosmetic PowerShell stderr noise is fine to include) |

All eight are embeds in the README "Screenshots" section (PNG, no annotations needed —
the UI already labels everything).
