# Architecture

## Data flow

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

## Python package layout

Source lives under `src/fiji_mcp/`:

| Module / package | Role |
|------------------|------|
| `mcp_instance.py` | Shared FastMCP singleton |
| `server.py` | Imports tool modules (registers `@mcp.tool` handlers) |
| `fiji_bridge.py` | PyImageJ / JVM bridge |
| `tools/` | `macro_runner`, `screenshot`, `discovery`, `workflow`, `structured_tools` |
| `config/settings.py` | Env-based settings |
| `cli/install.py` | `fiji-mcp-install` |
| `schemas/` | Pydantic result types |
| `utils/` | Logging, paths, errors, optimizer |

Unlike [cellpose_mcp](https://github.com/surajinacademia/cellpose_mcp) (single large `tools.py`), Fiji splits tools by concern because the integration surface mixes macros, discovery, GUI capture, and workflows.

## Design principles

- **Universal plugin surface** — most Fiji behavior is reachable via macros plus command discovery.
- **Headless-first** — stable MCP without a desktop; GUI mode when Robot full-screen is required.
- **Stdio-safe macros** — avoid ImageJ `print()` on stdio MCP (corrupts JSON-RPC); use return values or stderr-side logging from Python.
- **Stateful sessions** — optional trace, batch macros, async workflows with progress when supported.

## Related documents

- Implementation phases and benchmarks: [`plan.md`](https://github.com/surajinacademia/Fiji_imageJ_mcp/blob/main/plan.md)
