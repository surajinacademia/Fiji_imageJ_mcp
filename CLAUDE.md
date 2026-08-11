# CLAUDE.md

Guidance for agents working on `fiji-mcp-server`.

## Project

This is a minimal Python stdio MCP server for one local Fiji/ImageJ runtime.
Its public MCP surface is exactly `get_state`, `search_commands`,
`run_command`, `run_script`, `open_image`, `save_image`, `get_results`,
`screenshot`, and `compare_screenshots`.

`FIJI_PATH` is required when Fiji first starts and must point to a root with
`jars/` and `plugins/`. `FIJI_MODE` defaults to `headless`; `gui` is an
explicit override. Before startup, the bridge prefers exactly one valid JVM
bundled for the current platform below `FIJI_PATH/java/`, preserves an existing
SciJava JVM choice, and falls back to SciJava's normal JVM selection if no
matching Fiji bundle exists. Do not add automatic Fiji-path discovery.

## Common commands

```bash
# Development install
.venv/bin/python -m pip install -e ".[test,dev,publish]"

# Run the stdio server
.venv/bin/python -m fiji_mcp

# Lint and type check
.venv/bin/python -m ruff check src/ tests/
.venv/bin/python -m mypy src/fiji_mcp --ignore-missing-imports

# Tests that do not need a Fiji installation
.venv/bin/python -m pytest -m "not integration" -v

# Local Fiji integration tests
FIJI_PATH=/Applications/Fiji FIJI_MODE=headless \
  .venv/bin/python -m pytest tests/test_integration_runtime.py -m integration -v

# Distribution validation
.venv/bin/python -m build
.venv/bin/python -m twine check dist/*
.venv/bin/python tests/wheel_smoke.py dist/fiji_mcp_server-0.2.0-py3-none-any.whl
```

## Final package layout

```text
src/fiji_mcp/
├── __init__.py     # package version and lazy mcp export
├── __main__.py     # stderr logging and stdio entry point
├── server.py       # FastMCP construction and nine registrations
├── tools.py        # public handlers and Fiji state/command/results access
├── bridge.py       # settings, JVM lifecycle, stdout routing, locks, retries
├── imaging.py      # rendering, PNG encoding, path-based comparison
└── py.typed        # typing marker
```

The final tests are `conftest.py`, `test_bridge.py`, `test_commands.py`,
`test_imaging.py`, `test_integration_runtime.py`, `test_mcp_contract.py`,
`test_mcp_stdio_client.py`, `test_package_exports.py`, `test_serialization.py`,
`test_tools_core.py`, and `wheel_smoke.py`.

## Runtime constraints

- Fiji is the source of truth for active images, ROIs, and Results. The server
  does not hold workflow or session state.
- Fiji calls are synchronous and serialized. Read-only calls have at most one
  explicitly allowlisted retry; dispatched mutations are not retried. For an
  unknown mutation outcome, inspect state or a saved screenshot before deciding
  whether to repeat it.
- `run_script` is trusted arbitrary local IJM/Groovy execution. It can access
  local files available to the process. Ordinary Java output is redirected to
  stderr, but deliberate native file-descriptor-1 writes can bypass that
  redirection.
- The server can discover registered commands and access installed scriptable
  plugins. It does not install plugins or automate GUI input. GUI-only plugins
  may require a scriptable route or `FIJI_MODE=gui`.
- Save before/after captures with `screenshot` and pass their paths to
  `compare_screenshots`; use paginated `get_results` for complete Results data.
