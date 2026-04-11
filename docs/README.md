# Fiji MCP Server

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: BSD-3-Clause](https://img.shields.io/badge/License-BSD--3--Clause-blue.svg)](https://github.com/surajinacademia/Fiji_imageJ_mcp/blob/main/LICENSE)
[![CI](https://github.com/surajinacademia/Fiji_imageJ_mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/surajinacademia/Fiji_imageJ_mcp/actions/workflows/ci.yml)

**Fiji MCP** is a [Model Context Protocol](https://modelcontextprotocol.io/) server for **Fiji / ImageJ**: macros, command discovery, I/O, screenshots, and workflows via **PyImageJ** and **FastMCP**. Works with **Cursor**, **Claude Desktop**, **Claude Code**, **Gemini CLI**, **Windsurf**, and other MCP clients.

## Demos on this repo

Three small **pipelines** you can reproduce with `scripts/generate_readme_demo_assets.py` (JPEGs land in `demo_output/readme_ex*.jpg`):

1. **Soft blur** — before/after Gaussian filter.  
2. **Bright blobs** — threshold + particle outlines + a short **Area / circularity** markdown table on the [GitHub README](https://github.com/surajinacademia/Fiji_imageJ_mcp#see-it-running).  
3. **Skeleton summary** — mask → skeleton → branch-style markdown excerpt there.

**Full gallery + tables:** [GitHub README → *See it running*](https://github.com/surajinacademia/Fiji_imageJ_mcp#see-it-running).

Regenerate: `FIJI_PATH=… FIJI_MODE=headless python scripts/generate_readme_demo_assets.py`.

> **📌 Note:** Same MCP patterns as [napari-mcp](https://napari-hub.org/plugins/napari-mcp.html). Sibling: [**cellpose_mcp**](https://github.com/surajinacademia/cellpose_mcp). Contact: [ssahu2@ucmerced.edu](mailto:ssahu2@ucmerced.edu).

---

## Browse the docs

- **[Install & quick start](quickstart.md)** — clone, venv, `pip install`, auto vs manual MCP config, verify  
- **[MCP + GUI smoke](quickstart.md#mcp-and-gui-fiji)** — `scripts/mcp_and_gui_fiji.py` (stdio client + optional Fiji.app)  
- **[MCP Tools](tools.md)** — all **19** tools  
- **[Configuration](configuration.md)** — env vars, manual JSON, troubleshooting  
- **[Architecture](architecture.md)** — layout and data flow  
- **[Batch report workflow](batch_report_workflow.md)** — stdio batch report  

**GitHub README:** [surajinacademia/Fiji_imageJ_mcp](https://github.com/surajinacademia/Fiji_imageJ_mcp) · **Roadmap:** [plan.md](https://github.com/surajinacademia/Fiji_imageJ_mcp/blob/main/plan.md)

---

## License

BSD-3-Clause — see [LICENSE](https://github.com/surajinacademia/Fiji_imageJ_mcp/blob/main/LICENSE).
