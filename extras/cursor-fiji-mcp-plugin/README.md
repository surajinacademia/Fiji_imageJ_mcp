# Fiji MCP (Cursor plugin)

Small local plugin for working with the **Fiji/ImageJ MCP server** (FastMCP over stdio: `python -m fiji_mcp` / `fiji-mcp-server`).

## Install location

This tree lives at:

`~/.cursor/plugins/local/fiji-mcp/`

Cursor loads plugins from `~/.cursor/plugins/local/` automatically.

## Where to find it in Cursor (local plugins are not in the Marketplace list)

Local plugins **do not** show up as a separate “Fiji MCP” marketplace tile. Their **rules**, **skills**, and **commands** merge into Cursor like this:

1. **Reload** after install: Command Palette → **Developer: Reload Window** (or fully quit Cursor).
2. **Rules:** **Settings** (Cmd+Shift+J) → search **Rules** → find **Fiji MCP — stdio and data** (or filter by your rule description). Toggle **Always** / **Agent Decides** / **Manual** as you prefer.
3. **Skills:** **Settings** → **Rules** section → **Agent Decides** / skills list → look for **`fiji-mcp-workflow`**. In chat you can also try **`/fiji-mcp-workflow`** if your Cursor build exposes skills as slash commands.
4. **Commands:** Command Palette or slash menu → **`/fiji-mcp-cursor-json`** (command id `fiji-mcp-cursor-json`) for the MCP JSON snippet.
5. **Verify on disk:** In Terminal: `ls ~/.cursor/plugins/local/fiji-mcp/.cursor-plugin/plugin.json` — if that file is missing, the plugin is not installed in the folder Cursor scans.

**Plugins feature flag:** Plugins require a recent Cursor (2.5+). If nothing appears, update Cursor and reload again.

## What you get

- **Skill** `fiji-mcp-workflow`: env vars, stdio-safe macro rules, suggested MCP tool order for batch analysis, and optional batch-report flow when your checkout includes the upstream script.
- **Skill** `fiji-mcp-image-analysis`: batch / report workflow over MCP (`generate_image_analysis_report.py` or the same tool sequence in chat).
- **Rule** `fiji-mcp-stdio-and-data`: reminders for `print()` vs stdout and `FIJI_DATA_ROOTS` when editing macros or MCP JSON.
- **Command** `/fiji-mcp-cursor-json`: Cursor `mcp.json` snippet with placeholders (no machine-specific paths).

## Prerequisites

1. Install the **`fiji-mcp-server`** Python package in a dedicated venv or conda env (needs PyImageJ / scyjava).
2. Set **`FIJI_PATH`** to your Fiji **installation root** (directory that contains `jars/` and `plugins/`), for example `/path/to/Fiji` on macOS or Linux.
3. For IDE-hosted MCP, prefer **`FIJI_MODE=headless`** unless you explicitly need GUI/Robot capture.
4. Point Cursor’s MCP config at that env’s interpreter with args `["-m", "fiji_mcp"]`, and pass env vars there or in the shell profile used by Cursor.

Optional: **`FIJI_MCP_PYTHON`** when a driver script runs under a different Python than the one that has PyImageJ. **`FIJI_DATA_ROOTS`**: `os.pathsep`-separated allowlist roots for `open_image` / `save_image`. **`PYTHONUNBUFFERED=1`** on the server subprocess so RPC lines flush promptly.

## Upstream documentation

Environment variables, `fiji-mcp-install`, and production notes are documented in the **`fiji-mcp-server`** project README (install, timeouts, log level, macro size limits).

## Copy from this repo

The plugin source is tracked at **`extras/cursor-fiji-mcp-plugin/`** (not under `.cursor/`, which stays local-only). To (re)install into Cursor’s local folder:

```bash
rm -rf ~/.cursor/plugins/local/fiji-mcp
cp -R /path/to/Fiji_imageJ_mcp/extras/cursor-fiji-mcp-plugin ~/.cursor/plugins/local/fiji-mcp
```

Then **Developer: Reload Window**.
