# Fiji MCP README refresh design

**Status:** Approved on 2026-08-11

## Context

The v0.2.0 implementation is intentionally a small stdio MCP server with nine
tools. Its README must help a new user install and connect it quickly without
reviving the removed installer CLI or suggesting capabilities that the server
does not expose.

The information architecture is inspired by the public
[Cellpose MCP README](https://github.com/surajinacademia/cellpose_mcp#readme):
lead with the product promise, make setup copyable, show useful natural-language
prompts immediately, and keep the tool catalog compact. Wording and examples
will be original and specific to Fiji/ImageJ.

## Goals

- Explain the product as giving an AI assistant practical hands for a local
  Fiji/ImageJ installation.
- Get a new user from installation to a working stdio configuration with the
  fewest necessary steps.
- Show realistic image-analysis prompts, including screenshot comparison and
  cautious retry behavior.
- Reinforce the exact nine-tool surface and v0.2.0 release identity.
- State the trusted-local security boundary and headless/plugin limitations
  plainly.

## Non-goals

- No package-version bump beyond `0.2.0`.
- No reintroduction of `fiji-mcp-install` or other deleted installer commands.
- No claim that the server installs plugins, automates Fiji menus/dialogs, or
  exposes every plugin through structured parameters.
- No screenshots, logos, poster assets, or copied Cellpose MCP prose.
- No change to server behavior, public tool schemas, or runtime dependencies.

## README structure

1. **Title and badges** — PyPI version, Python 3.10+, and BSD-3-Clause.
2. **Plain-language promise** — a short explanation of the local Fiji/ImageJ
   control loop and the deliberate nine-tool scope.
3. **Quick start** — install Fiji, install `fiji-mcp-server`, locate the Fiji
   root, and use headless mode by default.
4. **Connect an MCP client** — one canonical stdio JSON example plus concise,
   verified notes for Codex and other common MCP clients. Configuration remains
   manual and uses the installed `fiji-mcp-server` entry point.
5. **Try these prompts** — immediately useful copyable requests.
6. **What can it do?** — examples grouped around inspection/I/O, installed
   command discovery, scripts/results, and visual verification.
7. **Nine tools** — one compact table with each exact public name and purpose.
8. **Safety and limitations** — trusted arbitrary IJM/Groovy execution,
   filesystem access, headless behavior, no automatic mutation retry, and
   plugin/dialog limitations.
9. **Architecture and links** — minimal stdio flow, detailed tool reference,
   acknowledgments, and license.

## Example prompt set

The README will include original prompts covering these verified workflows:

- Open a local microscopy image, inspect dimensions/state, and take an active
  image screenshot.
- Search installed commands for Gaussian blur, inspect the selected command,
  and run it with a supported parameter.
- Run an IJM or Groovy script on the active image, then read the Results table.
- Capture before/after PNGs, compare them, inspect state after an uncertain
  mutation, and retry only when evidence supports it.
- Save the active image to a new exact lowercase supported path without
  overwriting an existing output.

Examples must not promise free-form structured parameters for every legacy
plugin. They should demonstrate discovery before execution where the installed
command contract is unknown.

## Configuration policy

- The canonical executable is `fiji-mcp-server` from the installed wheel.
- `FIJI_PATH` is required and points to the Fiji root containing `jars/` and
  `plugins/`.
- `FIJI_MODE=headless` is the recommended default; `gui` is an explicit local
  override.
- Client-specific paths and config locations will be included only after they
  are checked against current authoritative documentation or the client's
  current schema.
- A full executable path may be shown as a troubleshooting fallback when an MCP
  client does not inherit the shell `PATH`.

## Version and badge policy

The README describes release `0.2.0`, matching `pyproject.toml`. Badges may show
the live PyPI release, the supported Python floor, and the repository license.
No badge may imply CI, coverage, download, or platform guarantees that are not
backed by the repository or publishing state.

## Acceptance criteria

- The first screen communicates purpose, install command, and next action.
- Every documented command exists in the v0.2.0 package.
- All nine public tool names appear exactly once in the catalog.
- At least five copyable prompts demonstrate the workflows above.
- Manual configuration is valid JSON and uses `FIJI_PATH` correctly.
- Security language identifies `run_script` as trusted arbitrary local code.
- The README links to `docs/tools.md`, the project license, Fiji, PyImageJ, and
  FastMCP without copying third-party branding or prose.
- Markdown, package tests, non-integration tests, build, Twine validation, and
  clean-wheel stdio smoke verification remain green.
