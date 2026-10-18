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
| 1 | `ui-clean-pair.png` | Ask: *What is the strongest recorded connection between GALAXY ASIA LIMITED. and TO.CE.CO LIMITED.?* | **8000 / offshore**: the flagship card: graph, score 9.35 (offshore), path chips |
| 2 | `ui-hub-blocked.png` | Ask: *What is the strongest recorded connection between MAGN DEVELOPMENT LIMITED and MASS FAITH GROUP LTD.?* | **8001 / icij** — "Excluded hubs" block naming ORION HOUSE SERVICES (HK) LIMITED, degree 7,016 |
| 3 | `ui-ambiguous.png` | Ask: *Find Gary Pepper. Then: what is the strongest recorded connection between Gary Pepper and Giltbridge Trading Limited?* | **8000 / offshore** — the candidate buttons with labels/countries/degrees |
| 4 | `ui-trace.png` | Any answered card → the "How I got here" panel expanded | **8000 / offshore** — tool steps with parameters and result summaries |
| 5 | `ui-expand.png` | On the flagship card: click a node, then "Expand neighbours"; click an edge | **8000 / offshore** — node/edge side cards, expansion edges drawn |
| 6 | `ui-panama-pair.png` | Ask: *Are "PEARL OCEAN HOLDING LIMITED" on the Panama Papers and on Offshore Leaks the same company?* | **8001 / icij** — the dashed `same_as` edge + "possible match" chip |
| 7 | `ui-soft-edge.png` | Ask: *What is the strongest recorded connection between Eton Consultants Group Ltd and Eton Consultants Group Limited?* | **8000 / offshore** — the agent asks twice; pick the two Intermediary records (HKG): Eton Consultants Group Ltd 290583, then Eton Consultants Group Limited 290763. Result: length 1, one dashed `similar` edge, "possible match", score "not applicable" |
| 8 | `mcp-external-client.png` | The verified external MCP client (see docs/MCP.md): run the documented `opencode run` command from a plain Windows terminal | no server screenshot (terminal) — tool calls + the correct answer (cosmetic PowerShell stderr noise is fine to include) |
| 9 | `ui-clean-pair2.png` | Second view of the clean-pair card (same flagship question) | **8000 / offshore** — full-width answer card: the path graph plus "Paths (1) · 3 hop(s) · score 10.45" (the union-graph reading) and the zoom toolbar |
| 10 | `ui-expand2.png` | Second expansion view: on the flagship card, "Expand neighbours" then full screen | **8000 / offshore** — a second `intermediary_of` neighbour (PricewaterhouseCoopers…) joins the graph; card header shows 3 hops, score 9.35 (offshore) |

Status 2026-10-18: all required files are present on disk under their exact names
(no double extensions; `ui-panama-pair.png` is the row-6 file); none missing.
Rows 1–8 are the README table embeds; rows 9–10 are the two detail views embedded
below the README table. The UI already labels everything — no annotations needed.
