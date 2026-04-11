---
name: fiji-mcp-workflow
description: Run Fiji/ImageJ analysis through the Fiji MCP stdio server—env vars (FIJI_PATH, FIJI_MODE, FIJI_MCP_PYTHON, FIJI_DATA_ROOTS), headless MCP, stdio-safe macros without print(), health_check and tool sequencing, optional batch report script from a fiji-mcp-server checkout. Use for Fiji MCP workflows, microscopy batch reports, or MCP/macro config.
---

# Fiji MCP workflow

## When this applies

Use when driving **Fiji/ImageJ** through the **FastMCP stdio** server (`python -m fiji_mcp`), writing **macros** for `run_macro`, or configuring **Cursor MCP** for image analysis.

## Environment (host)

1. **`FIJI_PATH`**: absolute path to the Fiji **root** (folder with `jars/` and `plugins/`), e.g. `/path/to/Fiji`.
2. **`FIJI_MODE`**: prefer **`headless`** for IDE-hosted MCP; use `gui` only when you need desktop/Robot capture and have a display.
3. **`FIJI_MCP_PYTHON`**: if a **driver** (batch script, CI) uses a minimal interpreter, set this to the Python that has **pyimagej** / **scyjava** so subprocesses spawn the right env.
4. **`FIJI_DATA_ROOTS`**: optional allowlist (`os.pathsep`-separated roots). Paths for **`open_image`** / **`save_image`** must resolve under one root when set.
5. **`PYTHONUNBUFFERED=1`** on the MCP subprocess so stdio RPC lines flush promptly.

Other useful toggles (see upstream package docs): operation timeouts, screenshot limits, **`FIJI_LOG_LEVEL`** (logs on **stderr**), macro size cap.

## Path A — Batch report via MCP only (optional)

If your **fiji-mcp-server** repository checkout includes the batch driver (often `scripts/generate_image_analysis_report.py`):

1. Activate the same env that runs the server (fastmcp, pyimagej).
2. Export `FIJI_PATH`, `FIJI_MODE=headless`, and optionally `FIJI_MCP_PYTHON`.
3. From that repository’s root, run the script with `python` (see that script’s CLI for image dirs and outputs).

Use a longer client timeout if cold JVM or large stacks need it (see env docs in the server package).

## Path B — Agent-driven session (attached MCP)

Suggested order for a **characterization-style** pass:

1. **`health_check`** — confirm the bridge before heavy work.
2. **`list_extensions`**, **`list_all_commands`** (bounded `limit`), **`list_open_images`**.
3. **`search_commands`** for a small keyword set (e.g. network, particle, segment, threshold) with a low `limit`.
4. **`describe_plugin`** on an interesting hit when `command_name` is stable.
5. Per image: **`open_image`** → **`get_image_info`** → **`run_macro`** with a macro that **`return`s one parseable string** (do not rely on log scraping for primary metrics).
6. Optional: **`screenshot_fiji`** (`capture_mode` as needed); may fail in headless/display-limited setups.
7. Demonstrate **`run_batch_macros`** / **`run_workflow`** with trivial **`return`-only** steps if useful.

## Hard rules (stdio MCP)

- **Do not use ImageJ `print()` in macros** while the server uses **stdio**: stdout is reserved for JSON-RPC; `print()` corrupts the session.
- Prefer **`return "...";`** or tool-native structured results. Same for **batch** and **workflow** steps.
- With **`FIJI_DATA_ROOTS`** set, keep **`open_image`** / **`save_image`** paths under an allowed root.

## Extending

- Keep **`run_macro`** return strings **bounded** and **machine-parseable** (e.g. delimited fields).
- For wrong interpreter errors (**`ModuleNotFoundError: scyjava`**), fix the MCP **`command`** / env so the server starts with the PyImageJ-capable Python.

For install CLIs (`fiji-mcp-install`), full env reference, and production hardening, use the **`fiji-mcp-server`** project README.
