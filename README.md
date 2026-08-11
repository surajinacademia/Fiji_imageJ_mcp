# Fiji MCP Server

Fiji MCP Server is a minimal stdio MCP server that lets an AI client control a
local Fiji/ImageJ instance through commands, IJM, Groovy, images, Results, and
screenshots.

## Install

```bash
pip install fiji-mcp-server
```

Install [Fiji](https://fiji.sc/) locally and set `FIJI_PATH` to its root
directory, which must contain `jars/` and `plugins/`. The server defaults to
headless Fiji; `FIJI_MODE=gui` is an explicit optional override.

Before Fiji starts, the bridge prefers exactly one valid JVM bundled for the
current platform under `FIJI_PATH/java/`. An already configured SciJava JVM is
left alone, and installations without one matching bundled JVM fall back to
SciJava's normal JVM selection. Multiple matching bundled JVMs produce a setup
error rather than an arbitrary choice.

## Configure an MCP client

Add a generic stdio server entry to your MCP client's configuration, replacing
the Fiji path with your local installation. `FIJI_MODE` is optional and shown
here with its default value.

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

## Nine MCP tools

| Tool | Purpose |
| --- | --- |
| `get_state` | Read live Fiji, image, and Results-table state. |
| `search_commands` | Find registered SciJava and ImageJ1 commands. |
| `run_command` | Invoke one registered command with supported parameters. |
| `run_script` | Run one IJM or Groovy script. |
| `open_image` | Open and activate a local image. |
| `save_image` | Save the active image to a local path. |
| `get_results` | Read a paginated, ordered page of the Results table. |
| `screenshot` | Render the active image or Results table as PNG. |
| `compare_screenshots` | Compare two saved screenshot paths numerically and visually. |

## Example prompts

1. “Open `/data/cells.tif`, save an active-image screenshot to
   `/tmp/cells-before.png`, apply a Gaussian blur, save
   `/tmp/cells-after.png`, compare the two screenshots, and save the processed
   image as `/data/out/cells-blurred.tif`.”
2. “Search the installed Fiji commands for particle analysis, show the accepted
   parameters for the best match, then run it on the active image and report
   the returned outputs.”
3. “Open `/data/objects.tif`, measure the objects with an IJM script, and
   return the Results table in pages of 200 rows.”

## Trusted local execution and limitations

`run_script` executes trusted arbitrary local IJM or Groovy code. It can read
or modify files available to the MCP process, so do not expose this server to
untrusted clients. Python diagnostics and ordinary Java output are redirected
to stderr so stdout remains MCP JSON-RPC; deliberately writing to native file
descriptor 1 can bypass Java stream redirection and is not a sandbox boundary.

The server discovers and runs already-installed commands, and IJM/Groovy can
reach installed plugins that are scriptable. It does not install plugins or
automate dialogs, menus, mouse input, or keyboard input. Plugins that require a
GUI or cannot accept scripted parameters may fail in headless mode; use a
scriptable route when available or restart with `FIJI_MODE=gui`.

Fiji calls are serialized. Read-only operations receive at most one retry for
explicitly allowlisted transient failures; image opening/saving, command
execution, and script execution are never retried automatically after they are
dispatched. If a mutation's result is unknown, inspect `get_state` or capture a
`screenshot` before choosing whether to repeat it.

For visual verification, save a `screenshot` before an operation and another
after it, then pass those two saved paths to `compare_screenshots`. The
comparison is stateless and reports image dimensions, a visual comparison, and
same-size pixel metrics. Use `get_results(offset, limit)` for full tabular data:
it preserves ImageJ column and row order, while a Results screenshot renders at
most the first 100 rows.

## Learn more

See the [nine-tool reference](docs/tools.md) for signatures and return fields,
and [historical release notes](docs/releases/) for prior releases.
