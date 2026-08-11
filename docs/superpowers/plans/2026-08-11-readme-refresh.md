# Fiji MCP README Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the terse v0.2.0 README with a fast, truthful onboarding guide modeled on the useful information flow of Cellpose MCP while preserving Fiji MCP's exact nine-tool contract.

**Architecture:** This is one documentation deliverable guarded by a parsed-content regression in the existing package-export test module. The README leads with installation and Codex setup, then examples, the exact tool catalog, limitations, architecture, and acknowledgments. No runtime source or public schema changes.

**Tech Stack:** Markdown, Python 3.10+, pytest, `json`, `tomllib`, and the existing `fiji-mcp-server` stdio entry point.

## Global Constraints

- Keep the package and documented release at exactly `0.2.0`.
- Do not restore `fiji-mcp-install` or any removed installer/framework surface.
- Document exactly nine tools: `get_state`, `search_commands`, `run_command`, `run_script`, `open_image`, `save_image`, `get_results`, `screenshot`, and `compare_screenshots`.
- `FIJI_PATH` points to the Fiji root containing `jars/` and `plugins/`; `FIJI_MODE=headless` is the recommended default.
- Do not claim plugin installation, universal structured plugin parameters, GUI automation, or a sandbox.
- Use original Fiji-specific prose; Cellpose MCP supplies information-architecture inspiration only.
- Use the current official Codex MCP setup documented at <https://developers.openai.com/codex/mcp/>.

---

### Task 1: Guard and implement the approved README

**Files:**
- Modify: `tests/test_package_exports.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: the nine public tool registrations in `src/fiji_mcp/server.py` and exact behavior documented in `docs/tools.md`.
- Produces: a v0.2.0 onboarding README whose JSON and TOML configuration snippets parse and whose tool catalog is machine-checked.

- [ ] **Step 1: Add the failing README contract test**

Add `json` and `re` imports and this test to `tests/test_package_exports.py`:

```python
def test_readme_documents_v020_onboarding_and_exact_tool_surface() -> None:
    readme = Path("README.md").read_text()
    json_config = readme.split("```json\n", maxsplit=1)[1].split(
        "\n```", maxsplit=1
    )[0]
    toml_config = readme.split("```toml\n", maxsplit=1)[1].split(
        "\n```", maxsplit=1
    )[0]
    tool_section = readme.split("## The nine tools\n", maxsplit=1)[1].split(
        "\n## ", maxsplit=1
    )[0]
    documented_tools = re.findall(r"^\| `([^`]+)` \|", tool_section, re.MULTILINE)

    assert "This README documents v0.2.0" in readme
    assert 'python -m pip install "fiji-mcp-server==0.2.0"' in readme
    assert "codex mcp add fiji" in readme
    assert json.loads(json_config)["mcpServers"]["fiji"]["command"] == (
        "fiji-mcp-server"
    )
    assert tomllib.loads(toml_config)["mcp_servers"]["fiji"]["env"] == {
        "FIJI_PATH": "/Applications/Fiji",
        "FIJI_MODE": "headless",
    }
    assert documented_tools == [
        "get_state",
        "search_commands",
        "run_command",
        "run_script",
        "open_image",
        "save_image",
        "get_results",
        "screenshot",
        "compare_screenshots",
    ]
    assert readme.count("> **Prompt:**") >= 5
    assert "fiji-mcp-install" not in readme
    assert "trusted arbitrary local code" in readme
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_package_exports.py::test_readme_documents_v020_onboarding_and_exact_tool_surface -v
```

Expected: FAIL because the old README has no TOML block, versioned install command, approved section title, or five prompt blocks.

- [ ] **Step 3: Replace `README.md` with the approved document**

Use this exact content:

````markdown
# Fiji MCP Server

[![PyPI version](https://img.shields.io/pypi/v/fiji-mcp-server.svg)](https://pypi.org/project/fiji-mcp-server/)
[![Python versions](https://img.shields.io/pypi/pyversions/fiji-mcp-server.svg)](https://pypi.org/project/fiji-mcp-server/)
[![License](https://img.shields.io/pypi/l/fiji-mcp-server.svg)](LICENSE)

**Give your AI assistant hands inside Fiji/ImageJ.** Fiji MCP Server is a small
stdio [Model Context Protocol](https://modelcontextprotocol.io/) bridge that can
open and save images, discover and run installed commands, execute IJM or
Groovy, read Results, and verify changes with screenshots.

This README documents v0.2.0. The public surface is deliberately limited to
nine tools; Fiji's live command registries and scripting APIs provide the
plugin reach without a large custom framework.

## Quick start

You need Python 3.10 or newer and a local
[Fiji](https://fiji.sc/) installation.

1. Install the server:

   ```bash
   python -m pip install "fiji-mcp-server==0.2.0"
   ```

2. Locate the Fiji root directory. It must directly contain `jars/` and
   `plugins/`; on this Mac, for example, it is `/Applications/Fiji`.

3. Connect your MCP client using `FIJI_PATH`. Headless mode is recommended for
   agent workflows:

   ```bash
   FIJI_PATH=/Applications/Fiji FIJI_MODE=headless fiji-mcp-server
   ```

Fiji starts lazily on the first Fiji-backed tool call. The bridge prefers one
compatible JVM bundled inside the selected Fiji installation.

## Connect Codex

The official Codex CLI, IDE extension, and ChatGPT desktop app share MCP
configuration on the same Codex host. Add this stdio server from a terminal:

```bash
codex mcp add fiji \
  --env FIJI_PATH=/Applications/Fiji \
  --env FIJI_MODE=headless \
  -- fiji-mcp-server
codex mcp list
```

Or add the equivalent entry to `~/.codex/config.toml` (or a trusted project's
`.codex/config.toml`):

```toml
[mcp_servers.fiji]
command = "fiji-mcp-server"
startup_timeout_sec = 120
tool_timeout_sec = 300

[mcp_servers.fiji.env]
FIJI_PATH = "/Applications/Fiji"
FIJI_MODE = "headless"
```

In ChatGPT desktop, you can also open **Settings → MCP servers → Add server**,
choose **STDIO**, and then restart after saving. See the
[official Codex MCP documentation](https://developers.openai.com/codex/mcp/)
for current client controls.

## Other JSON-based MCP clients

Many local MCP clients use this common JSON shape. Their configuration-file
location and restart control are client-specific:

```json
{
  "mcpServers": {
    "fiji": {
      "command": "fiji-mcp-server",
      "env": {
        "FIJI_PATH": "/Applications/Fiji",
        "FIJI_MODE": "headless"
      }
    }
  }
}
```

If the client cannot find `fiji-mcp-server`, replace `command` with the full
path reported by `which fiji-mcp-server` (macOS/Linux) or
`where fiji-mcp-server` (Windows).

## Try these prompts

> **Prompt:** Open `/data/cells.tif`, inspect its dimensions and current C/Z/T
> position, and show me an active-image screenshot.

> **Prompt:** Search the installed Fiji commands for “Gaussian Blur”. Show the
> best matching command's invocation route and accepted inputs, then run it with
> sigma 2 only if that parameter is supported.

> **Prompt:** Run an ImageJ macro that thresholds the active image and measures
> it, then return the Results table in pages of 200 rows.

> **Prompt:** Save a screenshot to `/tmp/before.png`, apply the chosen threshold,
> save `/tmp/after.png`, and compare them. If the expected change is absent,
> inspect state and logs before adjusting the threshold once; do not blindly
> repeat a mutation whose outcome is unknown.

> **Prompt:** Use Groovy to call an installed scriptable plugin that is not
> representable as a structured command, then summarize its bounded result and
> the active-image state.

> **Prompt:** Save the active image as `/data/output/processed.tiff`. Do not
> overwrite an existing file, and report the exact path Fiji created.

## What can it do?

- **Inspect and move data:** read live state, open a local image, save the active
  image, and page through the Results table.
- **Use installed commands:** search Fiji's SciJava and ImageJ1 registries, then
  invoke a selected command through structured parameters or legacy options
  when that route is supported.
- **Reach scriptable plugins:** use trusted IJM or Groovy for ROIs, unusual Java
  inputs, and installed plugins that do not fit the registered command route.
- **Verify visually:** render the active plane or Results table, save before and
  after PNGs, and compare dimensions and same-size pixel metrics.

The server does not install plugins, click dialogs, drive menus, or promise
structured parameters for every plugin.

## The nine tools

| Tool | Purpose |
| --- | --- |
| `get_state` | Read Fiji lifecycle, active/open images, and Results-table state. |
| `search_commands` | Search registered SciJava and ImageJ1 commands and inspect their routes. |
| `run_command` | Run one resolved installed command with supported parameters or options. |
| `run_script` | Run one trusted IJM or Groovy script. |
| `open_image` | Open an existing local image and make it current. |
| `save_image` | Save the active image to a new exact lowercase supported path. |
| `get_results` | Read an ordered, paginated page from Fiji's live Results table. |
| `screenshot` | Return and optionally save a PNG of the active plane or Results. |
| `compare_screenshots` | Compare two saved raster paths visually and, when sizes match, numerically. |

See the [complete nine-tool reference](docs/tools.md) for signatures, return
fields, limits, and failure behavior.

## How it works

```text
AI client ── stdio JSON-RPC ──▶ FastMCP ── serialized bridge ──▶ PyImageJ ──▶ Fiji + installed plugins
```

Fiji operations share one process-wide lock. Read-only operations receive at
most one retry for a small allowlist of transient failures. Commands, scripts,
image opens, and saves are never automatically repeated after dispatch.

## Safety and limitations

`run_script` executes **trusted arbitrary local code**. IJM and Groovy can read
or modify anything available to the MCP process, so run this server only for a
trusted local client. It is not a remote multi-user service or a sandbox.

Python diagnostics and ordinary Java output are redirected to stderr to protect
stdio JSON-RPC. Plugins that require GUI dialogs, mouse/keyboard automation, or
unscriptable interaction may fail in headless mode. Use `FIJI_MODE=gui` only for
an intentional local desktop workflow supported by that plugin.

Saving is strict: the requested suffix must be one of the exact lowercase
formats documented in the tool reference, and an existing output is rejected.
After any mutation with an unknown outcome, inspect state or take a screenshot
before deciding whether to retry.

## Project links and acknowledgments

- [Fiji](https://fiji.sc/) and [ImageJ](https://imagej.net/)
- [PyImageJ](https://github.com/imagej/pyimagej)
- [FastMCP](https://gofastmcp.com/)
- README-structure inspiration: [Cellpose MCP](https://github.com/surajinacademia/cellpose_mcp)
- Related minimal viewer bridge: [napari-mcp](https://github.com/royerlab/napari-mcp)
- [Changelog](CHANGELOG.md) and [historical release notes](docs/releases/)

## License

BSD-3-Clause. See [LICENSE](LICENSE).
````

- [ ] **Step 4: Run the focused test and verify GREEN**

Run:

```bash
.venv/bin/python -m pytest tests/test_package_exports.py -v
```

Expected: all package-export and README contract tests pass.

- [ ] **Step 5: Run README-specific static checks**

Run:

```bash
rg -n "fiji-mcp-install|run_macro|screenshot_fiji|health_check" README.md
```

Expected: exit 1 with no matches.

Run:

```bash
.venv/bin/python -m ruff check tests/test_package_exports.py
.venv/bin/python -m ruff format --check tests/test_package_exports.py
git diff --check
```

Expected: all exit 0; Ruff reports no issue or formatting change.

- [ ] **Step 6: Request a documentation/correctness review**

Ask a read-only reviewer to compare `README.md` against
`docs/superpowers/specs/2026-08-11-readme-refresh-design.md`, `docs/tools.md`,
`src/fiji_mcp/server.py`, and the official Codex MCP documentation. Resolve any
Critical or Important factual/onboarding defect before committing.

- [ ] **Step 7: Commit the README deliverable**

```bash
git add README.md tests/test_package_exports.py
git diff --cached --check
git commit -m "docs: refresh Fiji MCP onboarding"
```

Expected: one documentation commit containing only the README and its contract
test.

### Task 2: Verify the release candidate after the README change

**Files:**
- Verify only: repository and built distributions

**Interfaces:**
- Consumes: committed Task 1 README and existing v0.2.0 package metadata.
- Produces: evidence that docs, package, stdio tool discovery, and release
  artifacts remain consistent before merging to `main`.

- [ ] **Step 1: Run the full non-integration quality gates**

```bash
.venv/bin/python -m pytest -m "not integration" -v
.venv/bin/python -m ruff check src/ tests/
.venv/bin/python -m ruff format --check src/ tests/
.venv/bin/python -m mypy src/fiji_mcp --ignore-missing-imports
```

Expected: pytest has zero failures/errors; Ruff and mypy exit 0.

- [ ] **Step 2: Build and validate the final artifacts**

```bash
.venv/bin/python -m build --no-isolation
.venv/bin/python -m twine check dist/*
.venv/bin/python tests/wheel_smoke.py dist/fiji_mcp_server-0.2.0-py3-none-any.whl
```

Expected: wheel and sdist build; Twine reports `PASSED`; clean wheel install
lists exactly the nine MCP tools without requiring `FIJI_PATH`.

- [ ] **Step 3: Confirm the branch is ready for the finishing workflow**

```bash
git diff --check
git status --short
git log -3 --oneline
```

Expected: no whitespace errors, clean worktree, and the README plus security
commits are present. Then use the finishing-a-development-branch workflow to
merge into `main`, retest the merged tree, and remove the owned worktree/branch.
