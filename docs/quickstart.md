# Quick start

## Requirements

- **Python** 3.10+ (venv or conda)
- [**Fiji**](https://fiji.sc/) installed locally — directory that contains `jars/` and `plugins/`
- **Java** compatible with your Fiji build
- **Display** only for `FIJI_MODE=gui` and full-screen Robot capture. **Headless** MCP still supports `active_image` and `results_table` screenshots.

## Install from source

```bash
git clone https://github.com/surajinacademia/Fiji_imageJ_mcp.git
cd Fiji_imageJ_mcp
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[test]"
```

For the same **dev tooling** as [cellpose_mcp](https://github.com/surajinacademia/cellpose_mcp) (Ruff, Black, Mypy, pre-commit hooks): `pip install -e ".[dev]"` then `pre-commit install`.

## Point the server at Fiji

Set **`FIJI_PATH`** to the **installation root** (not only the nested `.app` path on macOS), for example `/Applications/Fiji` when that folder contains `jars/` and `plugins/`.

## Configure Cursor or Claude Desktop

Use the **same** Python where you installed the package:

```bash
fiji-mcp-install install cursor --fiji-path /Applications/Fiji
fiji-mcp-install install claude-desktop --fiji-path /Applications/Fiji
```

Defaults use **`FIJI_MODE=headless`** (recommended inside IDE MCP). Restart the app after writing config.

Details: [Configuration](configuration.md).

## Try a demo session

```bash
export FIJI_PATH=/Applications/Fiji
export FIJI_MODE=headless
python scripts/demo_fiji_mcp_session.py
```

This runs `health_check`, opens `demo_images/sample_gradient.pgm`, applies blur/stats macros, captures `active_image` / `results_table`, and optionally `full_screen` if a display exists.

## Batch analysis report (stdio MCP)

`scripts/generate_image_analysis_report.py` spawns the **same** stdio MCP server your IDE uses and writes:

- `research_output/analysis_raw.json`
- `docs/fiji_mcp_comprehensive_image_analysis_report.md`

```bash
export FIJI_PATH=/Applications/Fiji
export FIJI_MODE=headless
export FIJI_MCP_PYTHON=/path/to/conda-or-venv/bin/python   # if the driver lacks pyimagej
python scripts/generate_image_analysis_report.py
```

**Stdio safety:** do not use ImageJ `print()` in macros under stdio transport (stdout must stay JSON-clean). Prefer returning strings from macros or tool-level handling.

## Development and tests

```bash
pip install -e ".[test]"
pytest
```

CI runs `pytest -m "not integration"`. For integration tests, set **`FIJI_PATH`** and **`FIJI_TEST_IMAGE`**, then run pytest without that marker.

Roadmap: [`plan.md`](https://github.com/surajinacademia/Fiji_imageJ_mcp/blob/main/plan.md).
