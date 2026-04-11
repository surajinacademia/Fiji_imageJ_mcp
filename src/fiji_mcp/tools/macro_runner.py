"""Core execution tools for macro and file operations."""

from __future__ import annotations

from typing import Annotated

import scyjava as sj
from fastmcp.server.context import Context
from fastmcp.server.dependencies import OptionalCurrentContext
from mcp.types import ToolAnnotations
from pydantic import Field

from fiji_mcp.config.settings import load_settings
from fiji_mcp.fiji_bridge import get_bridge_status, get_ij, get_ij1
from fiji_mcp.mcp_instance import mcp
from fiji_mcp.schemas.tool_outputs import (
    BatchMacroStepFailure,
    BatchMacroStepSuccess,
    HealthCheckResult,
    MacroRunResult,
    OpenImageResult,
    RunBatchMacrosResult,
    SaveImageResult,
)
from fiji_mcp.utils.error_handler import FijiToolError, run_with_timeout, with_retries
from fiji_mcp.utils.path_policy import ensure_path_allowed, resolve_user_path

_OPERATION_COUNT = 0

_ANN_READ = ToolAnnotations(readOnlyHint=True, idempotentHint=True)
_ANN_MUTATE = ToolAnnotations(readOnlyHint=False, destructiveHint=False)

MacroCode = Annotated[
    str,
    Field(
        description='ImageJ macro language source, e.g. run("Gaussian Blur...", "sigma=2");',
        examples=['return "ok";', 'run("Add Noise...");'],
    ),
]
ImagePath = Annotated[
    str,
    Field(
        description="Absolute or user-expandable path to an image file Fiji can open.",
        examples=["/data/sample.tif", "~/Images/cells.png"],
    ),
]
SavePath = Annotated[
    str,
    Field(
        description="Destination path; parent directories are created if missing.",
        examples=["/tmp/out.tif", "~/results/stack.tif"],
    ),
]
FormatHint = Annotated[
    str,
    Field(
        description="ImageJ saveAs format hint (tiff, png, jpeg, etc.).",
        examples=["tiff", "png"],
    ),
]
RetryCount = Annotated[
    int,
    Field(
        ge=0,
        le=10,
        description="Number of retries on transient Java bridge failures (macro tools).",
    ),
]
MacroList = Annotated[
    list[str],
    Field(description="Ordered list of macro strings; each should be non-empty after strip()."),
]


def _check_macro_length(macro_code: str) -> None:
    limit = load_settings().max_macro_chars
    if len(macro_code) > limit:
        raise FijiToolError(
            f"macro_code is {len(macro_code)} characters; limit is FIJI_MAX_MACRO_CHARS={limit}. "
            "Split work into smaller macros or raise the limit only if you trust the caller."
        )


def _record_operation() -> None:
    global _OPERATION_COUNT
    _OPERATION_COUNT += 1
    settings = load_settings()
    if _OPERATION_COUNT % max(1, settings.gc_every_n_operations) == 0:
        system = sj.jimport("java.lang.System")
        system.gc()


@mcp.tool(
    annotations=_ANN_READ,
    description=(
        "Return runtime health: Fiji path, headless/GUI mode, ImageJ version, and configured "
        "operation timeout. Use before long jobs to confirm the bridge is alive."
    ),
)
def health_check() -> HealthCheckResult:
    """Return runtime health details for Fiji bridge and server config."""
    settings = load_settings()

    def _check() -> HealthCheckResult:
        ij = get_ij()
        app = ij.getApp()
        return HealthCheckResult(
            initialized=True,
            fiji_path=get_bridge_status()["fiji_path"],
            mode=get_bridge_status()["mode"],
            imagej_version=str(app.getVersion()),
            operation_timeout_seconds=settings.operation_timeout_seconds,
        )

    return run_with_timeout(_check, timeout_seconds=settings.operation_timeout_seconds)


@mcp.tool(
    annotations=_ANN_MUTATE,
    description=(
        "Execute ImageJ1 macro text in the current Fiji session. Returns macro return value "
        "and a tail of the ImageJ log. Prefer small, focused macros; increase timeout for heavy I/O."
    ),
)
def run_macro(macro_code: MacroCode, retries: RetryCount = 2) -> MacroRunResult:
    """Execute ImageJ macro code and return macro result/log context."""
    if not macro_code or not macro_code.strip():
        raise FijiToolError(
            "macro_code is empty. Paste a non-empty macro body (e.g. run('Measure');) and retry."
        )
    _check_macro_length(macro_code)

    def _run() -> MacroRunResult:
        ij1 = get_ij1()
        result = ij1.runMacro(macro_code)
        log_text = ij1.getLog() if hasattr(ij1, "getLog") else ""
        _record_operation()
        return MacroRunResult(
            result="" if result is None else str(result),
            log_tail="" if log_text is None else str(log_text)[-4000:],
        )

    return with_retries(lambda: run_with_timeout(_run), retries=retries)


@mcp.tool(
    annotations=_ANN_MUTATE,
    description=(
        "Open an image from disk in Fiji and show it as the active window. "
        "Verify the path exists on the MCP host before calling."
    ),
)
def open_image(path: ImagePath) -> OpenImageResult:
    """Open an image file in Fiji and make it the active image."""
    settings = load_settings()
    file_path = resolve_user_path(path)
    ensure_path_allowed(file_path, settings, operation="open_image")
    if not file_path.exists():
        raise FijiToolError(
            f"Image file not found: {file_path}. "
            "Confirm FIJI_PATH host can read this path (expand ~) and the file exists."
        )

    def _open() -> OpenImageResult:
        ij1 = get_ij1()
        image_plus = ij1.openImage(str(file_path))
        if image_plus is None:
            raise FijiToolError(
                f"Fiji failed to open image: {file_path}. "
                "Try a format Fiji supports, or open via Bio-Formats with an appropriate macro."
            )
        # image_plus.show() blocks indefinitely in headless mode (no AWT event loop).
        if load_settings().fiji_mode == "headless":
            window_manager = sj.jimport("ij.WindowManager")
            window_manager.setTempCurrentImage(image_plus)
        else:
            image_plus.show()
        _record_operation()
        return OpenImageResult(
            title=str(image_plus.getTitle()),
            width=int(image_plus.getWidth()),
            height=int(image_plus.getHeight()),
            path=str(file_path),
        )

    return with_retries(lambda: run_with_timeout(_open), retries=1)


@mcp.tool(
    annotations=_ANN_MUTATE,
    description=(
        "Save the currently active image to disk using ImageJ's saveAs. "
        "Requires an image window to be frontmost in Fiji."
    ),
)
def save_image(path: SavePath, format_hint: FormatHint = "tiff") -> SaveImageResult:
    """Save the current active image to disk in the requested format."""
    settings = load_settings()
    output_path = resolve_user_path(path)
    ensure_path_allowed(output_path, settings, operation="save_image")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    def _save() -> SaveImageResult:
        ij1 = get_ij1()
        image_plus = ij1.getImage()
        if image_plus is None:
            raise FijiToolError(
                "No active image to save. Use open_image or click an image window in Fiji, then retry."
            )
        ij1.saveAs(image_plus, format_hint, str(output_path))
        _record_operation()
        return SaveImageResult(
            path=str(output_path),
            title=str(image_plus.getTitle()),
            format=format_hint,
        )

    return with_retries(lambda: run_with_timeout(_save), retries=1)


@mcp.tool(
    annotations=_ANN_MUTATE,
    description=(
        "Run several macros in sequence. On failure, behavior depends on continue_on_error: "
        "either stop or record the error and continue. Each successful step returns the same "
        "shape as run_macro."
    ),
)
async def run_batch_macros(
    macros: MacroList,
    continue_on_error: Annotated[
        bool,
        Field(description="If true, record per-step errors and continue; if false, stop on first failure."),
    ] = False,
    retries_per_step: Annotated[
        int,
        Field(ge=0, le=10, description="Retries passed to run_macro for each non-empty step."),
    ] = 1,
    ctx: Context | None = OptionalCurrentContext(),
) -> RunBatchMacrosResult:
    """Run a group of macros as one batch operation."""
    if not macros:
        raise FijiToolError(
            'macros list is empty. Pass at least one macro string (e.g. ["run(\\"Measure\\");"]).'
        )

    results: list[BatchMacroStepSuccess | BatchMacroStepFailure] = []
    total = len(macros)
    for index, macro in enumerate(macros, start=1):
        if ctx is not None:
            try:
                await ctx.report_progress(index - 1, total, f"Batch step {index}/{total}")
                await ctx.debug(f"Running batch macro step {index} of {total}")
            except AttributeError:
                pass

        code = macro.strip()
        if not code:
            message = f"Batch step {index} contains empty macro text"
            if continue_on_error:
                results.append(BatchMacroStepFailure(step=index, error=message))
                continue
            raise FijiToolError(message)

        try:
            macro_result = run_macro(code, retries=retries_per_step)
            results.append(BatchMacroStepSuccess(step=index, result=macro_result))
        except Exception as error:
            results.append(BatchMacroStepFailure(step=index, error=str(error)))
            if not continue_on_error:
                break

    failures = [entry for entry in results if not entry.ok]
    return RunBatchMacrosResult(
        ok=len(failures) == 0,
        total_steps=len(macros),
        completed_steps=len(results),
        failed_steps=len(failures),
        results=results,
    )
