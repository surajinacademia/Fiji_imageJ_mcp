# Batch image analysis report

This workflow matches the idea of a **long-running, reproducible pipeline** doc (similar to [Cellpose MCP training with annotations](https://github.com/surajinacademia/cellpose_mcp/blob/main/docs/training_with_annotations.md) in scope: one dedicated guide for an advanced path).

## What it does

[`scripts/generate_image_analysis_report.py`](https://github.com/surajinacademia/Fiji_imageJ_mcp/blob/main/scripts/generate_image_analysis_report.py) **spawns the Fiji MCP server over stdio** and drives it with an MCP client (`fastmcp` `Client` + `StdioTransport`). It does **not** import Fiji tool modules in-process, so behavior matches Cursor or Claude calling the same server.

Outputs (defaults):

- `research_output/analysis_raw.json` — structured tool results
- `docs/fiji_mcp_comprehensive_image_analysis_report.md` — human-readable report (may be overwritten on each run)

## Prerequisites

- `FIJI_PATH` set to your Fiji root
- `FIJI_MODE=headless` recommended for unattended runs
- A Python environment with **`fiji-mcp-server`** / `pyimagej` / `scyjava` installed (the subprocess that runs `-m fiji_mcp`)

If the **driver** Python (the one executing the script) is minimal, set:

```bash
export FIJI_MCP_PYTHON=/path/to/conda-or-venv/bin/python
```

so the script spawns MCP with an interpreter that can start ImageJ.

## Run

```bash
export FIJI_PATH=/Applications/Fiji
export FIJI_MODE=headless
python scripts/generate_image_analysis_report.py
```

## Stdio safety

Macros executed through stdio MCP must **not** use ImageJ `print()` (stdout corruption). Prefer returning strings from macros or handling output in tool responses only.

## See also

- [Quick Start](quickstart.md) — shorter demo via `scripts/demo_fiji_mcp_session.py`
- [Configuration](configuration.md) — env vars including `FIJI_MCP_PYTHON`
