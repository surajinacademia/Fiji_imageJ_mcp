# Fiji MCP Server

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: BSD-3-Clause](https://img.shields.io/badge/License-BSD--3--Clause-blue.svg)](https://github.com/surajinacademia/Fiji_imageJ_mcp/blob/main/LICENSE)
[![CI](https://github.com/surajinacademia/Fiji_imageJ_mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/surajinacademia/Fiji_imageJ_mcp/actions/workflows/ci.yml)

**Fiji MCP** is a [Model Context Protocol](https://modelcontextprotocol.io/) server that lets AI assistants drive **Fiji / ImageJ** through natural language: macros, command discovery, I/O, screenshots, and workflows—using **PyImageJ** and **FastMCP**.

<p align="center">
  <table>
    <tr>
      <td align="center" width="50%">
        <img src="https://raw.githubusercontent.com/surajinacademia/Fiji_imageJ_mcp/main/demo_output/active_image.jpg" alt="Active image" width="100%" />
        <sub><b>Active image</b> — <code>screenshot_fiji</code> (<code>active_image</code>)</sub>
      </td>
      <td align="center" width="50%">
        <img src="https://raw.githubusercontent.com/surajinacademia/Fiji_imageJ_mcp/main/demo_output/results_table.jpg" alt="Results table" width="100%" />
        <sub><b>Results table</b> — Measure/Results render</sub>
      </td>
    </tr>
  </table>
</p>

> **Note:** Same MCP-install pattern as [napari-mcp](https://napari-hub.org/plugins/napari-mcp.html). Sibling project: [**cellpose_mcp**](https://github.com/surajinacademia/cellpose_mcp). Contact: [ssahu2@ucmerced.edu](mailto:ssahu2@ucmerced.edu).

---

## Browse the docs

- **[Quick Start](quickstart.md)** — install, `FIJI_PATH`, first demo, batch report script, tests
- **[MCP Tools](tools.md)** — full tool catalog (19 tools)
- **[Configuration](configuration.md)** — `fiji-mcp-install`, manual JSON, env vars, troubleshooting, Cursor plugin
- **[Architecture](architecture.md)** — components, data flow, design notes

Repository README (GitHub landing): [github.com/surajinacademia/Fiji_imageJ_mcp](https://github.com/surajinacademia/Fiji_imageJ_mcp).

Implementation roadmap: [`plan.md`](https://github.com/surajinacademia/Fiji_imageJ_mcp/blob/main/plan.md) in the repo root.

---

## License

BSD-3-Clause — see [LICENSE](https://github.com/surajinacademia/Fiji_imageJ_mcp/blob/main/LICENSE).
