# Install and quick start

Three steps: **install the Python package** → **tell the MCP client where Fiji lives** → **confirm it works**.

---

## 1. Prerequisites

| You need | Notes |
| -------- | ----- |
| **Python 3.10+** | Use a venv or conda env dedicated to this project. |
| **Fiji** | [fiji.sc](https://fiji.sc/) — the folder you pass later must contain **`jars/`** and **`plugins/`** (installation root, not only a nested `.app` bundle path on macOS). |
| **Java** | Same major line your Fiji build expects. |

For normal IDE / CLI use, **`FIJI_MODE=headless`** is enough (no desktop required for `active_image` / `results_table` screenshots). Use **`gui`** only if you need full-screen Robot capture.

---

## 2. Install (from source)

**Method:** clone the repo, create a venv, install in editable mode.

```bash
git clone https://github.com/surajinacademia/Fiji_imageJ_mcp.git
cd Fiji_imageJ_mcp
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -U pip setuptools wheel
pip install -e ".[test]"
```

Check that the CLI is on your PATH (same shell as above):

```bash
fiji-mcp-install --help
python -m fiji_mcp --help
```

*(There is no PyPI one-liner yet; installs are from this repository.)*

---

## 3. Configure your MCP client

**Method A — auto-install (recommended)**  
Run **`fiji-mcp-install`** with the **absolute** Fiji root and your **target** app. Use the **same** venv you used for `pip install` (so `python` there has `pyimagej` / `fiji_mcp`).

Replace `/Applications/Fiji` with your real path.

```bash
# Pick one:
fiji-mcp-install install cursor --fiji-path /Applications/Fiji
fiji-mcp-install install claude-desktop --fiji-path /Applications/Fiji
fiji-mcp-install install claude-code --fiji-path /Applications/Fiji
fiji-mcp-install install gemini --fiji-path /Applications/Fiji
fiji-mcp-install install windsurf --fiji-path /Applications/Fiji

# Optional: Claude Code project file instead of ~/.claude.json
fiji-mcp-install install claude-code --fiji-path /Applications/Fiji --project /path/to/your/repo
```

Defaults: **`FIJI_MODE=headless`**, **`PYTHONUNBUFFERED=1`**.  
Optional: `--mode gui`, or `--command /full/path/to/venv/bin/fiji-mcp-server` if the GUI app cannot see your venv.

**Then restart** Cursor, Claude, Windsurf, or the Gemini CLI so it reloads MCP config.

**Method B — paste JSON yourself**  
Same shape everywhere: `mcpServers.fiji` with `command` + `args: ["-m", "fiji_mcp"]` + `env` (`FIJI_PATH`, `FIJI_MODE`, `PYTHONUNBUFFERED`). See [Configuration](configuration.md) for paths per app and a full example.

---

## 4. Quick verification

**In the AI chat** (after restart), try:

```text
Call the Fiji MCP health_check tool
```

**From the terminal** (optional smoke script; needs `FIJI_PATH`):

```bash
export FIJI_PATH=/Applications/Fiji
export FIJI_MODE=headless
python scripts/demo_fiji_mcp_session.py
```

First JVM start can take **30–90 seconds**; later calls are usually fast.

---

## 5. What to read next

| Topic | Doc |
| ----- | --- |
| All env vars, troubleshooting, Cursor plugin | [Configuration](configuration.md) |
| Every MCP tool | [MCP Tools](tools.md) |
| Package layout | [Architecture](architecture.md) |
| Batch report over stdio MCP | [Batch report workflow](batch_report_workflow.md) |
| Roadmap / internals | [plan.md](https://github.com/surajinacademia/Fiji_imageJ_mcp/blob/main/plan.md) |

**Developers:** `pip install -e ".[dev]"` and `pre-commit install` for Ruff / format hooks (see repo `README.md`).

---

## Tests (optional)

```bash
pytest -m "not integration"
```

Integration tests need **`FIJI_PATH`** and **`FIJI_TEST_IMAGE`** set; see [Configuration](configuration.md).
