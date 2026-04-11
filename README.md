# Fiji MCP Server

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![PyPI](https://img.shields.io/pypi/v/fiji-mcp-server.svg)](https://pypi.org/project/fiji-mcp-server/)
[![License: BSD-3-Clause](https://img.shields.io/badge/License-BSD--3--Clause-blue.svg)](https://opensource.org/licenses/BSD-3-Clause)
[![CI](https://github.com/surajinacademia/Fiji_imageJ_mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/surajinacademia/Fiji_imageJ_mcp/actions/workflows/ci.yml)

**Talk to Fiji / ImageJ in plain English from Cursor, Claude, Gemini, Windsurf, and more.**

Open images, run any ImageJ plugin, count cells, measure features, take screenshots to verify — without writing a single line of macro code yourself.

<!-- Demo images: absolute raw.githubusercontent.com URLs + Markdown tables (PyPI does not host ./demo_output; raw HTML <img> is less reliable in Warehouse). -->

---

## See it in action

**"Open the image, apply a Gaussian blur, show me before and after."**

| Before | After |
| :---: | :---: |
| ![Gaussian blur — input](https://raw.githubusercontent.com/surajinacademia/Fiji_imageJ_mcp/main/demo_output/readme_ex01_img07_input.jpg) | ![Gaussian blur — output](https://raw.githubusercontent.com/surajinacademia/Fiji_imageJ_mcp/main/demo_output/readme_ex01_img07_processed.jpg) |

**"Threshold the bright spots, outline each object, report area and circularity."**

| Input | Outlined objects |
| :---: | :---: |
| ![Particles — input](https://raw.githubusercontent.com/surajinacademia/Fiji_imageJ_mcp/main/demo_output/readme_ex02_img10_input.jpg) | ![Particles — outlines](https://raw.githubusercontent.com/surajinacademia/Fiji_imageJ_mcp/main/demo_output/readme_ex02_img10_overlay.jpg) |

| # | Area | Circularity |
| ---: | ---: | ---: |
| 1 | 1052 | 0.89 |
| 2 | 2840 | 0.72 |
| 3 | 641 | 0.91 |
| 4 | 1902 | 0.68 |

**"Skeletonize the mask and summarize branches per tree."**

| Mask | Skeleton |
| :---: | :---: |
| ![Skeleton — input mask](https://raw.githubusercontent.com/surajinacademia/Fiji_imageJ_mcp/main/demo_output/readme_ex03_img12_input.jpg) | ![Skeleton — midlines](https://raw.githubusercontent.com/surajinacademia/Fiji_imageJ_mcp/main/demo_output/readme_ex03_img12_skeleton.jpg) |

| Tree | Branches | Junctions |
| ---: | ---: | ---: |
| 1 | 14 | 6 |
| 2 | 9 | 7 |

---

## Get started in 3 steps

### 1 — Install

```bash
pip install fiji-mcp-server
```

> You need **Python 3.10+**, **[Fiji](https://fiji.sc/)** installed on your machine, and **Java** (required by PyImageJ). See [quickstart](docs/quickstart.md) if anything needs clarification.

### 2 — Connect to your AI app

Replace `/Applications/Fiji` with your actual Fiji folder (the one containing `jars/` and `plugins/`).

| App | One command |
|-----|-------------|
| **Claude Desktop** | `fiji-mcp-install install claude-desktop --fiji-path /Applications/Fiji` |
| **Cursor** | `fiji-mcp-install install cursor --fiji-path /Applications/Fiji` |
| **Claude Code** | `fiji-mcp-install install claude-code --fiji-path /Applications/Fiji` |
| **Gemini CLI** | `fiji-mcp-install install gemini --fiji-path /Applications/Fiji` |
| **Windsurf** | `fiji-mcp-install install windsurf --fiji-path /Applications/Fiji` |

Then **restart** the app.

### 3 — Verify it works

In chat, type:

```
Run the Fiji MCP health_check tool
```

You should get back the Fiji version and mode. First startup takes 30–90 seconds while the JVM loads — that's normal.

---

## What to ask

Once connected, just describe what you want:

```
"Open ./images/cells.tif and tell me the dimensions."

"Apply a Gaussian blur with sigma 4 and show me the result."

"Count the bright objects and give me their areas."

"Search for ImageJ commands related to 'threshold'."

"Open the image, subtract background, threshold, count particles — show me a screenshot after each step."
```

No macro knowledge needed. The assistant finds the right Fiji plugin, runs it, and can show you a screenshot to verify.

---

## Available tools (19 total)

| Category | Tools |
|----------|-------|
| **Run & I/O** | `health_check` `run_macro` `run_batch_macros` `open_image` `save_image` |
| **Screenshots** | `screenshot_fiji` — full screen, active image, or results table |
| **Discover plugins** | `list_all_commands` `search_commands` `describe_plugin` `list_extensions` |
| **Image info** | `list_open_images` `get_image_info` |
| **Workflows** | `run_workflow` — chain steps with screenshot verification |
| **Results** | `parse_macro_output` `compare_screenshots` `list_macro_templates` `get_macro_template` |
| **Session** | `get_session_trace` `clear_session_trace` |

---

## Documentation

| | |
|-|-|
| [**Quick start**](docs/quickstart.md) | Install, configure, verify — step by step |
| [**All tools**](docs/tools.md) | What every tool does and when to use it |
| [**Configuration**](docs/configuration.md) | Environment variables and troubleshooting |
| [**Architecture**](docs/architecture.md) | How the pieces fit together |

---

**Author:** Suraj Sahu · UC Merced Physics · [ssahu2@ucmerced.edu](mailto:ssahu2@ucmerced.edu)

**Related:** [cellpose_mcp](https://github.com/surajinacademia/cellpose_mcp) · [PyImageJ](https://pyimagej.readthedocs.io/) · [FastMCP](https://github.com/jlowin/fastmcp)

**License:** BSD-3-Clause
