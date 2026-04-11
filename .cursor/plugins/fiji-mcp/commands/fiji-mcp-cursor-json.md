---
name: fiji-mcp-cursor-json
description: Show a Cursor-style mcp.json snippet for the Fiji MCP stdio server (python -m fiji_mcp) with FIJI_PATH and headless placeholders.
---

# Fiji MCP — Cursor MCP JSON snippet

Paste into your Cursor MCP configuration (merge under `mcpServers`). Replace placeholders with your real interpreter and Fiji install root.

```json
{
  "mcpServers": {
    "fiji": {
      "command": "/path/to/venv-or-conda/bin/python",
      "args": ["-m", "fiji_mcp"],
      "env": {
        "FIJI_PATH": "/path/to/Fiji",
        "FIJI_MODE": "headless",
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

Optional additions to `env` (see upstream **`fiji-mcp-server`** README):

- **`FIJI_DATA_ROOTS`**: allowlist for image I/O (host-separated list of roots).
- **`FIJI_MCP_PYTHON`**: only needed for external **driver** scripts that spawn another Python; the MCP block above already pins the server interpreter via `command`.

After editing MCP config, **reload Cursor** (or restart) so the server restarts with new variables.
