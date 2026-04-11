# Fiji MCP Server

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: BSD-3-Clause](https://img.shields.io/badge/License-BSD--3--Clause-blue.svg)](https://github.com/surajinacademia/Fiji_imageJ_mcp/blob/main/LICENSE)
[![CI](https://github.com/surajinacademia/Fiji_imageJ_mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/surajinacademia/Fiji_imageJ_mcp/actions/workflows/ci.yml)

**Fiji MCP** is a [Model Context Protocol](https://modelcontextprotocol.io/) server for **Fiji / ImageJ**: macros, command discovery, I/O, screenshots, and workflows via **PyImageJ** and **FastMCP**. Works with **Cursor**, **Claude Desktop**, **Claude Code**, **Gemini CLI**, **Windsurf**, and other MCP clients.

<p align="center"><b>Three Fiji examples on <code>demo_images/</code></b> — see <code>scripts/generate_readme_demo_assets.py</code></p>

<table>
<tr><th colspan="2" align="center">Example 1 — <code>img07.png</code> → Gaussian blur (σ = 4)</th></tr>
<tr>
<td width="50%">
<a href="https://raw.githubusercontent.com/surajinacademia/Fiji_imageJ_mcp/main/demo_output/readme_ex01_img07_input.jpg">
<img src="https://raw.githubusercontent.com/surajinacademia/Fiji_imageJ_mcp/main/demo_output/readme_ex01_img07_input.jpg" alt="Example 1 input" width="100%" />
</a>
<p align="center"><em>Input</em></p>
</td>
<td width="50%">
<a href="https://raw.githubusercontent.com/surajinacademia/Fiji_imageJ_mcp/main/demo_output/readme_ex01_img07_analysis.jpg">
<img src="https://raw.githubusercontent.com/surajinacademia/Fiji_imageJ_mcp/main/demo_output/readme_ex01_img07_analysis.jpg" alt="Example 1 blurred" width="100%" />
</a>
<p align="center"><em>After Gaussian blur</em></p>
</td>
</tr>
<tr><th colspan="2" align="center">Example 2 — <code>img04.png</code> → Find Edges</th></tr>
<tr>
<td width="50%">
<a href="https://raw.githubusercontent.com/surajinacademia/Fiji_imageJ_mcp/main/demo_output/readme_ex02_img04_input.jpg">
<img src="https://raw.githubusercontent.com/surajinacademia/Fiji_imageJ_mcp/main/demo_output/readme_ex02_img04_input.jpg" alt="Example 2 input" width="100%" />
</a>
<p align="center"><em>Input</em></p>
</td>
<td width="50%">
<a href="https://raw.githubusercontent.com/surajinacademia/Fiji_imageJ_mcp/main/demo_output/readme_ex02_img04_analysis.jpg">
<img src="https://raw.githubusercontent.com/surajinacademia/Fiji_imageJ_mcp/main/demo_output/readme_ex02_img04_analysis.jpg" alt="Example 2 edges" width="100%" />
</a>
<p align="center"><em>After Find Edges</em></p>
</td>
</tr>
<tr><th colspan="2" align="center">Example 3 — <code>img10.png</code> → threshold + particle count / morphology</th></tr>
<tr>
<td width="50%">
<a href="https://raw.githubusercontent.com/surajinacademia/Fiji_imageJ_mcp/main/demo_output/readme_ex03_img10_input.jpg">
<img src="https://raw.githubusercontent.com/surajinacademia/Fiji_imageJ_mcp/main/demo_output/readme_ex03_img10_input.jpg" alt="Example 3 input" width="100%" />
</a>
<p align="center"><em>Input</em></p>
</td>
<td width="50%">
<a href="https://raw.githubusercontent.com/surajinacademia/Fiji_imageJ_mcp/main/demo_output/readme_ex03_img10_overlay.jpg">
<img src="https://raw.githubusercontent.com/surajinacademia/Fiji_imageJ_mcp/main/demo_output/readme_ex03_img10_overlay.jpg" alt="Particle overlay" width="100%" />
</a>
<p align="center"><em>Overlay outlines</em></p>
</td>
</tr>
<tr>
<td colspan="2" align="center">
<a href="https://raw.githubusercontent.com/surajinacademia/Fiji_imageJ_mcp/main/demo_output/readme_ex03_img10_results.jpg">
<img src="https://raw.githubusercontent.com/surajinacademia/Fiji_imageJ_mcp/main/demo_output/readme_ex03_img10_results.jpg" alt="Measurements table" width="95%" />
</a>
<p align="center"><em>Per-object measurements (Area, Mean, StdDev, Perimeter, Circ., Feret)</em></p>
</td>
</tr>
</table>

> **📌 Note:** Same MCP patterns as [napari-mcp](https://napari-hub.org/plugins/napari-mcp.html). Sibling: [**cellpose_mcp**](https://github.com/surajinacademia/cellpose_mcp). Contact: [ssahu2@ucmerced.edu](mailto:ssahu2@ucmerced.edu).

---

## Browse the docs

- **[Install & quick start](quickstart.md)** — clone, venv, `pip install`, auto vs manual MCP config, verify  
- **[MCP Tools](tools.md)** — all **19** tools  
- **[Configuration](configuration.md)** — env vars, manual JSON, troubleshooting  
- **[Architecture](architecture.md)** — layout and data flow  
- **[Batch report workflow](batch_report_workflow.md)** — stdio batch report  

**GitHub README:** [surajinacademia/Fiji_imageJ_mcp](https://github.com/surajinacademia/Fiji_imageJ_mcp) · **Roadmap:** [plan.md](https://github.com/surajinacademia/Fiji_imageJ_mcp/blob/main/plan.md)

---

## License

BSD-3-Clause — see [LICENSE](https://github.com/surajinacademia/Fiji_imageJ_mcp/blob/main/LICENSE).
