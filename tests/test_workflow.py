"""Workflow tests that validate control flow behavior."""

from __future__ import annotations

import pytest

from fiji_mcp.tools.workflow import run_workflow
from fiji_mcp.utils.error_handler import FijiToolError


@pytest.mark.asyncio
async def test_run_workflow_requires_steps() -> None:
    with pytest.raises(FijiToolError):
        await run_workflow([], ctx=None)


@pytest.mark.asyncio
async def test_run_workflow_requires_macro_field() -> None:
    with pytest.raises(FijiToolError):
        await run_workflow([{"name": "bad-step"}], continue_on_error=False, ctx=None)


@pytest.mark.asyncio
async def test_run_workflow_continue_on_error() -> None:
    result = await run_workflow(
        [{"name": "bad-step"}],
        continue_on_error=True,
        verify_each_step=False,
        ctx=None,
    )
    assert result.ok is False
    assert result.failed_steps == 1
