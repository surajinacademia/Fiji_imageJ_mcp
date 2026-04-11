"""Structured parsing, screenshot comparison, macro templates, and session trace."""

from __future__ import annotations

from typing import Annotated, Literal

from mcp.types import ToolAnnotations
from pydantic import Field

from fiji_mcp.mcp_instance import mcp
from fiji_mcp.schemas.tool_outputs import (
    ClearSessionTraceResult,
    CompareScreenshotsResult,
    GetMacroTemplateResult,
    GetSessionTraceResult,
    ListMacroTemplatesResult,
    MacroTemplateEntry,
    ParseMacroOutputResult,
    SessionEventEntry,
)
from fiji_mcp.tools.discovery import open_images_snapshot
from fiji_mcp.utils import result_parser as _macro_text_parser
from fiji_mcp.utils.error_handler import FijiToolError
from fiji_mcp.utils.image_compare import compare_screenshot_base64_pair
from fiji_mcp.utils.session_state import (
    clear_tool_events,
    get_tool_events,
    log_tool_event,
)
from fiji_mcp.utils.template_catalog import get_template, list_templates

_ANN_READ = ToolAnnotations(readOnlyHint=True, idempotentHint=True)

FormatHintArg = Annotated[
    Literal["auto", "json", "csv", "key_value", "imagej_table", "numbers_only"],
    Field(
        description=(
            "auto: try JSON, then ImageJ-style TSV, CSV, key=value lines, then numbers. "
            "json/csv/key_value/imagej_table/numbers_only: force a parser."
        ),
    ),
]


def parse_macro_output(
    text: Annotated[
        str, Field(description="Usually MacroRunResult.result or a log tail slice.")
    ],
    format_hint: FormatHintArg = "auto",
) -> ParseMacroOutputResult:
    """Parse measurement / statistics text into structured fields."""
    parsed = _macro_text_parser.parse_macro_output(text, format_hint)
    nums = parsed.get("numbers") or []
    coerced_nums: list[float] = []
    for x in nums:
        try:
            coerced_nums.append(float(x))
        except (TypeError, ValueError):
            continue
    result = ParseMacroOutputResult(
        format_detected=str(parsed.get("format_detected", "unknown")),
        parsed_json=parsed.get("json"),
        values=dict(parsed.get("values") or {}),
        rows=list(parsed.get("rows") or []),
        numbers=coerced_nums,
    )
    log_tool_event(
        "parse_macro_output",
        f"format={result.format_detected}",
        {"numbers": len(result.numbers), "rows": len(result.rows)},
    )
    return result


def compare_screenshots(
    image_base64_before: Annotated[
        str,
        Field(
            description="image_base64 from an earlier screenshot_fiji call (before step)."
        ),
    ],
    image_base64_after: Annotated[
        str,
        Field(description="image_base64 from screenshot_fiji after the operation."),
    ],
) -> CompareScreenshotsResult:
    """Build a before/after composite and numeric change metrics."""
    try:
        stats, mime, b64, cw, ch = compare_screenshot_base64_pair(
            image_base64_before, image_base64_after
        )
    except Exception as error:
        raise FijiToolError(
            "Failed to decode or compare images. Pass raw base64 from screenshot_fiji without data URLs. "
            f"Detail: {error}"
        ) from error

    log_tool_event(
        "compare_screenshots",
        f"mae={stats.mean_abs_error:.6f} rmse={stats.rmse:.6f}",
        {"compare_width": stats.compare_width, "compare_height": stats.compare_height},
    )
    return CompareScreenshotsResult(
        mime_type=mime,
        format="jpeg",
        width=cw,
        height=ch,
        image_base64=b64,
        mean_abs_error=stats.mean_abs_error,
        rmse=stats.rmse,
        width_before=stats.width_before,
        height_before=stats.height_before,
        width_after=stats.width_after,
        height_after=stats.height_after,
        compare_width=stats.compare_width,
        compare_height=stats.compare_height,
    )


def list_macro_templates(
    category: Annotated[
        str | None,
        Field(
            description="Optional filter: filters, process, segment, analyze, image, annotate."
        ),
    ] = None,
) -> ListMacroTemplatesResult:
    """Return the curated template library (subset of common Fiji operations)."""
    raw = list_templates(category=category)
    entries = [MacroTemplateEntry.model_validate(t) for t in raw]
    result = ListMacroTemplatesResult(count=len(entries), templates=entries)
    log_tool_event(
        "list_macro_templates",
        f"count={result.count}",
        {"category": category},
    )
    return result


def get_macro_template(
    template_id: Annotated[
        str, Field(description="Stable id, e.g. gaussian_blur, analyze_particles.")
    ],
) -> GetMacroTemplateResult:
    """Return title, category, description, and example macro text for a template id."""
    row = get_template(template_id)
    if row is None:
        raise FijiToolError(
            f"Unknown template_id={template_id!r}. Call list_macro_templates() for ids."
        )
    tpl = MacroTemplateEntry.model_validate(row)
    log_tool_event("get_macro_template", tpl.id, {"title": tpl.title[:80]})
    return GetMacroTemplateResult(template=tpl)


def get_session_trace(
    limit: Annotated[
        int, Field(ge=1, le=500, description="Max recent events to return.")
    ] = 100,
    include_open_images: Annotated[
        bool,
        Field(
            description="If true, append current open-image windows (same data as list_open_images; no extra trace row).",
        ),
    ] = True,
) -> GetSessionTraceResult:
    """Session audit: ordered operations and current Fiji image windows."""
    raw_events = get_tool_events(limit=limit)
    events = [SessionEventEntry.model_validate(e) for e in raw_events]
    note = ""
    open_imgs = None
    if include_open_images:
        try:
            open_imgs = open_images_snapshot()
        except Exception as error:
            note = f"open_images_unavailable: {error}"
    return GetSessionTraceResult(
        returned_events=len(events),
        events=events,
        open_images=open_imgs,
        note=note,
    )


def clear_session_trace() -> ClearSessionTraceResult:
    """Remove all remembered session events for a fresh trace."""
    n = clear_tool_events()
    log_tool_event("clear_session_trace", f"cleared {n}", {})
    return ClearSessionTraceResult(cleared=n)


mcp.tool(
    annotations=_ANN_READ,
    description=(
        "Turn macro return text or a pasted Results snippet into structured JSON: "
        "detected format, key/value map, tabular rows, and/or extracted numbers. "
        "Prefer macros that `return` a small JSON or key=value string for best results."
    ),
)(parse_macro_output)

mcp.tool(
    annotations=_ANN_READ,
    description=(
        "Compare two screenshot_fiji payloads (before/after). Returns mean absolute error "
        "and RMSE on aligned grayscale patches plus a side-by-side JPEG for quick visual diff."
    ),
)(compare_screenshots)

mcp.tool(
    annotations=_ANN_READ,
    description="List bundled macro snippets (threshold, blur, Analyze Particles, etc.) with stable ids.",
)(list_macro_templates)

mcp.tool(
    annotations=_ANN_READ,
    description="Fetch one bundled macro template by id (from list_macro_templates).",
)(get_macro_template)

mcp.tool(
    annotations=_ANN_READ,
    description=(
        "Return recent tool invocations (run_macro, open_image, …) in order plus optional live open-image list. "
        "Trace is in-process only (resets when the MCP server restarts)."
    ),
)(get_session_trace)

mcp.tool(
    annotations=_ANN_READ,
    description="Clear the in-process session trace (does not close Fiji images).",
)(clear_session_trace)
