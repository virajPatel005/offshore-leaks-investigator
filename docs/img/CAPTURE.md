# SCREENSHOT CAPTURE LIST (docs/img/)

The README references these files. Capture each in the UI (`http://127.0.0.1:8000`,
default graph unless noted), save as the exact filename below, and prefer the
dark theme + a maximised window (~1280×800 or wider). The graph card, thread card
and "How I got here" panel should all be visible where possible.

| # | File | Capture this | Notes |
|---|---|---|---|
| 1 | `ui-clean-pair.png` | Ask: *What is the strongest recorded connection between GALAXY ASIA LIMITED. and TO.CE.CO LIMITED.?* | the flagship card: graph, score ≈ 9.35 (offshore), path chips |
| 2 | `ui-hub-blocked.png` | `GRAPH_NAME=icij`, ask: *What is the strongest recorded connection between MAGN DEVELOPMENT LIMITED and MASS FAITH GROUP LTD.?* | "Excluded hubs" block naming ORION HOUSE SERVICES (HK) LIMITED, degree 7,016 |
| 3 | `ui-ambiguous.png` | Ask: *Find Gary Pepper. Then: what is the strongest recorded connection between Gary Pepper and Giltbridge Trading Limited?* | the candidate buttons with labels/countries/degrees |
| 4 | `ui-trace.png` | Any answered card → the "How I got here" panel expanded | tool steps with parameters and result summaries |
| 5 | `ui-expand.png` | On the flagship card: click a node, then "Expand neighbours"; click an edge | node/edge side cards, expansion edges drawn |
| 6 | `ui-panama-pair.png` | `GRAPH_NAME=icij`, ask: *Are "PEARL OCEAN HOLDING LIMITED" on the Panama Papers and on Offshore Leaks the same company?* | the dashed `same_as` edge + "possible match" chip |
| 7 | `ui-soft-edge.png` | Ask: *Is "Eton Consultants Group Ltd" the same company as "Eton Consultants Group Limited"?* | the one dashed `similar` edge, possible-match wording in the answer |
| 8 | `mcp-external-client.png` | The verified external MCP client (see docs/MCP.md): run the documented `opencode run` command from a plain Windows terminal | terminal output showing the tool calls + the correct answer (cosmetic PowerShell stderr noise is fine to include) |

All eight are embeds in the README "Screenshots" section (PNG, no annotations needed —
the UI already labels everything).
