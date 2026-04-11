---
name: fiji-mcp-image-analysis
description: Runs reproducible Fiji/ImageJ batch analysis via the Fiji MCP server—either the bundled MCP-stdio report script or the same tool sequence through an MCP client. Use when generating the comprehensive image analysis report, batch-processing demo_images, driving health_check/open_image/run_macro/search_commands, or when the user mentions Fiji MCP image workflows, microscopy batch reports, or stdio-safe ImageJ macros.
---

# Fiji MCP image analysis workflow

## When this applies

Use this skill for **batch characterization of images under `demo_images/`** (or the same pattern on other paths) using **Fiji MCP tools**, with emphasis on **reproducibility** and **stdio-safe** macro usage.

## Path A — Full report (preferred)

Runs analysis **only over MCP** (subprocess server + `Client` + `StdioTransport`); does not call `fiji_mcp` tools in-process.

1. Ensure a Python env with **`fastmcp`** and **`pyimagej`/`scyjava`** (the same class of env that runs the server).
2. Set **`FIJI_PATH`** to the Fiji install root (folder with `jars/` and `plugins/`). Prefer **`FIJI_MODE=headless`** for IDE-hosted MCP.
3. If the shell running the script is **not** the Fiji env, set **`FIJI_MCP_PYTHON`** to that env’s `python`.
4. Run from repo root:

```bash
export FIJI_PATH=/path/to/Fiji
export FIJI_MODE=headless
# optional: export FIJI_MCP_PYTHON=/path/to/conda/bin/python
python scripts/generate_image_analysis_report.py
```

5. **Artifacts:** `research_output/analysis_raw.json` (JSON, large `image_base64` stripped) and `docs/fiji_mcp_comprehensive_image_analysis_report.md`.

6. **Images scanned:** sorted files in `demo_images/` with extensions `.png`, `.pgm`, `.pbm`, `.ppm`, `.tif`, `.tiff`, `.jpg`, `.jpeg` (no dotfiles).

Optional: **`FIJI_MCP_CLIENT_TOOL_TIMEOUT`** (default `900`) if cold-start or huge stacks need a longer client tool timeout.

## Path B — Same logic via connected MCP (agent-driven)

If the user already has the **Fiji MCP server** attached in Cursor/Claude, mirror the script’s order for a comparable report:

1. **`health_check`** — confirm bridge before heavy work.
2. **`list_extensions`**, **`list_all_commands`** (with a reasonable `limit`), **`list_open_images`**.
3. **`search_commands`** for a small set of queries (e.g. `network`, `particle`, `colocal`, `segment`, `threshold`) with a low `limit`.
4. **`describe_plugin`** on one interesting hit from search (when a stable `command_name` exists).
5. For each image: **`open_image`** → **`get_image_info`** → **`run_macro`** with a stats macro that **`return`s a single parseable string** (do not rely on log scraping for primary metrics).
6. **`screenshot_fiji`** with `capture_mode: "active_image"` (optional; may fail depending on mode/display).
7. After per-image work: **`run_batch_macros`** then **`run_workflow`** with **trivial `return`-only** steps if demonstrating those tools.

## Hard rules (stdio MCP)

- **Never use ImageJ `print()` in macros** while the server uses **stdio**: stdout is reserved for JSON-RPC and `print()` corrupts the session.
- Prefer **`return "...";`** or structured tool responses. Same rule applies to **batch** and **workflow** steps.
- If **`FIJI_DATA_ROOTS`** is set on the server, **`open_image` / `save_image`** paths must resolve under an allowed root.

## Extending the workflow

- Add or replace images under **`demo_images/`**, re-run the script, or repeat Path B on new paths (absolute paths the server host can read).
- For custom metrics, keep **`run_macro`** outputs **bounded** (truncate in the consumer) and **machine-parseable** (e.g. pipe-delimited tokens in the return string).

## Quick troubleshooting

- **`ModuleNotFoundError: scyjava`** on server start: wrong interpreter — fix **`FIJI_MCP_PYTHON`** / MCP config command to the env where **`fiji-mcp-server`** was installed.
- **`FIJI_PATH` missing or invalid**: set to an existing Fiji root; first **`health_check`** may take 30–90s on cold JVM.

For server install, env vars, and production toggles (**`FIJI_DATA_ROOTS`**, **`FIJI_MAX_MACRO_CHARS`**, **`FIJI_LOG_LEVEL`**), see the repo **`README.md`**.
