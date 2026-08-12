# Demo-image Fiji integration design

Status: approved for implementation on 2026-08-12.

## Goal

Prove the nine-tool MCP against representative real microscopy images and fix
Groovy so it sees the active image in headless Fiji. Keep the suite small,
repeatable, and useful as a regression gate.

## Groovy execution

`open_image` binds the headless current image to the bridge's Java thread.
PyImageJ's current `run_script` convenience method schedules Groovy on a
SciJava worker thread, where `WindowManager.getCurrentImage()` is empty.

The server will replace that Groovy path with a private synchronous runner:

1. Build a SciJava `ScriptInfo` from the trusted Groovy source.
2. Create and initialize its `ScriptModule`.
3. Run the module synchronously inside the existing `run_mutation` dispatch.
4. Return the module's declared `#@output` values through the existing bounded
   serializer.
5. Capture the module error writer. If it contains a script failure, raise a
   bounded `script_failed` `FijiError` with `Outcome.UNKNOWN`, because arbitrary
   trusted code may have changed Fiji state before failing.

This preserves the public `run_script(language="groovy", code=...)` contract,
keeps declared outputs, and evaluates on the thread that owns the active image.
Direct `ScriptEngine.eval` is rejected because it loses SciJava parameter and
output processing. Rebinding the image on an asynchronous worker is rejected
because worker selection and cleanup are brittle.

## Tracked fixtures

Only these three PNG files will be committed:

- `demo_images/img00.png`: 512 x 512 RGB image for Groovy, command execution,
  screenshots, and comparison.
- `demo_images/img00_masks.png`: 512 x 512 16-bit label image for mask
  statistics and Results-table handling.
- `demo_images/segmentation_comparison.png`: 2357 x 1219 RGBA image for the
  bounded large-image screenshot path.

The other 22 PNG demo images remain local and are moved to a recoverable
temporary directory rather than committed or deleted.

## Test coverage

Focused unit tests will first demonstrate the existing failure and then cover:

- synchronous Groovy module execution and preservation of `#@output` values;
- dispatch through the new helper instead of `ij.py.run_script`;
- bounded script-error reporting with `Outcome.UNKNOWN`.

Three real-Fiji integration workflows will use the tracked fixtures:

1. **RGB workflow:** open `img00.png`; prove Groovy sees its title and
   dimensions; capture a before screenshot; find and run the exact Gaussian
   Blur command `ij.plugin.filter.GaussianBlur` with `sigma=2`; capture an after
   screenshot; verify the comparison reports changed pixels. The source
   fixture must remain byte-identical.
2. **Mask workflow:** open `img00_masks.png`; use Groovy to compute deterministic
   label statistics; populate and read the Results table; render a Results
   screenshot. Assert 16-bit handling, maximum label 221, and 202,807 nonzero
   pixels.
3. **Large screenshot workflow:** open `segmentation_comparison.png`; render the
   active image; assert its 2357 x 1219 source is proportionally bounded to
   2048 x 1059 and that source image metadata is unchanged.

Tests are marked `integration`, skip explicitly without a valid `FIJI_PATH`,
and run headless against `/Applications/Fiji` locally. CI continues to run the
non-integration suite without requiring Fiji.

## Verification and delivery

Implementation follows RED-GREEN TDD. Completion requires focused unit tests,
all three real-Fiji workflows, the full non-integration suite, Ruff formatting
and lint, mypy, and a final diff review. Changes may be committed locally but
must not be pushed or published.
