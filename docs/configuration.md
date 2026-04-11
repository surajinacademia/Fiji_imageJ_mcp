# Configuration

## Auto-install (`fiji-mcp-install`)

| Application | Command | Config file |
|-------------|---------|-------------|
| **Cursor** | `fiji-mcp-install install cursor --fiji-path <ABS>` | `~/.cursor/mcp.json` |
| **Claude Desktop** | `fiji-mcp-install install claude-desktop --fiji-path <ABS>` | macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`; Linux/Windows: see [Anthropic docs](https://support.anthropic.com/) |
| **Claude Code** (user) | `fiji-mcp-install install claude-code --fiji-path <ABS>` | `~/.claude.json` → top-level `mcpServers` ([Claude Code MCP](https://code.claude.com/docs/en/mcp)) |
| **Claude Code** (project) | `fiji-mcp-install install claude-code --fiji-path <ABS> --project <DIR>` | `<DIR>/.mcp.json` (commit-friendly team scope) |
| **Gemini CLI** | `fiji-mcp-install install gemini --fiji-path <ABS>` | `~/.gemini/settings.json` → `mcpServers` ([Gemini CLI MCP](https://geminicli.com/docs/tools/mcp-server/)) |
| **Windsurf** | `fiji-mcp-install install windsurf --fiji-path <ABS>` | `~/.codeium/windsurf/mcp_config.json` ([Windsurf MCP](https://docs.windsurf.com/windsurf/cascade/mcp)) |

Options:

- `--mode` — `gui`, `headless`, `auto`, or `smart` (default `headless`).
- `--command` — absolute path to `fiji-mcp-server` if the host app’s PATH does not see your venv.
- `--project DIR` — **only with `claude-code`:** write project-scoped `.mcp.json` under `DIR` instead of user `~/.claude.json`.

Restart the IDE or CLI after changing MCP config.

## Manual MCP JSON

Use the Python executable from the environment where `fiji-mcp-server` / `fiji_mcp` is installed:

```json
{
  "mcpServers": {
    "fiji": {
      "command": "/path/to/venv-or-conda/bin/python",
      "args": ["-m", "fiji_mcp"],
      "env": {
        "FIJI_PATH": "/Applications/Fiji",
        "FIJI_MODE": "headless",
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

- **Cursor:** `~/.cursor/mcp.json` or project `.cursor/mcp.json`.
- **Claude Code:** user merge goes to `~/.claude.json`; project merge to `.mcp.json` (see table above).
- **Gemini CLI:** `~/.gemini/settings.json` may already contain other keys; the installer only merges `mcpServers.fiji`.
- **Windsurf:** same JSON shape as Cursor (`mcpServers` with `command` / `args` / `env`).
- **`PYTHONUNBUFFERED=1`:** keeps stdio JSON-RPC lines flushing promptly.

An example file lives at [`.mcp.json`](../.mcp.json) in the repository (edit `FIJI_PATH` and `command` for your machine).

## Environment variables

| Variable | Role | Typical |
|----------|------|---------|
| `FIJI_PATH` | Fiji root (`jars/`, `plugins/`) | `/Applications/Fiji` |
| `FIJI_MODE` | `gui`, `headless`, `auto`, `smart` | `headless` for IDE MCP |
| `FIJI_JAVA_HOME` | Force JPype Java home | Optional |
| `FIJI_OPERATION_TIMEOUT_SECONDS` | Tool timeout hint | `60` (range 1–86400) |
| `FIJI_DATA_ROOTS` | Allowlist for `open_image` / `save_image` | Empty = unrestricted |
| `FIJI_MCP_PYTHON` | Python to spawn MCP in batch scripts | Defaults to driver `sys.executable` |
| `FIJI_LOG_LEVEL` | Python log level (stderr only) | `WARNING` |

Invalid numeric env values → **exit code 2** at startup (`python -m fiji_mcp` / `fiji-mcp-server`).

### Additional tuning

- `FIJI_SCREENSHOT_MAX_DIM` — default `1920`
- `FIJI_SCREENSHOT_QUALITY` — JPEG quality, default `85`
- `FIJI_SCREENSHOT_CACHE_SIZE` — LRU size, default `5`
- `FIJI_GC_EVERY_N_OPERATIONS` — default `10`
- `FIJI_MAX_MACRO_CHARS` — macro size cap, default `500000`
- `FIJI_TEST_IMAGE` — integration test image path
- `FIJI_INTERACTIVE_FORCE` — `1` on macOS + `gui` if PyImageJ needs `interactive:force`

## Production notes

- Prefer **`headless`** for remote or IDE-hosted MCP unless you need full-screen Robot capture.
- Set **`FIJI_DATA_ROOTS`** on shared or untrusted-prompt hosts.
- First Fiji cold start can take **30–90s** before `health_check` succeeds.

## Troubleshooting

- **Cursor + `gui` on macOS** often hangs — use **`headless`**; `active_image` and `results_table` still work.
- **`ModuleNotFoundError: scyjava`** — wrong interpreter in MCP config; point `command` at the venv/conda Python with `pyimagej` installed, or re-run `fiji-mcp-install`.

## Cursor plugin (optional)

Bundled under [`.cursor/plugins/fiji-mcp/`](../.cursor/plugins/fiji-mcp/) (rules, skill, slash command). Install locally:

```bash
cp -R .cursor/plugins/fiji-mcp ~/.cursor/plugins/local/fiji-mcp
```

**Developer: Reload Window** in Cursor. See the plugin [README](../.cursor/plugins/fiji-mcp/README.md).
