# Fiji MCP Server

`fiji-mcp-server` is a FastMCP stdio server that gives LLM agents access to Fiji/ImageJ through PyImageJ.

It is designed for:

- universal plugin access via macro execution
- command discovery (`CommandService` + legacy `Menus`)
- GUI screenshots for visual verification workflows
- stateful multi-step automation

## Project status

**Current phase:** Phase 5 — testing and deployment prep (tracked in `plan.md`).

| Phase | Scope | Status |
|-------|--------|--------|
| 1 | PyImageJ bridge, macros, screenshots, config | Done |
| 2 | Command/extension discovery and search | Done |
| 3 | Workflows and batch macros | Done |
| 4 | Screenshot limits/cache, smart/headless modes, timeouts | Done |
| 5 | Integration tests with real Fiji, benchmarks, release polish | In progress |

Unit tests: `pytest` (use a venv or conda env with `pip install -e ".[test]"` so `imagej` / `jpype1` resolve). Integration tests run only when `FIJI_PATH` and `FIJI_TEST_IMAGE` are set. CI (`.github/workflows/ci.yml`) runs `pytest -m "not integration"` on Python 3.10–3.12.

## Requirements

- Python 3.10+
- Fiji installed locally
- Java runtime compatible with your Fiji install
- Display server for screenshots (`FIJI_MODE=gui` with desktop or Xvfb)

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[test]"
```

## Environment Variables

- `FIJI_PATH`: absolute path to the Fiji **installation root** (folder containing `jars/` and `plugins/`), e.g. `/Applications/Fiji` on macOS for a typical download layout—not only the nested `Fiji.app` bundle
- `FIJI_JAVA_HOME`: optional Java home to force JPype runtime (useful when plugins need newer Java)
- `FIJI_MODE`: `gui`, `headless`, `auto`, or `smart` (default: `smart`)
- `FIJI_OPERATION_TIMEOUT_SECONDS`: tool timeout hint (seconds), default `60`, validated range `1`–`86400`
- `FIJI_SCREENSHOT_MAX_DIM`: resize cap for screenshots, default `1920`
- `FIJI_SCREENSHOT_QUALITY`: JPEG quality, default `85`
- `FIJI_SCREENSHOT_CACHE_SIZE`: LRU cache size, default `5`
- `FIJI_GC_EVERY_N_OPERATIONS`: periodic GC interval, default `10`
- `FIJI_TEST_IMAGE`: image path used by integration tests
- `FIJI_INTERACTIVE_FORCE`: set to `1` on macOS with `FIJI_MODE=gui` if PyImageJ refuses `interactive` for a local `python` demo (uses PyImageJ `interactive:force`; try without it inside Cursor’s MCP subprocess first)
- `FIJI_MCP_PYTHON`: optional path to the Python interpreter used to **spawn** the MCP server subprocess (used by `scripts/generate_image_analysis_report.py`; defaults to the script’s own `sys.executable`). Set this when the driver runs with a minimal Python but Fiji needs a conda/venv that has `pyimagej` / `scyjava`
- `FIJI_DATA_ROOTS`: optional **allowlist** for `open_image` / `save_image`: `os.pathsep`-separated list of directory roots; resolved paths must lie under one of them. Empty (default) = no restriction (suitable for trusted single-user workstations; set in shared or agent-facing deployments).
- `FIJI_MAX_MACRO_CHARS`: maximum macro string length accepted by `run_macro` / batch tools (default `500000`, range `4096`–`10000000`) to limit accidental or malicious huge payloads.
- `FIJI_LOG_LEVEL`: Python log level for server-side diagnostics (`DEBUG`, `INFO`, `WARNING`, …); default `WARNING`. Logs go to **stderr** so stdout stays clean for stdio MCP.

## Production notes

- Prefer **`FIJI_MODE=headless`** for remote or IDE-hosted MCP unless you truly need full-screen Robot capture.
- Set **`FIJI_DATA_ROOTS`** when the MCP host is shared or driven by untrusted prompts, so agents cannot open arbitrary host paths.
- Keep **`PYTHONUNBUFFERED=1`** in the MCP subprocess env so RPC lines flush promptly.
- Invalid numeric env values cause the server to **exit with code 2** at startup (`python -m fiji_mcp` / `fiji-mcp-server`).

## Configure your AI app (Claude Desktop or Cursor)

After `pip install -e ".[test]"`, the `fiji-mcp-install` CLI merges a `fiji` entry into the client config (same idea as [napari-mcp](https://napari-hub.org/plugins/napari-mcp.html) for napari).

```bash
# Use the same Python environment where you ran pip install (has pyimagej / scyjava).
# FIJI_PATH = folder that contains jars/ and plugins/ (often /Applications/Fiji on macOS).
# Default install mode is headless (reliable inside Cursor); add --mode gui only for local desktop + Robot.

fiji-mcp-install install cursor --fiji-path /Applications/Fiji

# If `fiji-mcp-install` is not on PATH for Cursor, pin the script from that env:
fiji-mcp-install install cursor --fiji-path /Applications/Fiji \
  --command "/path/to/venv-or-conda/bin/fiji-mcp-server"

# Claude Desktop
fiji-mcp-install install claude-desktop --fiji-path /Applications/Fiji
```

Restart Cursor or Claude after changing MCP config.

### If the MCP “does nothing” or times out

- **Cursor + `FIJI_MODE=gui` on macOS** often blocks for minutes or hangs: use **`FIJI_MODE=headless`** for MCP (you still get `active_image` and `results_table` screenshots).
- **`ModuleNotFoundError: scyjava`** means the interpreter starting the server is wrong (e.g. base conda): use the venv/conda env where you installed `fiji-mcp-server`, or reinstall with `fiji-mcp-install` so the config uses `python -m fiji_mcp` from that env.
- First **Fiji cold start** can take 30–90s before `health_check` returns; wait once, then tools should be fast.

### Manual JSON (Cursor-style)

```json
{
  "mcpServers": {
    "fiji": {
      "command": "/path/to/conda-or-venv/bin/python",
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

## Demo: open image → analyze → screenshots

With Fiji installed and `FIJI_PATH` set (use `FIJI_MODE=gui` only for local full-screen Robot capture; headless is fine for the script’s image/results screenshots):

```bash
export FIJI_PATH=/Applications/Fiji
export FIJI_MODE=headless
python scripts/demo_fiji_mcp_session.py
```

This runs the same style of flow as napari-mcp quick tests: health check, open `demo_images/sample_gradient.pgm`, blur macro, stats, `active_image` / `results_table` screenshots, and optional `full_screen` if a display is available.

## Batch image analysis report (MCP client only)

`scripts/generate_image_analysis_report.py` builds `research_output/analysis_raw.json` and `docs/fiji_mcp_comprehensive_image_analysis_report.md` by **spawning the Fiji MCP server over stdio** and calling tools through the MCP client (`fastmcp` `Client` + `StdioTransport`). It does **not** import `fiji_mcp` tool modules in-process, so the run matches how Cursor or Claude drive the server.

```bash
export FIJI_PATH=/Applications/Fiji
export FIJI_MODE=headless
# If the Python running this script lacks pyimagej/scyjava, point at the env that has them:
export FIJI_MCP_PYTHON=/path/to/conda-or-venv/bin/python
python scripts/generate_image_analysis_report.py
```

**Stdio and macros:** when the server uses stdio transport, **ImageJ `print()` must not be used in macros** (it writes to stdout and can corrupt JSON-RPC). Prefer returning a string from the macro, logging via mechanisms that do not touch the process stdout, or handling output inside tool responses only.

## Cursor plugin (optional)

A small **Cursor plugin** ships in this repo under [`.cursor/plugins/fiji-mcp/`](.cursor/plugins/fiji-mcp/) (rules, skill, slash command for MCP JSON). Cursor loads **local** plugins from `~/.cursor/plugins/local/<name>/`, not from the Marketplace browser.

1. **Install:** `cp -R .cursor/plugins/fiji-mcp ~/.cursor/plugins/local/fiji-mcp` (from repo root), then **Command Palette → Developer: Reload Window**.
2. **Find it:** Local plugins do not appear as a marketplace tile. Open **Settings → Rules** and search for **Fiji** / stdio; check **skills** (e.g. `fiji-mcp-workflow`); use slash command **`/fiji-mcp-cursor-json`** for the snippet. See the plugin’s own [`README.md`](.cursor/plugins/fiji-mcp/README.md) if rules do not show up (update Cursor, confirm the path above exists).

## Main Tools

- `health_check`
- `run_macro`
- `run_batch_macros`
- `open_image`
- `save_image`
- `screenshot_fiji` (`capture_mode`: `full_screen` = primary monitor + display; `active_image` = current image; `results_table` = render Measure/Results — last two work without a desktop)
- `run_workflow` (async; MCP progress when the client sends a progress token)
- `list_all_commands`
- `search_commands`
- `describe_plugin`
- `list_extensions`
- `list_open_images`
- `get_image_info`

## Test

```bash
pytest
```

Integration tests run only when both `FIJI_PATH` and `FIJI_TEST_IMAGE` are set.
