# Fiji MCP nine-tool reference

The server starts Fiji lazily on the first Fiji-backed call. `FIJI_PATH` is
required and must identify a Fiji root containing `jars/` and `plugins/`.
`FIJI_MODE` is optional: it defaults to `headless` and may be `gui` when a
desktop-only operation is necessary. Before startup, the bridge prefers one
valid current-platform JVM bundled under `FIJI_PATH/java/`, preserves an
existing SciJava JVM selection, and otherwise falls back to SciJava's normal
JVM selection.

All Fiji operations share one process-wide lock. The server exposes exactly the
following nine tools.

## `get_state()`

Returns a live state dictionary with:

- `lifecycle`, `version`, and `mode`.
- `active_image`, or `null`, and `open_images`; each image summary has `title`,
  `width`, `height`, `channels`, `slices`, `frames`, and `bit_depth`.
- `results` containing its `columns` and `total_rows`.

Use this to confirm setup and inspect Fiji before deciding whether an uncertain
mutation should be repeated.

## `search_commands(query: str, limit: int = 20)`

Searches registered SciJava commands and ImageJ1 menu commands. `query` may be
empty; `limit` must be from 1 through 100. The response contains `query`,
`returned`, `total`, and ordered `commands`. Each command record includes
`name`, `class_name`, `menu_path`, `family`, `invocation_route`, and `inputs`.
SciJava input records provide `name`, `type`, `required`, and `description`.

`invocation_route` is `structured_parameters`, `legacy_options`, or
`script_fallback`. Search first when the plugin name or its accepted route is
unclear.

## `run_command(name: str, parameters: dict[str, Any] | None = None, options: str | None = None)`

Runs one registered command. `name` resolves in this order: exact class name,
exact case-sensitive display name, then a unique case-insensitive display name.
`parameters` is for compatible SciJava commands; `options` is for an ImageJ1
options string. They are mutually exclusive. Commands whose inputs require a
script fallback return an actionable error instead of guessing.

Returns `name`, `class_name`, `family`, `invocation_route`, JSON-safe `outputs`,
the final 4,000-character `log_tail`, and `active_image` metadata after
execution.

## `run_script(language: Literal["ijm", "groovy"], code: str)`

Runs one non-empty ImageJ Macro (`ijm`) or Groovy (`groovy`) script. It is the
escape hatch for ROI work, unusual plugin APIs, complex Java inputs, and
already-installed plugins that are scriptable but not representable as a
registered structured command.

Returns `language`, a bounded JSON-safe `result`, the final
4,000-character `log_tail`, and `active_image` metadata. IJM and Groovy are
trusted arbitrary local code: they are not a plugin installer or a sandbox.

## `open_image(path: str)`

Opens an existing local image and makes it current. Returns the resolved `path`
and an `image` metadata summary. Basic formats use Fiji directly; use a
registered command or script for formats that need an installed importer.

## `save_image(path: str)`

Saves the current image to the exact requested local filename. Parent
directories are created. Only these exact lowercase suffixes are supported:
`.tif`, `.tiff`, `.jpg`, `.png`, `.gif`, `.bmp`, `.fits`, `.pgm`, `.zip`,
`.raw`, and `.avi`. `.jpeg` and case variants are rejected because ImageJ
rewrites those filename spellings. An existing exact output path is also
rejected: `save_image` never overwrites a file. Returns the exact resolved
`path`, the extension without its leading dot as `format`, and `image` metadata
summary.

## `get_results(offset: int = 0, limit: int = 500)`

Reads an ordered page from Fiji's live Results table. `offset` must be
non-negative; `limit` must be from 1 through 5,000. The response has original
`columns`, ordered-array `rows`, `offset`, `returned`, and `total_rows`.

Rows deliberately remain arrays so duplicate or blank ImageJ column headings
are preserved. `null` is reserved for undefined ImageJ column slots
(`columnExists(index) == false`). Defined cells reflect the ResultsTable:
finite numeric cells are JSON numbers, stored text cells are strings (including
possible empty-string placeholders), and numeric infinities become
`"Infinity"` or `"-Infinity"`. Numeric `NaN` and NaN-encoded empty numeric
slots both become `"NaN"`, because the public API cannot distinguish them.
With NaN-empty disabled, empty numeric slots surface as `0`. Page through this
tool for complete data; rendered Results screenshots show only the first 100
rows.

## `screenshot(target: Literal["active_image", "results"], save_path: str | None = None)`

Renders one target as a native MCP PNG image block plus structured metadata.
`target` is required and must be `active_image` or `results`. If `save_path` is
provided, the identical returned PNG bytes are written there and the metadata
includes `save_path`.

- `active_image` renders the current C/Z/T plane with its display range, LUT,
  visible overlay, and ROI. Its metadata includes `target`, `current_c`,
  `current_z`, `current_t`, `overlay_present`, `roi_present`, `width`, and
  `height`.
- `results` renders a deterministic table. Its metadata includes `target`,
  `columns`, `total_rows`, `rendered_rows`, `omitted_rows`, `width`, and
  `height`.

Neither target is enlarged; dimensions over 2,048 pixels are reduced
proportionally. To compare a workflow visually, save one capture before the
operation and another after it, then use their paths with `compare_screenshots`.

## `compare_screenshots(before_path: str, after_path: str, save_path: str | None = None)`

Loads two local raster paths without starting Fiji and returns a native MCP PNG
with Before and After panels; equal-sized inputs also receive an absolute-
difference panel. Structured metadata always contains `before_dimensions`,
`after_dimensions`, `dimensions_match`, `panels`, `width`, and `height`.
Equal-sized inputs additionally contain `mae`, `rmse`, and
`changed_pixel_fraction`. An optional `save_path` receives the exact comparison
PNG bytes.

The comparison does not resize or crop source images for metrics. When source
dimensions differ, it returns the side-by-side visual and dimensions but omits
pixel metrics.

## Retry, output, and GUI behavior

Read-only work may receive one automatic retry only for an explicitly
allowlisted transient failure: `InterruptedError`, `OSError` with `EINTR`, or a
live-JVM Java `ConcurrentModificationException`. JVM initialization and all
mutations are never retried automatically. A command, script, image open, or
image save that fails after dispatch can have an unknown outcome; inspect
`get_state` or `screenshot` before choosing whether to repeat it.

Python diagnostics and ordinary Java output go to stderr so stdio stdout stays
valid MCP JSON-RPC. Trusted script code that deliberately writes to native file
descriptor 1 can bypass Java stream redirection. GUI-only plugins, dialogs, and
mouse or keyboard automation are outside the headless contract; use an
installed scriptable route or explicitly run with `FIJI_MODE=gui` when the
plugin supports it.
