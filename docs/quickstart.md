# Install and quick start

Three steps: **install Python + dependencies** → **point MCP at Fiji** → **confirm it works**.

---

## 1. Prerequisites

| You need | Notes |
| -------- | ----- |
| **Python 3.10+** | On your PATH as `python3` / `python`. |
| **Network** | `pip` downloads packages from PyPI (FastMCP, PyImageJ, NumPy, …). |
| **Fiji** | [fiji.sc](https://fiji.sc/) — later you pass the **installation root** (folder with `jars/` and `plugins/`). |
| **Java (JDK)** | Required when PyImageJ / **jpype1** first builds or runs against your Fiji. Install before or right after the Python install if `pip install` fails on `jpype1`. |

For IDE / CLI MCP, default **`FIJI_MODE=headless`** is enough (no desktop for `active_image` / `results_table` screenshots).

---

## 2. Install

### From PyPI (recommended for users)

```bash
pip install fiji-mcp-server
```

Continue to **§3** to configure Cursor / Claude / etc. (`fiji-mcp-install install … --fiji-path …`).

### From a git clone (developers)

**Clone once**, then run the installer from the repo root. It creates **`.venv`**, upgrades **pip / setuptools / wheel**, and runs **`pip install -e .`**, which pulls **every runtime dependency** from `pyproject.toml` (you do not need to list packages yourself).

```bash
git clone https://github.com/surajinacademia/Fiji_imageJ_mcp.git
cd Fiji_imageJ_mcp
python3 scripts/install_fiji_mcp.py
```

Or the same thing via shell wrapper:

```bash
chmod +x install.sh   # once, if needed
./install.sh
```

**Options:**

| Flag | Meaning |
| ---- | -------- |
| `--venv .venv` | Virtualenv path (default: `.venv`) |
| `--with-tests` | Also install pytest extras (`pip install -e .[test]`) |
| `--into-current` | No new venv; install into the **active** Python (use only inside a venv you already created) |

**Alternative — already inside your own venv:**

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python scripts/install_fiji_mcp.py --into-current
```

**Alternative — one `pip` line from GitHub** (installs into the **current** environment; use a venv first):

```bash
python -m venv .venv && source .venv/bin/activate
python -m pip install -U pip setuptools wheel
python -m pip install "git+https://github.com/surajinacademia/Fiji_imageJ_mcp.git"
```

After any method, check:

```bash
source .venv/bin/activate   # if you use .venv
fiji-mcp-install --help
python -m fiji_mcp --help
```

---

## 3. Configure your MCP client

Use the **same** Python that has `fiji_mcp` (the `.venv` you just created, unless you used `--into-current` elsewhere).

Replace `/Applications/Fiji` with your real Fiji root.

**Method A — auto-install (recommended)**

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
Optional: `--mode gui`, or `--command /full/path/to/.venv/bin/fiji-mcp-server` if the host app does not see your venv.

**Restart** the editor or CLI, then continue to §4.

**Method B — paste JSON** — same `mcpServers.fiji` shape everywhere; see [Configuration](configuration.md).

---

## 4. Quick verification

In chat:

```text
Call the Fiji MCP health_check tool
```

Optional terminal smoke (needs `FIJI_PATH`):

```bash
export FIJI_PATH=/Applications/Fiji
export FIJI_MODE=headless
python scripts/demo_fiji_mcp_session.py
```

First JVM start is often **30–90 seconds**; later calls are faster.

### Plug-and-play: `scripts/mcp_and_gui_fiji.py`

<a id="mcp-and-gui-fiji"></a>

One command exercises **the real MCP stdio path** (FastMCP `Client` → `python -m fiji_mcp` → `call_tool`), not in-process imports of `fiji_mcp.tools.*`.

From the **repo root**, with the same venv you use for MCP:

```bash
source .venv/bin/activate   # if needed
python scripts/mcp_and_gui_fiji.py
```

**What it does by default**

- If **`FIJI_PATH`** is unset, it imports `fiji_mcp` and uses the same **auto-detection** as the server (`fiji_mcp.fiji_bridge.detect_fiji_path`), sets `FIJI_PATH` for the child MCP process, and prints the chosen path.
- If you **omit the image**, it prefers `demo_output/readme_ex03_img00_input.jpg`, then `demo_images/sample_gradient.pgm`, then another raster under `demo_images/`.
- Runs the **MCP monitor** (default **4** ticks, **5** s apart): writes `tick_*.json` and `tick_*.jpg` under `demo_output/mcp_live/`.
- On **macOS**, opens **Fiji.app** with the same file **after** MCP finishes (two separate Fiji instances).

**Useful flags** (default parser — omit these for the full combo on macOS):

| Flag | Meaning |
| ---- | ------- |
| `--mcp-only` | No Fiji.app |
| `--gui-only` | Only Fiji.app (no MCP; macOS) |
| `--no-gui` / `--no-mcp` | Turn off half of the default combo |
| `--gui-first` | Fiji.app before MCP |
| `--iterations`, `--interval`, `--out-dir` | Monitor tuning (defaults: 4 ticks, 5 s, `demo_output/mcp_live/`) |

**Auto-detect when `FIJI_PATH` is unset:** the script must be able to **`import fiji_mcp`** (e.g. `pip install -e .` from this repo, or `python scripts/install_fiji_mcp.py` so `.venv` has the editable install).

**Examples**

```bash
python scripts/mcp_and_gui_fiji.py
python scripts/mcp_and_gui_fiji.py ./my_sample.tif
python scripts/mcp_and_gui_fiji.py --mcp-only --iterations 2 --interval 1
unset FIJI_PATH && python scripts/mcp_and_gui_fiji.py --mcp-only --iterations 1
```

**Legacy (unchanged):** if the **first** argument is `mcp-monitor`, `open-gui`, or `both`, the old subcommand API is used, e.g. `python scripts/mcp_and_gui_fiji.py mcp-monitor --image demo_images/sample_gradient.pgm`. See `python scripts/mcp_and_gui_fiji.py --help` in each mode.

---

## 5. What to read next

| Topic | Doc |
| ----- | --- |
| Env vars, troubleshooting, Cursor plugin | [Configuration](configuration.md) |
| All MCP tools | [MCP Tools](tools.md) |
| Package layout | [Architecture](architecture.md) |
| Batch report over stdio MCP | [Batch report workflow](batch_report_workflow.md) |
| Roadmap | [plan.md](https://github.com/surajinacademia/Fiji_imageJ_mcp/blob/main/plan.md) |

**Developers:** after `python scripts/install_fiji_mcp.py --with-tests`, run `pip install -e ".[dev]"` and `pre-commit install` if you use repo hooks.

---

## Tests (optional)

```bash
pytest -m "not integration"
```

Integration tests need **`FIJI_PATH`** and **`FIJI_TEST_IMAGE`** — see [Configuration](configuration.md).
