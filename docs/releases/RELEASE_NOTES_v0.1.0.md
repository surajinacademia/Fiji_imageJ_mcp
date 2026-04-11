# Fiji MCP v0.1.0 — initial packaging release

First coordinated **documentation + packaging** release for **fiji-mcp-server**: public repo layout aligned with [cellpose_mcp](https://github.com/surajinacademia/cellpose_mcp) (Docsify `docs/`, `LICENSE`, `CHANGELOG`, installer metadata, optional dev tooling).

## Highlights

- **19 MCP tools** for Fiji/ImageJ: macros, batch macros, open/save, screenshots (`full_screen`, `active_image`, `results_table`), command discovery, async workflows, macro templates, session trace helpers.
- **`fiji-mcp-install`** for **Cursor** and **Claude Desktop** with `FIJI_PATH` / `FIJI_MODE` / optional `--command`.
- **Docs** (`docs/index.html`, sidebar, quickstart, tools, configuration, architecture) plus optional **batch report** workflow doc.
- **BSD-3-Clause** `LICENSE`, **Keep a Changelog** `CHANGELOG.md`, **`MANIFEST.in`**, example **`.mcp.json`**, **`.python-version`**.

## Install (from source)

```bash
git clone https://github.com/surajinacademia/Fiji_imageJ_mcp.git
cd Fiji_imageJ_mcp
pip install -e ".[test]"
```

Configure MCP (same Python env as `pip install`):

```bash
fiji-mcp-install install cursor --fiji-path /path/to/Fiji
```

## Requirements

- Python **3.10+**
- Local **Fiji** install and compatible **Java**
- For full-screen Robot capture: desktop / `FIJI_MODE=gui`; for typical IDE MCP, prefer **`headless`**.

## Links

- Repository: https://github.com/surajinacademia/Fiji_imageJ_mcp  
- Documentation tree: https://github.com/surajinacademia/Fiji_imageJ_mcp/tree/main/docs  
- Issues: https://github.com/surajinacademia/Fiji_imageJ_mcp/issues  
