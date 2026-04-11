# Fiji MCP Server

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: BSD-3-Clause](https://img.shields.io/badge/License-BSD--3--Clause-blue.svg)](https://github.com/surajinacademia/Fiji_imageJ_mcp/blob/main/LICENSE)
[![CI](https://github.com/surajinacademia/Fiji_imageJ_mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/surajinacademia/Fiji_imageJ_mcp/actions/workflows/ci.yml)

**Fiji MCP** is a [Model Context Protocol](https://modelcontextprotocol.io/) server that lets AI assistants drive **Fiji / ImageJ** through natural language: run macros, discover commands, open and save images, capture verification screenshots, and chain multi-step workflows—powered by **PyImageJ** and **FastMCP**.

<p align="center">
  <table>
    <tr>
      <td align="center" width="50%">
        <a href="https://raw.githubusercontent.com/surajinacademia/cellpose_mcp/main/poster/poster_images/img00.png">
          <img src="https://raw.githubusercontent.com/surajinacademia/cellpose_mcp/main/poster/poster_images/img00.png" alt="Fluorescence microscopy: cytoplasm and nuclei" width="100%" />
        </a>
        <sub><b>Widefield fluorescence</b> — cytoplasm (green) and nuclei (blue); typical input you can open with <code>open_image</code> and process in Fiji</sub>
      </td>
      <td align="center" width="50%">
        <a href="https://raw.githubusercontent.com/surajinacademia/cellpose_mcp/main/poster/poster_images/img00_annotated_overlay.png">
          <img src="https://raw.githubusercontent.com/surajinacademia/cellpose_mcp/main/poster/poster_images/img00_annotated_overlay.png" alt="Same field with segmentation-style overlays" width="100%" />
        </a>
        <sub><b>Analysis overlay</b> — boundaries and labels; Fiji MCP can drive the macros, measurements, and <code>screenshot_fiji</code> steps behind similar workflows</sub>
      </td>
    </tr>
  </table>
</p>

<p align="center"><sub>Hero frames are from the <a href="https://github.com/surajinacademia/cellpose_mcp">cellpose_mcp</a> poster assets (same author) to show realistic microscopy; <strong>Fiji MCP</strong> targets ImageJ/Fiji automation on <em>your</em> paths and plugins.</sub></p>

> **Note:** Same MCP-install pattern as [napari-mcp](https://napari-hub.org/plugins/napari-mcp.html). Sibling project: [**cellpose_mcp**](https://github.com/surajinacademia/cellpose_mcp). Contributions welcome — **ssahu2@ucmerced.edu**.

---

## Documentation

| Guide | Description |
|-------|-------------|
| [**Quick Start**](docs/quickstart.md) | Install, `FIJI_PATH`, `fiji-mcp-install`, demos, batch report, tests |
| [**MCP Tools**](docs/tools.md) | All **19** tools (macros, screenshots, discovery, workflows) |
| [**Configuration**](docs/configuration.md) | Env vars, manual JSON, troubleshooting, optional Cursor plugin |
| [**Architecture**](docs/architecture.md) | Data flow, package layout, design notes |
| [**Batch report**](docs/batch_report_workflow.md) | `generate_image_analysis_report.py` over stdio MCP |

**Browse locally:** open [`docs/index.html`](docs/index.html) with [Docsify](https://docsify.js.org/) (`npx docsify serve docs`) for a searchable sidebar site—the same layout as [cellpose_mcp/docs](https://github.com/surajinacademia/cellpose_mcp/tree/main/docs).

---

## Project status

| Phase | Scope | Status |
|-------|--------|--------|
| 1 | PyImageJ bridge, macros, screenshots, config | Done |
| 2 | Command/extension discovery and search | Done |
| 3 | Workflows and batch macros | Done |
| 4 | Screenshot limits/cache, smart/headless modes, timeouts | Done |
| 5 | Integration tests with real Fiji, benchmarks, release polish | In progress |

CI: `pytest -m "not integration"` on Python 3.10–3.12. Roadmap: [`plan.md`](plan.md).

---

## Quick install

```bash
git clone https://github.com/surajinacademia/Fiji_imageJ_mcp.git
cd Fiji_imageJ_mcp
python -m venv .venv && source .venv/bin/activate
pip install -e ".[test]"
fiji-mcp-install install cursor --fiji-path /Applications/Fiji
```

Restart Cursor after configuring. Full steps and Claude Desktop: [**Quick Start**](docs/quickstart.md).

---

## Changelog and releases

- [**CHANGELOG.md**](CHANGELOG.md) — version history (Keep a Changelog)
- [**RELEASE_NOTES_v0.1.0.md**](RELEASE_NOTES_v0.1.0.md) — first packaging-aligned release notes

Developer onboarding for Claude Code: [**CLAUDE.md**](CLAUDE.md). Optional [**pre-commit**](https://pre-commit.com/) config: `.pre-commit-config.yaml` (`pip install -e ".[dev]" && pre-commit install`).

---

## Author

**Suraj Sahu** — Department of Physics, University of California Merced, USA · **ssahu2@ucmerced.edu**

---

## Acknowledgments

- [**ImageJ2**](https://imagej.net/software/imagej2) / [**PyImageJ**](https://pyimagej.readthedocs.io/)
- [**napari-mcp**](https://napari-hub.org/plugins/napari-mcp.html) (royerlab)
- [**FastMCP**](https://github.com/jlowin/fastmcp)
- [**Model Context Protocol**](https://modelcontextprotocol.io/)

---

## License

**BSD-3-Clause** — see [**LICENSE**](LICENSE).
