# Fiji MCP Server

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: BSD-3-Clause](https://img.shields.io/badge/License-BSD--3--Clause-blue.svg)](https://opensource.org/licenses/BSD-3-Clause)
[![CI](https://github.com/surajinacademia/Fiji_imageJ_mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/surajinacademia/Fiji_imageJ_mcp/actions/workflows/ci.yml)

**Fiji MCP** is a [Model Context Protocol](https://modelcontextprotocol.io/) server that lets AI assistants drive **Fiji / ImageJ** through natural language: run macros, search commands, open and save images, capture verification screenshots, and chain multi-step workflows. It is built with **PyImageJ**, **FastMCP**, and stdio MCP so the same server works from **Cursor**, **Claude Desktop**, **Claude Code**, **Gemini CLI**, **Windsurf**, and other MCP-capable hosts.

<p align="center">
  <table>
    <tr>
      <td align="center" width="50%">
        <a href="https://raw.githubusercontent.com/surajinacademia/Fiji_imageJ_mcp/main/demo_output/readme_ex01_img07_input.jpg">
          <img src="https://raw.githubusercontent.com/surajinacademia/Fiji_imageJ_mcp/main/demo_output/readme_ex01_img07_input.jpg" alt="Bundled demo image opened in Fiji" width="100%" />
        </a>
        <p align="center"><em>Input — sample from <code>demo_images/</code>, opened via MCP</em></p>
      </td>
      <td align="center" width="50%">
        <a href="https://raw.githubusercontent.com/surajinacademia/Fiji_imageJ_mcp/main/demo_output/readme_ex01_img07_analysis.jpg">
          <img src="https://raw.githubusercontent.com/surajinacademia/Fiji_imageJ_mcp/main/demo_output/readme_ex01_img07_analysis.jpg" alt="Same field after Fiji macro pipeline" width="100%" />
        </a>
        <p align="center"><em>After analysis — blur / stats / overlay pipeline (see <code>scripts/generate_readme_demo_assets.py</code>)</em></p>
      </td>
    </tr>
  </table>
</p>

> **📌 Note:** This project follows the same MCP installer pattern as [napari-mcp](https://napari-hub.org/plugins/napari-mcp.html). Sibling project: [**cellpose_mcp**](https://github.com/surajinacademia/cellpose_mcp) (Cellpose + Napari MCP). To contribute or collaborate, contact **[ssahu2@ucmerced.edu](mailto:ssahu2@ucmerced.edu)**.

### 🚀 Quick Start

**Requirements:** Python **3.10+**, a local [**Fiji**](https://fiji.sc/) install (folder with `jars/` and `plugins/`), and a **Java** runtime compatible with that Fiji build.

**Install from source (recommended for development):**

```bash
git clone https://github.com/surajinacademia/Fiji_imageJ_mcp.git
cd Fiji_imageJ_mcp
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[test]"
```

**Configure Cursor in one go** (uses the same Python you just installed; set your real Fiji root):

```bash
fiji-mcp-install install cursor --fiji-path /Applications/Fiji
```

Restart **Cursor** (or whichever client you configured) after the installer runs.

**Regenerate README hero images** (optional; requires `FIJI_PATH` and a Python env with PyImageJ):

```bash
export FIJI_PATH=/Applications/Fiji
export FIJI_MODE=headless
python scripts/generate_readme_demo_assets.py
```

### Auto-Configure Your AI Application

After `pip install -e ".[test]"` (or a future PyPI install), run **`fiji-mcp-install install <target> --fiji-path <ABS>`**. It merges a `fiji` entry into the correct MCP JSON using **`python -m fiji_mcp`** from the interpreter next to `fiji-mcp-server` (when possible).

| Application | Command | Notes |
| ----------- | ------- | ----- |
| **Cursor** | `fiji-mcp-install install cursor --fiji-path <ABS>` | Writes `~/.cursor/mcp.json` |
| **Claude Desktop** | `fiji-mcp-install install claude-desktop --fiji-path <ABS>` | Claude Desktop `mcpServers` |
| **Claude Code** (user) | `fiji-mcp-install install claude-code --fiji-path <ABS>` | Merges into `~/.claude.json` |
| **Claude Code** (project) | `fiji-mcp-install install claude-code --fiji-path <ABS> --project <DIR>` | Creates or updates `<DIR>/.mcp.json` |
| **Gemini CLI** | `fiji-mcp-install install gemini --fiji-path <ABS>` | Merges into `~/.gemini/settings.json` |
| **Windsurf** | `fiji-mcp-install install windsurf --fiji-path <ABS>` | `~/.codeium/windsurf/mcp_config.json` |

**Options:** `--mode gui|headless|auto|smart` (default **`headless`** for IDE/CLI stability); `--command /path/to/fiji-mcp-server` if the host app does not see your venv on `PATH`.

<details>
<summary><strong>Manual configuration</strong> (any MCP host)</summary>

Use the Python that has `fiji-mcp-server` / `fiji_mcp` installed:

```json
{
  "mcpServers": {
    "fiji": {
      "command": "/path/to/venv-or-conda/bin/python",
      "args": ["-m", "fiji_mcp"],
      "env": {
        "FIJI_PATH": "/Applications/Fiji",
        "FIJI_MODE": "headless",
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

For **Cursor**, use the same object in `~/.cursor/mcp.json` or project `.cursor/mcp.json`. Under **stdio**, do not use ImageJ `print()` in macros (stdout must stay JSON-clean).

</details>

After installation, restart your AI app and try asking:

```text
"Run health_check, then open ./demo_images/sample_gradient.pgm in Fiji"
"Search ImageJ commands matching 'Gaussian blur'"
"Take an active_image screenshot after running Measure"
```

## 🎯 What Can You Do?

### Example: Fiji / ImageJ in action

<table>
<tr>
<td width="50%">
<a href="https://raw.githubusercontent.com/surajinacademia/Fiji_imageJ_mcp/main/demo_output/readme_ex01_img07_input.jpg">
<img src="https://raw.githubusercontent.com/surajinacademia/Fiji_imageJ_mcp/main/demo_output/readme_ex01_img07_input.jpg" alt="Demo input" />
</a>
<p align="center"><em>Demo input from bundled <code>demo_images/</code></em></p>
</td>
<td width="50%">
<a href="https://raw.githubusercontent.com/surajinacademia/Fiji_imageJ_mcp/main/demo_output/readme_ex01_img07_analysis.jpg">
<img src="https://raw.githubusercontent.com/surajinacademia/Fiji_imageJ_mcp/main/demo_output/readme_ex01_img07_analysis.jpg" alt="Demo analysis" />
</a>
<p align="center"><em>Same session after macro-driven processing</em></p>
</td>
</tr>
</table>

### Basic macros and I/O

```text
"Open ./demo_images/sample_gradient.pgm and report width and height"
"Run a macro that applies Gaussian blur then runs Measure"
"Save the active image to ./out/result.tif"
```

### Discovery and screenshots

```text
"List extensions loaded in this Fiji session"
"Search commands matching 'FFT'"
"Capture results_table after Measure on the current image"
```

### Batch and reporting

```text
"Run generate_image_analysis_report-style steps on all PNGs under ./demo_images/"
```

Use **`scripts/generate_image_analysis_report.py`** for a full stdio-MCP batch report (`research_output/` + `docs/` markdown). See [**Batch report workflow**](docs/batch_report_workflow.md).

## 🛠 Available MCP Tools

The server exposes **19** tools for Fiji/ImageJ automation:

### Macros and images

- **`health_check`** — Verify Fiji / PyImageJ readiness  
- **`run_macro`** — Execute ImageJ macro text (with retries)  
- **`run_batch_macros`** — Run several macros with optional MCP progress  
- **`open_image`** / **`save_image`** — Path-aware I/O with optional `FIJI_DATA_ROOTS` allowlist  

### Screenshots

- **`screenshot_fiji`** — `full_screen`, `active_image`, or `results_table`  

### Discovery

- **`list_all_commands`** / **`search_commands`** / **`describe_plugin`**  
- **`list_extensions`** / **`list_open_images`** / **`get_image_info`**  

### Workflows and session helpers

- **`run_workflow`** — Async multi-step pipelines  
- **`parse_macro_output`**, **`compare_screenshots`**, **`list_macro_templates`**, **`get_macro_template`**  
- **`get_session_trace`** / **`clear_session_trace`**  

## 📖 Documentation

| Resource | Description |
| -------- | ----------- |
| [**Quick Start**](docs/quickstart.md) | Install, `FIJI_PATH`, all installer targets, demos, tests |
| [**MCP Tools**](docs/tools.md) | Full tool tables and parameters |
| [**Configuration**](docs/configuration.md) | Env vars, troubleshooting, Cursor plugin |
| [**Architecture**](docs/architecture.md) | Package layout and data flow |
| [**Batch report**](docs/batch_report_workflow.md) | Stdio MCP batch report script |

**Local doc site:** `npx docsify serve docs` then open the URL shown (same Docsify pattern as [cellpose_mcp/docs](https://github.com/surajinacademia/cellpose_mcp/tree/main/docs)).

**Changelog & releases:** [**CHANGELOG.md**](CHANGELOG.md) · [**RELEASE_NOTES_v0.1.0.md**](RELEASE_NOTES_v0.1.0.md) · [**CLAUDE.md**](CLAUDE.md) (Claude Code) · **Pre-commit:** `.pre-commit-config.yaml` (`pip install -e ".[dev]" && pre-commit install`)

## 📋 Architecture

- **FastMCP** — stdio JSON-RPC to your AI client  
- **PyImageJ / JPype** — JVM bridge into Fiji/ImageJ2  
- **Tool modules** — `macro_runner`, `discovery`, `screenshot`, `workflow`, `structured_tools`  
- **Design** — Headless-first for MCP; optional GUI + Robot for `full_screen`; stdio-safe macros (no `print()` to stdout)  

**Project status:** Phases 1–4 complete; phase 5 (integration polish) in progress — see [**plan.md**](plan.md). CI: `pytest -m "not integration"` on Python 3.10–3.12.

---

**Author:** Suraj Sahu  
**Affiliation:** Department of Physics, University of California Merced, CA, USA  
**Email:** [ssahu2@ucmerced.edu](mailto:ssahu2@ucmerced.edu)

## 📄 License

BSD-3-Clause — see [**LICENSE**](LICENSE).

## 🙏 Acknowledgments

- [**Napari MCP**](https://github.com/royerlab/napari-mcp) (royerlab) — installer and MCP patterns  
- [**ImageJ2**](https://imagej.net/software/imagej2) / [**PyImageJ**](https://pyimagej.readthedocs.io/)  
- [**FastMCP**](https://github.com/jlowin/fastmcp)  
- [**Anthropic**](https://www.anthropic.com/) and the [**Model Context Protocol**](https://modelcontextprotocol.io/)  

---
