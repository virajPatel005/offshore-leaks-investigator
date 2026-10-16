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

opencode.json

```
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "offshore": {
      "type": "local",
      "command": ["/home/viraj/projects/offshore-investigator/.venv/bin/python",
                  "backend/mcp_server/server.py"],
      "cwd": "/home/viraj/projects/offshore-investigator",
      "enabled": true
    }
  }
}
```

Replace the two paths with your checkout location. External client check
(opencode/Claude Code from the empty folder) is a separate 30 min task (D12)
and has NOT been run yet.
