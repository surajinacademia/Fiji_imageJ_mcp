"""Workflow execution helpers for multi-step autonomous Fiji pipelines."""

from __future__ import annotations

from typing import Annotated, Any, cast

from fastmcp.server.context import Context
from fastmcp.server.dependencies import OptionalCurrentContext
from mcp.types import ToolAnnotations
from pydantic import Field

from fiji_mcp.mcp_instance import mcp
from fiji_mcp.schemas.tool_outputs import (
    RunWorkflowResult,
    WorkflowStepFailure,
    WorkflowStepInput,
    WorkflowStepSuccess,
)
from fiji_mcp.tools.macro_runner import run_macro
from fiji_mcp.tools.screenshot import screenshot_fiji
from fiji_mcp.utils.error_handler import FijiToolError

_ANN_MUTATE = ToolAnnotations(readOnlyHint=False, destructiveHint=False)

WorkflowSteps = Annotated[
    list[WorkflowStepInput | dict[str, Any]],
    Field(
        description=(
            'Each step: {"macro", "screenshot_after", '
            '"screenshot_capture": "full_screen"|"active_image"|"results_table"}.'
        ),
    ),
]


@mcp.tool(
    annotations=_ANN_MUTATE,
    description=(
        "Run a scripted pipeline: each step runs a macro, optionally followed by a screenshot. "
        "Supports MCP progress when the client requests it. Use verify_each_step=false for faster runs."
    ),
)
async def run_workflow(
    steps: WorkflowSteps,
    verify_each_step: Annotated[
        bool,
        Field(description="If true, append screenshot after each step when screenshot_after allows."),
    ] = True,
    continue_on_error: Annotated[
        bool,
        Field(description="If false, stop after the first failing step and return partial results."),
    ] = False,
    ctx: Context | None = OptionalCurrentContext(),
) -> RunWorkflowResult:
    """Execute a multi-step workflow with optional screenshot verification."""
    if not steps:
        raise FijiToolError(
            'steps is empty. Pass a list like [{"macro": "run(\\"Measure\\");"}].'
        )

    coerced_steps: list[WorkflowStepInput] = [
        WorkflowStepInput.model_validate(s) if isinstance(s, dict) else cast("WorkflowStepInput", s)
        for s in steps
    ]

    results: list[WorkflowStepSuccess | WorkflowStepFailure] = []
    total = len(coerced_steps)
    for index, step in enumerate(coerced_steps, start=1):
        if ctx is not None:
            try:
                await ctx.report_progress(index - 1, total, f"Workflow step {index}/{total}")
                await ctx.debug(f"Fiji workflow step {index}: executing macro")
            except AttributeError:
                # OptionalCurrentContext / no MCP client (e.g. asyncio.run from a script).
                pass

        command = str(step.macro).strip()
        if not command:
            message = f"Step {index} is missing a non-empty 'macro' field."
            if continue_on_error:
                results.append(WorkflowStepFailure(step=index, error=message))
                continue
            raise FijiToolError(message)

        try:
            step_result = run_macro(command)
            entry: WorkflowStepSuccess
            if verify_each_step and step.screenshot_after:
                shot = screenshot_fiji(capture_mode=step.screenshot_capture)
                entry = WorkflowStepSuccess(step=index, result=step_result, screenshot=shot)
            else:
                entry = WorkflowStepSuccess(step=index, result=step_result, screenshot=None)
            results.append(entry)
        except Exception as error:
            results.append(WorkflowStepFailure(step=index, error=str(error)))
            if not continue_on_error:
                return RunWorkflowResult(
                    ok=False,
                    completed_steps=index - 1,
                    failed_step=index,
                    results=results,
                )

    failed = [item for item in results if not item.ok]
    return RunWorkflowResult(
        ok=len(failed) == 0,
        total_steps=len(coerced_steps),
        failed_steps=len(failed),
        results=results,
    )
