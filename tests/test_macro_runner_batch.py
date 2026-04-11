"""Unit tests for batch macro orchestration."""

from __future__ import annotations

import pytest

from fiji_mcp.schemas.tool_outputs import MacroRunResult
from fiji_mcp.tools import macro_runner
from fiji_mcp.utils.error_handler import FijiToolError


@pytest.mark.asyncio
async def test_run_batch_macros_requires_steps() -> None:
    with pytest.raises(FijiToolError):
        await macro_runner.run_batch_macros([], ctx=None)


@pytest.mark.asyncio
async def test_run_batch_macros_continue_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_run_macro(macro_code: str, retries: int = 1) -> MacroRunResult:
        if "bad" in macro_code:
            raise RuntimeError("broken")
        return MacroRunResult(result=macro_code, log_tail="")

    monkeypatch.setattr(macro_runner, "run_macro", _fake_run_macro)
    result = await macro_runner.run_batch_macros(
        ["good", "bad", "good-two"],
        continue_on_error=True,
        retries_per_step=2,
        ctx=None,
    )
    assert result.ok is False
    assert result.total_steps == 3
    assert result.completed_steps == 3
    assert result.failed_steps == 1
