# Fiji MCP Server

[![PyPI version](https://img.shields.io/pypi/v/fiji-mcp-server.svg)](https://pypi.org/project/fiji-mcp-server/)
[![Python versions](https://img.shields.io/pypi/pyversions/fiji-mcp-server.svg)](https://pypi.org/project/fiji-mcp-server/)
[![License](https://img.shields.io/pypi/l/fiji-mcp-server.svg)](https://github.com/surajinacademia/Fiji_imageJ_mcp/blob/main/LICENSE)

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

   To test a source checkout instead:

   ```bash
   python -m pip install .
   ```

2. Locate the Fiji root directory. It must directly contain `jars/` and
   `plugins/`; on this Mac, for example, it is `/Applications/Fiji`.

3. Configure your MCP client with `FIJI_PATH` and `FIJI_MODE=headless`; see
   the client-specific instructions below. The MCP client owns the stdio process
   and starts `fiji-mcp-server` when needed.

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

## Connect Claude

For Claude Code, use the absolute path reported by `which fiji-mcp-server`:

```bash
claude mcp add \
  --scope user \
  --transport stdio \
  fiji \
  --env FIJI_PATH=/Applications/Fiji \
  --env FIJI_MODE=headless \
  -- /absolute/path/to/fiji-mcp-server
claude mcp get fiji
```

For Claude Desktop, add this entry to `claude_desktop_config.json`. On macOS,
the file is in `~/Library/Application Support/Claude/`. On Windows, it is in
`%APPDATA%\Claude\`. Fully quit and reopen Claude Desktop after saving.

```json
{
  "mcpServers": {
    "fiji": {
      "command": "/absolute/path/to/fiji-mcp-server",
      "args": [],
      "env": {
        "FIJI_PATH": "/Applications/Fiji",
        "FIJI_MODE": "headless"
      }
    }
  }
}
```

See the official [Claude Code MCP guide](https://code.claude.com/docs/en/mcp)
and [Claude Desktop host guide](https://py.sdk.modelcontextprotocol.io/get-started/real-host/).

## Connect Gemini CLI

Gemini CLI supports the same local stdio server. User scope makes it available
in all trusted projects:

```bash
gemini mcp add \
  --scope user \
  --transport stdio \
  -e FIJI_PATH=/Applications/Fiji \
  -e FIJI_MODE=headless \
  fiji /absolute/path/to/fiji-mcp-server
gemini mcp list
```

See the official [Gemini CLI MCP guide](https://geminicli.com/docs/tools/mcp-server/).

## Connect Perplexity

Local MCP is currently documented for the Perplexity macOS app from the Mac
App Store. The feature is rolling out to paid subscribers. Open **Settings →
Connectors**, install the **PerplexityXPC** helper, then select **Add Connector
→ Simple**. Use `Fiji` as the server name and this command:

```text
/usr/bin/env FIJI_PATH=/Applications/Fiji FIJI_MODE=headless /absolute/path/to/fiji-mcp-server
```

Save the connector, wait for **Running**, and enable it under **Sources**.
Perplexity does not currently document local MCP setup for Windows or
standalone Comet. See the official
[Perplexity local MCP guide](https://www.perplexity.ai/help-center/en/articles/11502712-local-and-remote-mcps-for-perplexity).

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

See the [complete nine-tool reference](https://github.com/surajinacademia/Fiji_imageJ_mcp/blob/main/docs/tools.md) for
signatures, return fields, limits, and failure behavior.

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

`save_image` is strict within this MCP server process: its requested suffix must
be one of the exact lowercase formats documented in the tool reference, and an
output that exists when the serialized save begins is rejected. It is not a
cross-process atomic publisher, so another local process can still race that
check; use a dedicated output directory when other writers are active.
`screenshot` and `compare_screenshots` overwrite an existing `save_path`; use a
new path when preserving an existing PNG is required. After any mutation with
an unknown outcome, inspect state or take a screenshot before deciding whether
to retry.

## Project links and acknowledgments

- [Fiji](https://fiji.sc/) and [ImageJ](https://imagej.net/)
- [PyImageJ](https://github.com/imagej/pyimagej)
- [FastMCP](https://gofastmcp.com/)
- README-structure inspiration: [Cellpose MCP](https://github.com/surajinacademia/cellpose_mcp)
- Related minimal viewer bridge: [napari-mcp](https://github.com/royerlab/napari-mcp)
- [Changelog](https://github.com/surajinacademia/Fiji_imageJ_mcp/blob/main/CHANGELOG.md)

## License

BSD-3-Clause. See [LICENSE](https://github.com/surajinacademia/Fiji_imageJ_mcp/blob/main/LICENSE).
