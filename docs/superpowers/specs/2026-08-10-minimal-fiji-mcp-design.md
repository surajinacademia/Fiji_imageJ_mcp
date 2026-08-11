# Minimal Fiji MCP Design

**Date:** 2026-08-10
**Status:** Approved design; implemented
**Scope:** Replace the current broad Fiji MCP API with a small, script-first server

## 1. Purpose

The project should give an AI agent practical hands inside Fiji/ImageJ through MCP. The agent must be able to inspect the current Fiji state, discover and invoke installed commands, run ImageJ Macro or Groovy code, open and save images, read measurements, and visually inspect results.

The MCP server is an adapter, not a workflow engine. Fiji owns scientific application state, and the agent owns reasoning and multi-step orchestration.

The intended experience follows the useful abstraction in [`royerlab/napari-mcp`](https://github.com/royerlab/napari-mcp): a limited set of generic application operations plus a general code-execution escape hatch. The closest direct Fiji precedent, [`NicoKiaru/fiji_mcp`](https://github.com/NicoKiaru/fiji_mcp), likewise demonstrates that broad Fiji access does not require one MCP tool per plugin.

## 2. Goals

The minimal server must:

1. Run as a standard stdio MCP server.
2. Start and own one Fiji instance through PyImageJ.
3. Default to headless operation while allowing an explicit GUI override.
4. Discover registered ImageJ1 and SciJava commands.
5. Invoke installed commands with supplied parameters.
6. Execute ImageJ Macro and Groovy scripts as universal escape hatches.
7. Open, inspect, and save local images.
8. Return the ImageJ Results table as structured, paginated data.
9. Capture the active image or Results table for visual inspection.
10. Compare two saved screenshots numerically and visually.
11. Retry only operations that can be repeated without risking duplicate scientific actions.
12. Produce concise, actionable errors without corrupting stdio JSON-RPC.

## 3. Non-goals

The server will not:

- Provide a server-side workflow or batch engine.
- Maintain an MCP session trace or duplicate Fiji's state.
- Bundle macro templates or predefined scientific pipelines.
- Create individual MCP tools for specific Fiji plugins.
- Install plugins, enable update sites, or manage packages.
- Automate mouse clicks, menus, dialogs, or keyboard input.
- Guarantee headless execution of plugins that require GUI interaction.
- Parse arbitrary free-form macro output with a general parser.
- Cache screenshots or maintain screenshot identifiers.
- Auto-detect Fiji or Java through platform-specific search rules.
- Ship client-specific configuration installers or compatibility wrappers for the old API.

"All plugins" means every already-installed plugin that is registered as an ImageJ command or can be reached through ImageJ Macro, Groovy, or the SciJava API. GUI-only plugins that cannot accept scripted parameters are outside this contract.

## 4. Architecture

One Python process hosts FastMCP, PyImageJ, and a single Fiji runtime:

```text
MCP client --stdio--> FastMCP tools --> thin PyImageJ bridge --> Fiji and installed plugins
```

Fiji starts lazily on the first tool call and remains alive until the MCP process exits. Its lifecycle has four explicit states: `NEW`, `STARTING`, `READY`, and `FAILED`. A single process-wide operation lock serializes access because ImageJ windows, active images, ROIs, and Results tables share global mutable state.

Fiji is the only source of application state. The server does not mirror open images, remember workflows, or record tool history. Each query reads live state from Fiji.

The core implementation consists of:

```text
src/fiji_mcp/
├── __init__.py     # package metadata
├── __main__.py     # stdio entry point
├── server.py       # FastMCP instance and nine registrations
├── tools.py        # thin public tool handlers
├── bridge.py       # lifecycle, locking, execution, retries, errors
├── imaging.py      # screenshots and image comparison
└── py.typed        # typing marker
```

There is no custom result-schema package. Public tools return small typed dictionaries, text, tabular rows, or native MCP image content.

## 5. Configuration and startup

The server accepts only two runtime settings:

- `FIJI_PATH` is required and must point to a Fiji root containing `jars/` and `plugins/`.
- `FIJI_MODE` is optional, accepts `headless` or `gui`, and defaults to `headless`.

There is no automatic Fiji-path discovery. Before importing or initializing
ImageJ, the bridge prefers exactly one valid JVM packaged under the current
platform bucket in `FIJI_PATH/java/`; it preserves a caller-configured SciJava
`jvmpath`, falls back to SciJava's normal JVM selection when no matching bundle
exists, and fails clearly rather than guessing when several valid bundled JVMs
exist. A missing or invalid `FIJI_PATH` fails with one short setup instruction
before any scientific operation is attempted.

The published console entry point remains `fiji-mcp-server`. Documentation provides one generic stdio MCP configuration block that users can adapt to any compliant client. The `fiji-mcp-install` command is removed.

## 6. Public MCP tools

The server exposes exactly nine tools.

### 6.1 `get_state()`

Returns live Fiji state:

- Fiji/ImageJ version and configured mode.
- Active image title, dimensions, channels, slices, frames, and bit depth.
- Summaries of all open images.
- Results-table row count and column names.

Calling `get_state` also serves as the health check. There is no separate `health_check`, `list_open_images`, or `get_image_info` tool.

### 6.2 `search_commands(query, limit=20)`

Searches both SciJava `CommandService` entries and the ImageJ1 menu command registry. It returns:

- Display name, class name, menu path, and command family.
- Input names, types, required status, and descriptions when SciJava metadata exists.
- The appropriate invocation route: structured parameters, legacy options string, or script fallback.

An empty query lists commands up to `limit`. `limit` must be between 1 and 100 so an entire Fiji command catalog cannot flood the MCP context. Results are sorted deterministically by display name and class name.

### 6.3 `run_command(name, parameters=None, options=None)`

Runs one already-installed command.

- Modern SciJava commands receive a JSON-like parameter dictionary.
- Legacy ImageJ commands receive an ImageJ options string.
- If neither route can represent a plugin's inputs, the tool fails with a suggestion to use `run_script`.

`parameters` and `options` are mutually exclusive; omitting both runs a no-argument command. `name` accepts either a display name or a fully qualified command class. Resolution precedence is exact class name, exact case-sensitive display name, then a unique case-insensitive display name. An ambiguous name returns matching display names/classes and asks the agent to choose a class. Discovery deduplicates the same delegate class found through both registries and prefers its SciJava record because it carries richer metadata. JSON-incompatible or complex Java inputs use the Groovy escape hatch.

The response contains JSON-safe command outputs, the final 4,000 characters of the Fiji log, and active-image metadata after execution.

### 6.4 `run_script(language, code)`

Executes one script. Supported language values are:

- `ijm` for ImageJ Macro language.
- `groovy` for Groovy through the SciJava scripting service.

The response contains a JSON-safe script result, the final 4,000 characters of the Fiji log, and active-image metadata. This tool is the universal escape hatch for ROIs, stacks, unusual plugins, advanced APIs, and operations deliberately omitted from the typed MCP surface.

Command outputs and script results share one bounded serializer. It preserves nulls, booleans, finite numbers, strings, arrays, and collections. Maps with string keys become JSON objects. A map containing any non-string key becomes an ordered `map_entries` array of `{key, value}` pairs, so keys are never lossy string-coerced or accidentally merged. ImageJ images/datasets and Results tables become metadata summaries because pixels and table rows have dedicated tools. Unknown Java objects become a dictionary containing `java_type` and a string summary. Recursive values are limited to four levels, collections or maps to 100 entries, strings to 4,000 characters, and the serialized result to 64 KiB; truncation is reported explicitly. Cycles are replaced by a cycle marker rather than traversed indefinitely.

### 6.5 `open_image(path)`

Opens a local image, makes it active, and returns its title and dimensions. Basic formats use ImageJ directly; formats requiring Bio-Formats or another plugin can be opened through `run_command` or `run_script`.

### 6.6 `save_image(path)`

Saves the active image to the exact requested local path. Parent directories are
created when missing. The only accepted suffixes are the exact lowercase list
`.tif`, `.tiff`, `.jpg`, `.png`, `.gif`, `.bmp`, `.fits`, `.pgm`, `.zip`,
`.raw`, and `.avi`. `.jpeg` and case variants are rejected because ImageJ
rewrites those filename spellings. An existing exact output path is rejected, so
the tool never overwrites a file. The response returns the exact resolved path
and its extension without a leading dot as `format`. Because the server is an
explicitly trusted local execution tool, it does not implement a separate path
allowlist.

### 6.7 `get_results(offset=0, limit=500)`

Reads the live ImageJ Results table and returns:

- Original column headings in ImageJ column order.
- Rows as ordered arrays aligned with those headings.
- `offset`, returned row count, and total row count.

Pagination prevents large particle-analysis tables from consuming the agent's entire context. The server does not attempt to infer scientific meaning or parse arbitrary log text.

`offset` must be non-negative and `limit` must be between 1 and 5,000.

`null` is reserved for undefined ImageJ column slots (`columnExists(index) == false`). Defined cells reflect the ResultsTable: finite numeric cells remain JSON numbers, stored text remains strings (including possible empty-string placeholders), and numeric infinities become `"Infinity"` or `"-Infinity"`. Numeric `NaN` and NaN-encoded empty numeric slots both become `"NaN"`, because the public API cannot distinguish them. With NaN-empty disabled, empty numeric slots surface as `0`. Returning ordered arrays preserves blank or duplicate ImageJ headings without inventing dictionary keys. Row order is the live Results-table order.

### 6.8 `screenshot(target, save_path=None)`

Supported targets are `active_image` and `results`.

For `active_image`, the server renders the current C/Z/T plane using its current display range and LUT, compositing the visible overlay and ROI when present. It does not capture window chrome. For `results`, it renders a deterministic white table with black monospace text, original column order, headings, and up to the first 100 rows, followed by an omission marker when more rows exist. `get_results` remains the complete data interface.

Both targets are rendered at their natural size and proportionally reduced, never enlarged, when either dimension exceeds 2,048 pixels. The returned and optionally saved PNG contain the same rendered pixels. The tool returns native MCP image content plus basic dimensions. Saving before and after captures gives `compare_screenshots` stateless inputs without creating a cache or session store.

### 6.9 `compare_screenshots(before_path, after_path, save_path=None)`

Loads two local image files and returns:

- Original dimensions and whether dimensions match.
- Mean absolute error, RMSE, and changed-pixel fraction when dimensions match.
- A native MCP comparison image containing before, after, and absolute-difference panels when dimensions match.
- An optional saved comparison path.

For equal-sized inputs, both images are converted to RGB values in `[0, 1]`. MAE and RMSE are computed over every channel. The changed-pixel fraction is the fraction of pixels whose maximum channel difference is greater than zero.

Pixel metrics and the difference panel are omitted when dimensions differ rather than silently resizing or cropping images into a misleading numeric comparison. A side-by-side visual and both original dimensions are still returned. These metrics are verification aids, not scientific evidence by themselves.

## 7. Data flow

A typical agent-driven analysis is:

1. Call `get_state` or `open_image`.
2. Save a before capture with `screenshot` when comparison is needed.
3. Call `search_commands` if the correct plugin or command is unknown.
4. Use `run_command` for registered commands or `run_script` for the scripting escape hatch.
5. Inspect the active image with `screenshot` and measurements with `get_results`.
6. Save an after capture and call `compare_screenshots` when requested.
7. Call `save_image` for durable output.

The agent performs this sequencing. No MCP tool calls another MCP tool, and no workflow object exists in the server.

## 8. Concurrency, retries, and long operations

All Fiji calls are synchronous and acquire one process-wide lock inside the worker that performs the Java call. Concurrent MCP requests therefore execute one at a time and cannot race over the active image or Results table. If an MCP request is cancelled after dispatch, the Java worker remains lock-owning until Java returns; cancellation stops delivery of that result but does not release Fiji for another request. If Java never returns, restarting the MCP process is the only safe recovery.

Automatic retries are bounded to one additional attempt. They use the explicit lifecycle and dispatch phases rather than broad exception-message matching:

- `imagej.init` itself is never retried. A failure while lifecycle state is `STARTING` changes the state to `FAILED` and requires an MCP-server restart.
- Before JVM startup, only Python `InterruptedError` or `OSError` with `errno.EINTR` during Fiji-path validation is retryable.
- After startup, only a read-only snapshot that fails with Java `ConcurrentModificationException`, Python `InterruptedError`, or `OSError` with `errno.EINTR` is retryable, and only when lifecycle state remains `READY`, JPype reports a running JVM, and a lightweight Fiji version probe succeeds.
- Every unclassified exception defaults to no retry.
- No failure after a mutating operation reaches its `DISPATCHED` phase is retried automatically.

`run_command`, `run_script`, `open_image`, and `save_image` are dispatched exactly once. If the bridge fails after dispatch, the server reports the execution outcome as unknown and instructs the agent to inspect `get_state` or `screenshot` before explicitly deciding whether to repeat the action.

The server imposes no thread-based timeout on dispatched Fiji work. A timed-out Python worker could leave a plugin running and make the result unknowable. Long scientific operations are allowed to finish; client cancellation does not imply that Fiji safely stopped the operation.

The server never attempts to restart a partially started, stopped, or failed JVM in the same process. Such failures instruct the user to restart the MCP server.

## 9. Error contract and logging

One small exception translator maps common Python, Java, ImageJ, and SciJava failures into concise MCP errors. Each error communicates:

- Failure category and plain-language message.
- Whether retrying is safe.
- Whether execution definitely failed or may have completed.
- One concrete recovery action.

Expected categories include invalid configuration, missing file, no active image, command not found, invalid command parameters, unsupported script language, GUI-required plugin, Java bridge failure, and unknown execution outcome.

All Python diagnostic logging is directed to `stderr`. Before JVM startup, the bridge registers a JVM-start hook that immediately redirects Java `System.out` to `System.err`; this contains ordinary Groovy `println`, Java logging, and plugin output before tools execute. ImageJ Macro output is returned through the script result or Fiji log rather than server stdout.

The contract protects stdio against ordinary Python, ImageJ, Groovy, and Java output paths. Because `run_script` is trusted arbitrary code, deliberately writing to native process file descriptor 1 can still bypass Java stream redirection; this limitation is documented rather than presented as a sandbox guarantee.

## 10. Security model

This is a trusted local-development server. `run_script` provides arbitrary local ImageJ/Groovy execution and can read or modify files accessible to the MCP process. Attempting to impose a path restriction only on `open_image` and `save_image` would not sandbox scripts and would create a false security boundary.

The README must state this capability prominently. The server does not install plugins, run package managers, or expose a network transport by default.

## 11. Removal and migration

The simplification is a clean breaking change. Remove the old public tools and their supporting layers:

- `health_check` as a separate tool.
- `run_macro` in favor of `run_script(language="ijm", ...)`.
- `run_batch_macros` and `run_workflow`.
- `list_all_commands`, `describe_plugin`, and `list_extensions`.
- `list_open_images` and `get_image_info` as separate tools.
- `parse_macro_output`.
- Macro-template tools and bundled template data.
- Session-trace tools and session storage.
- Screenshot cache and generic optimizer utilities.
- The custom Pydantic output-schema package.
- Client-specific installer code and entry point.
- The obsolete `2026-07-21` v0.2 design and implementation-plan documents, plus user documentation that describes removed tools.

Retain and simplify the existing screenshot conversion/comparison logic and reusable Java error recognition where they serve the approved contracts. Historical release notes remain as release history. Git history preserves deleted implementation and documentation; no compatibility aliases are provided.

The direct runtime dependency list is FastMCP, PyImageJ, Pillow, and NumPy. The project no longer declares Pydantic directly merely for custom output models.

## 12. Testing strategy

### Contract tests

- Start the MCP server through an in-process or stdio FastMCP client.
- Assert that exactly the nine approved tool names are exposed.
- Assert the stable argument schemas and absence of legacy tools.
- Verify without Fiji that Python logging and simulated redirected output never corrupt stdio JSON-RPC.

### Unit tests

- Fiji-path and mode validation.
- Command search merging and bounded results.
- Duplicate command-name resolution and registry deduplication.
- Results-table pagination, ordering, duplicate/blank headings, defined-column gaps, and non-finite values.
- Bounded Java-object serialization, non-string map keys, cycles, and truncation.
- Error translation and known/unknown execution outcomes.
- Lifecycle/dispatch phase transitions, safe retry classification, health probing, and maximum attempt count.
- Deterministic headless active-plane/overlay and Results-table rendering.
- Screenshot same-size/different-size comparison and one-level pixel changes.
- Cancellation retaining the operation lock until a dispatched Java worker completes.

Unit tests mock only the thin bridge boundary. They do not recreate Fiji behavior in a second Python state model.

### Integration tests

Integration tests require a local Fiji installation and remain separately marked. They cover:

- Lazy startup and `get_state`.
- Failure injection before JVM startup, during startup, after successful startup, and after operation dispatch.
- Opening and saving a fixture image.
- ImageJ Macro and Groovy execution.
- Real stdio execution of ImageJ Macro output, Groovy `println`, and Java `System.out`, verifying that each leaves JSON-RPC intact.
- Searching for and invoking a known built-in command.
- Producing and reading a Results table.
- Active-image and Results screenshots.
- Before/after screenshot comparison.

### End-to-end acceptance examples

The README demonstrates three agent prompts:

1. Open an image, process it, and visually compare before and after.
2. Discover and run an already-installed Fiji plugin with parameters.
3. Measure objects and return the Results table as structured data.

## 13. Definition of done

The simplification is complete when:

- The server exposes exactly nine public tools.
- The old orchestration, templates, trace, installer, and custom-schema layers are removed.
- A user can install the package, set `FIJI_PATH`, paste one generic stdio configuration, and call `get_state`.
- The three acceptance examples work against a local Fiji installation.
- Unit and stdio contract tests pass without Fiji.
- Integration tests pass when `FIJI_PATH` is supplied.
- README and tool documentation describe only the new API and its trusted-code security model.
