# CLAUDE.md

Guidance for Claude Code and similar agents working in this repository.

## Project overview

**fiji-mcp-server** is a Python [Model Context Protocol](https://modelcontextprotocol.io/) server that exposes **Fiji / ImageJ** to AI assistants (Cursor, Claude Desktop, etc.) via **PyImageJ** and **FastMCP**: macros, command discovery, I/O, screenshots, and workflows.

## Common commands

```bash
# Development install (tests + linters)
pip install -e ".[test,dev]"

# Run the MCP server (stdio)
python -m fiji_mcp
# or: fiji-mcp-server

# Write MCP config (requires absolute Fiji install root)
fiji-mcp-install install cursor --fiji-path /Applications/Fiji
fiji-mcp-install install claude-desktop --fiji-path /Applications/Fiji

# Tests (CI excludes integration)
pytest -m "not integration"

# Lint / format (after pip install -e ".[dev]")
ruff check src/ tests/ --fix
ruff format src/ tests/

# Type check
mypy src/fiji_mcp --ignore-missing-imports

# Pre-commit on all files
pre-commit run --all-files
```

## Architecture

```text
AI client ── stdio JSON-RPC ──▶ FastMCP (`fiji_mcp.mcp_instance`) ──▶ tools ──▶ PyImageJ ──▶ Fiji
```

**Entry flow:** `__main__.py` → `server.py` (imports tool modules for side-effect registration) → `mcp_instance.py` (singleton `mcp`) → `tools/*` (`@mcp.tool` handlers).

**Key paths:**

- `src/fiji_mcp/tools/macro_runner.py` — `health_check`, `run_macro`, `open_image`, `save_image`, `run_batch_macros`
- `src/fiji_mcp/tools/discovery.py` — command search, `describe_plugin`, extensions, image metadata
- `src/fiji_mcp/tools/screenshot.py` — `screenshot_fiji`
- `src/fiji_mcp/tools/workflow.py` — `run_workflow`
- `src/fiji_mcp/tools/structured_tools.py` — templates, trace, parsing helpers
- `src/fiji_mcp/fiji_bridge.py` — JVM / ImageJ lifecycle
- `src/fiji_mcp/cli/install.py` — Cursor + Claude Desktop MCP JSON merge

## Important details

- **Stdio MCP:** ImageJ `print()` in user macros must not write to **stdout** (breaks JSON-RPC). Prefer return values / Python-side logging to stderr.
- **`FIJI_PATH`:** Must point at the Fiji **root** (directory containing `jars/` and `plugins/`), not only a nested `.app` path on macOS.
- **`FIJI_MODE`:** Use **`headless`** for IDE-hosted MCP; **`gui`** is for local desktop + Robot `full_screen` capture and can hang under Cursor on macOS.
- **Integration tests:** Require `FIJI_PATH` and `FIJI_TEST_IMAGE`; marked `integration` and skipped in CI by default.
- **Documentation:** User-facing guides live under `docs/` (Docsify); roadmap in `plan.md`.
