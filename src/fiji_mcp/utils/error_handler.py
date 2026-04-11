"""Execution helpers for retries and timeout-aware tool behavior."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

from fiji_mcp.config.settings import load_settings
from fiji_mcp.utils.java_errors import friendly_java_hint

T = TypeVar("T")


class FijiToolError(RuntimeError):
    """Structured tool-level error with actionable guidance."""


def run_with_timeout(func: Callable[[], T], timeout_seconds: float | None = None) -> T:
    """Run Fiji/Java work on the caller thread (required for JPype + AWT).

    ``timeout_seconds`` is accepted for API compatibility but cannot interrupt blocked Java calls.
    """
    _ = (
        timeout_seconds
        if timeout_seconds is not None
        else load_settings().operation_timeout_seconds
    )
    try:
        return func()
    except Exception as error:  # noqa: BLE001
        hint = friendly_java_hint(error)
        if hint and not isinstance(error, FijiToolError):
            raise FijiToolError(f"{hint} (Java error: {error})") from error
        raise


def with_retries(
    func: Callable[[], T], retries: int = 2, base_delay: float = 0.25
) -> T:
    """Retry a callable for transient failures with exponential backoff."""
    attempt = 0
    while True:
        attempt += 1
        try:
            return func()
        except Exception:
            if attempt > retries:
                raise
            time.sleep(base_delay * (2 ** (attempt - 1)))
