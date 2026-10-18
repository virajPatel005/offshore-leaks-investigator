# MCP server (D8, D12)

Own small server with fixed, purpose-built tools (not generic text-to-Cypher).
Read-only: the name full-text indexes are created once at server startup, so
every tool call only reads. Nothing is exposed publicly (local stdio).

## Launch

From the repo root, with FalkorDB running:

```
docker compose up -d
.venv/bin/python backend/mcp_server/server.py
```

Tools: `search_entity_tool`, `strongest_connection_tool`, `shared_neighbors_tool`.
Resource: `graph-schema://offshore` (labels, edge types, core vs soft, degree meaning).
Every result carries the Cypher used, a limitations note, and truncation flags.
Tool budget: 20 s per call, structured errors, no tracebacks.

## opencode config (EMPTY folder, per D12)

Run the client from an EMPTY folder holding only this config — never from the
repo (the repo's AGENTS.md would make the client act as a coder). No secrets:
the server needs no keys and defaults to localhost:6379.

On this machine opencode is the Windows build (the `opencode` shim in WSL
execs `opencode.exe`), so the MCP command must pass through `wsl.exe`.
VERIFIED 2026-10-17; folder used: `C:\Users\<your-user>\icij-mcp-check` (outside the
repo, holds only `opencode.json`). The verified run used the author's own paths
and folder names — substitute yours in every path below.

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "offshore": {
      "type": "local",
      "command": ["wsl.exe", "-d", "Ubuntu",
                  "--cd", "<repo-path>",
                  "-e", "<repo-path>/.venv/bin/python",
                  "backend/mcp_server/server.py"],
      "enabled": true
    }
  },
  "permission": { "edit": "deny", "bash": "deny", "webfetch": "deny", "websearch": "deny" }
}
```

(The permission block is optional; it keeps the demo client to MCP tools only.)
For a natively-installed Linux opencode, drop the `wsl.exe` wrapper and use
`"command": ["<repo-path>/.venv/bin/python",
"backend/mcp_server/server.py"]` with `"cwd": "<repo-path>"`.
Clients see the tools prefixed with the server name: `offshore_search_entity_tool`,
`offshore_strongest_connection_tool`, `offshore_shared_neighbors_tool`.

## D12 check result (2026-10-17) — PASSED

Model `opencode/deepseek-v4.1-flash-free`; command run from the empty folder:

```
opencode run -m opencode/deepseek-v4.1-flash-free "Use the offshore MCP tools (offshore_search_entity_tool, offshore_strongest_connection_tool) to answer: what is the strongest recorded connection between GALAXY ASIA LIMITED. and TO.CE.CO LIMITED.? Give the path and the score."
```

Observed (~20 s): two `offshore_search_entity_tool` calls (GALAXY ASIA LIMITED /
TO.CE.CO LIMITED) → `offshore_strongest_connection_tool {"source_id":"123345","target_id":"170362"}`
→ answer "score 9.35, 3 hops: GALAXY ASIA LIMITED. → Tricor Services Limited →
address → TO.CE.CO LIMITED" — the correct T2Q1 result. The same MCP server thus
serves both the product agent and an external opencode client (multi-client
check). PowerShell's npm shim prints one cosmetic `NativeCommandError` line on
stderr; the run itself is clean (use a plain terminal for the video).
