# Fiji MCP Server

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: BSD-3-Clause](https://img.shields.io/badge/License-BSD--3--Clause-blue.svg)](https://opensource.org/licenses/BSD-3-Clause)
[![CI](https://github.com/surajinacademia/Fiji_imageJ_mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/surajinacademia/Fiji_imageJ_mcp/actions/workflows/ci.yml)

**Fiji MCP** is a [Model Context Protocol](https://modelcontextprotocol.io/) server that lets AI assistants drive **Fiji / ImageJ** through natural language: run macros, discover commands, open and save images, capture verification screenshots, and chain multi-step workflows—powered by **PyImageJ** and **FastMCP**.

<p align="center">
  <table>
    <tr>
      <td align="center" width="50%">
        <a href="https://raw.githubusercontent.com/surajinacademia/Fiji_imageJ_mcp/main/demo_output/active_image.jpg">
          <img src="https://raw.githubusercontent.com/surajinacademia/Fiji_imageJ_mcp/main/demo_output/active_image.jpg" alt="Active image view in Fiji" width="100%" />
        </a>
        <sub><b>Active image</b> — headless-friendly screenshot via <code>screenshot_fiji</code> (<code>active_image</code>)</sub>
      </td>
      <td align="center" width="50%">
        <a href="https://raw.githubusercontent.com/surajinacademia/Fiji_imageJ_mcp/main/demo_output/results_table.jpg">
          <img src="https://raw.githubusercontent.com/surajinacademia/Fiji_imageJ_mcp/main/demo_output/results_table.jpg" alt="Results table rendered from Measure" width="100%" />
        </a>
        <sub><b>Results table</b> — Measure/Results render for reproducible reporting</sub>
      </td>
    </tr>
  </table>
</p>

> **Note:** This project follows the same “install into your AI app’s MCP config” pattern as [napari-mcp](https://napari-hub.org/plugins/napari-mcp.html) and our sibling project [**cellpose_mcp**](https://github.com/surajinacademia/cellpose_mcp). Contributions and collaboration are welcome—reach out at **ssahu2@ucmerced.edu**.

---

## Project status

| Phase | Scope | Status |
|-------|--------|--------|
| 1 | PyImageJ bridge, macros, screenshots, config | Done |
| 2 | Command/extension discovery and search | Done |
| 3 | Workflows and batch macros | Done |
| 4 | Screenshot limits/cache, smart/headless modes, timeouts | Done |
| 5 | Integration tests with real Fiji, benchmarks, release polish | In progress |

Unit tests run on every push (**Python 3.10–3.12**); CI runs `pytest -m "not integration"`. Integration tests run locally when `FIJI_PATH` and `FIJI_TEST_IMAGE` are set.

---

## Requirements

- **Python** 3.10 or later (venv or conda recommended)
- [**Fiji**](https://fiji.sc/) installed locally (folder containing `jars/` and `plugins/`)
- **Java** compatible with your Fiji build
- **Display** only if you need full-screen Robot capture (`FIJI_MODE=gui`). Headless MCP workflows still support `active_image` and `results_table` screenshots.

---

## Quick start

**1. Clone and install (development / research)**

```bash
git clone https://github.com/surajinacademia/Fiji_imageJ_mcp.git
cd Fiji_imageJ_mcp
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[test]"
```

**2. Point the server at your Fiji install**

Set `FIJI_PATH` to the **installation root** (the directory that contains `jars/` and `plugins/`), e.g. `/Applications/Fiji` on macOS for a typical download—not only the nested `.app` bundle path.

**3. Configure your AI app in one command**

Use the same Python environment where you ran `pip install` (so `pyimagej`, `scyjava`, and `fiji_mcp` resolve):

```bash
# Cursor — writes ~/.cursor/mcp.json (headless is the default; stable inside IDE MCP)
fiji-mcp-install install cursor --fiji-path /Applications/Fiji

# Claude Desktop
fiji-mcp-install install claude-desktop --fiji-path /Applications/Fiji
```

Optional: `--mode gui|headless|auto|smart` and `--command /path/to/venv/bin/fiji-mcp-server` if the app’s PATH does not see your venv.

**Restart Cursor or Claude** after changing MCP config.

---

## Auto-configure your AI application

| Application | Command | Notes |
|-------------|---------|--------|
| **Cursor** | `fiji-mcp-install install cursor --fiji-path <ABS_PATH>` | Default **`FIJI_MODE=headless`** is recommended for MCP stability. |
| **Claude Desktop** | `fiji-mcp-install install claude-desktop --fiji-path <ABS_PATH>` | Same config merge pattern as napari-mcp. |

For other MCP-capable hosts, use the JSON shape below with the **same** Python that has `fiji-mcp-server` installed.

---

## Manual configuration (Cursor / Claude / custom)

Use the interpreter from your venv or conda env:

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

- **Cursor:** `~/.cursor/mcp.json` (global) or project-local `.cursor/mcp.json` if you prefer.
- **`PYTHONUNBUFFERED=1`:** keeps stdio JSON-RPC lines flushing promptly.

---

## What can you ask?

Try prompts like:

```
Run a health check on the Fiji MCP server, then open ./demo_images/sample_gradient.pgm
Search ImageJ commands matching "Gaussian blur"
Run a macro that applies Gaussian blur then reports mean gray value in the ROI
Take an active_image screenshot and a results_table screenshot after Measure
```

**Batch reporting:** `scripts/generate_image_analysis_report.py` drives the **same stdio MCP** your IDE uses and writes `research_output/analysis_raw.json` plus `docs/fiji_mcp_comprehensive_image_analysis_report.md`—no in-process shortcuts.

---

## Demo: open → analyze → screenshots

```bash
export FIJI_PATH=/Applications/Fiji
export FIJI_MODE=headless
python scripts/demo_fiji_mcp_session.py
```

This mirrors a napari-mcp-style smoke flow: `health_check`, open `demo_images/sample_gradient.pgm`, blur/stats macros, `active_image` / `results_table` screenshots, and optional `full_screen` when a display is available.

---

## MCP tools (overview)

The server exposes **17** tools grouped by role:

### Fiji lifecycle and macros

| Tool | Purpose |
|------|---------|
| `health_check` | Verify Fiji/PyImageJ readiness |
| `run_macro` | Execute ImageJ macro code (with retries) |
| `run_batch_macros` | Run multiple macros in sequence |
| `open_image` | Open a path-resolved image |
| `save_image` | Save the active image with format hint |

### Screenshots and verification

| Tool | Purpose |
|------|---------|
| `screenshot_fiji` | `full_screen`, `active_image`, or `results_table` capture modes |

### Discovery and metadata

| Tool | Purpose |
|------|---------|
| `list_all_commands` | Enumerate commands (CommandService + menus) |
| `search_commands` | Fuzzy search over command names |
| `describe_plugin` | Details for a specific command |
| `list_extensions` | List extensions / plugins |
| `list_open_images` | Titles of open windows |
| `get_image_info` | Dimensions, type, calibration for an image |

### Workflows and session helpers

| Tool | Purpose |
|------|---------|
| `run_workflow` | Async multi-step workflow with MCP progress when supported |
| `parse_macro_output` | Structured parsing helpers for macro text |
| `compare_screenshots` | Compare two screenshot payloads |
| `list_macro_templates` / `get_macro_template` | Curated macro templates |
| `get_session_trace` / `clear_session_trace` | Session diagnostics |

---

## Architecture

```text
┌─────────────────┐     stdio JSON-RPC      ┌──────────────────┐
│  Cursor / Claude │ ◄──────────────────────►│   FastMCP        │
│  or MCP client   │                         │   (fiji_mcp)     │
└─────────────────┘                         └────────┬─────────┘
                                                     │
                                            PyImageJ │ JPype
                                                     ▼
                                            ┌──────────────────┐
                                            │  Fiji / ImageJ   │
                                            │  plugins + IJ2   │
                                            └──────────────────┘
```

**Design highlights**

- **Universal plugin surface** — most Fiji capability is reachable via macros plus command discovery.
- **Headless-first** — stable MCP sessions without a full desktop; GUI mode when you need Robot-based full-screen capture.
- **Stdio-safe macros** — avoid ImageJ `print()` in macros when using stdio transport (stdout must stay clean for JSON-RPC). Return strings or use tool-level logging instead.
- **Stateful automation** — multi-step sessions with optional trace and workflow progress.

---

## Important environment variables

| Variable | Role | Typical value |
|----------|------|----------------|
| `FIJI_PATH` | Fiji install root (contains `jars/`, `plugins/`) | `/Applications/Fiji` |
| `FIJI_MODE` | `gui`, `headless`, `auto`, or `smart` | `headless` for IDE MCP |
| `FIJI_JAVA_HOME` | Force JPype Java home | Optional |
| `FIJI_OPERATION_TIMEOUT_SECONDS` | Tool timeout hint | `60` (1–86400) |
| `FIJI_DATA_ROOTS` | Allowlist roots for `open_image` / `save_image` | Empty = no restriction |
| `FIJI_MCP_PYTHON` | Python used to spawn MCP for batch scripts | Defaults to `sys.executable` |
| `FIJI_LOG_LEVEL` | Server log level (`stderr` only) | `WARNING` |

Invalid numeric env values cause **exit code 2** at startup (`python -m fiji_mcp` / `fiji-mcp-server`).

<details>
<summary><b>More tuning (screenshots, GC, macro limits, …)</b></summary>

- `FIJI_SCREENSHOT_MAX_DIM` — max dimension for screenshots (default `1920`)
- `FIJI_SCREENSHOT_QUALITY` — JPEG quality (default `85`)
- `FIJI_SCREENSHOT_CACHE_SIZE` — LRU cache size (default `5`)
- `FIJI_GC_EVERY_N_OPERATIONS` — periodic GC interval (default `10`)
- `FIJI_MAX_MACRO_CHARS` — max macro length for `run_macro` / batch (default `500000`)
- `FIJI_TEST_IMAGE` — path for integration tests
- `FIJI_INTERACTIVE_FORCE` — set `1` on macOS with `FIJI_MODE=gui` if PyImageJ needs `interactive:force`

</details>

---

## Production notes

- Prefer **`FIJI_MODE=headless`** for remote or IDE-hosted MCP unless you truly need full-screen Robot capture.
- Set **`FIJI_DATA_ROOTS`** when the host is shared or driven by untrusted prompts.
- First **Fiji cold start** can take **30–90s** before `health_check` returns; subsequent calls are usually fast.

### If the MCP “does nothing” or times out

- **Cursor + `FIJI_MODE=gui` on macOS** often blocks or hangs—use **`headless`** for MCP; you still get `active_image` and `results_table`.
- **`ModuleNotFoundError: scyjava`** — the interpreter launching the server is wrong; reinstall with `fiji-mcp-install` so the config uses the venv/conda `python -m fiji_mcp`.

---

## Batch image analysis report

Spawns the Fiji MCP server over stdio (same as Cursor) and calls tools via the MCP client:

```bash
export FIJI_PATH=/Applications/Fiji
export FIJI_MODE=headless
export FIJI_MCP_PYTHON=/path/to/conda-or-venv/bin/python   # if the driver Python lacks pyimagej
python scripts/generate_image_analysis_report.py
```

---

## Cursor plugin (optional)

A small **Cursor plugin** lives under [`.cursor/plugins/fiji-mcp/`](.cursor/plugins/fiji-mcp/) (rules, skill, slash command for MCP JSON). Local plugins load from `~/.cursor/plugins/local/<name>/`.

```bash
cp -R .cursor/plugins/fiji-mcp ~/.cursor/plugins/local/fiji-mcp
```

Then **Command Palette → Developer: Reload Window**. See the plugin [`README.md`](.cursor/plugins/fiji-mcp/README.md) for discovery in Settings → Rules and skills.

---

## Development

```bash
pip install -e ".[test]"
pytest
```

Integration tests: set both `FIJI_PATH` and `FIJI_TEST_IMAGE`, then run the full suite without `-m "not integration"`.

Roadmap and deep implementation notes: [`plan.md`](plan.md).

---

## Author

**Suraj Sahu** — Department of Physics, University of California Merced, USA · **ssahu2@ucmerced.edu**

---

## Acknowledgments

- [**ImageJ2**](https://imagej.net/software/imagej2) / [**PyImageJ**](https://pyimagej.readthedocs.io/) teams
- [**napari-mcp**](https://napari-hub.org/plugins/napari-mcp.html) (royerlab) for MCP installer patterns
- [**FastMCP**](https://github.com/jlowin/fastmcp) for the Python MCP stack
- [**Anthropic**](https://www.anthropic.com/) and the [**Model Context Protocol**](https://modelcontextprotocol.io/) community

---

## License

**BSD-3-Clause** — see [`pyproject.toml`](pyproject.toml) (`project.license`).
