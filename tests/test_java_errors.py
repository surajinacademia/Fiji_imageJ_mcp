"""Tests for Java-side error hint mapping."""

from __future__ import annotations

import pytest

from fiji_mcp.utils.error_handler import FijiToolError, run_with_timeout
from fiji_mcp.utils.java_errors import friendly_java_hint


def test_friendly_java_hint_out_of_memory() -> None:
    class JavaOOM(Exception):
        pass

    hint = friendly_java_hint(JavaOOM("java.lang.OutOfMemoryError: Java heap space"))
    assert hint is not None
    assert "memory" in hint.lower()


def test_run_with_timeout_wraps_java_style_failure() -> None:
    class JavaOOM(Exception):
        pass

    def _boom() -> None:
        raise JavaOOM("java.lang.OutOfMemoryError: Java heap space")

    with pytest.raises(FijiToolError) as excinfo:
        run_with_timeout(_boom)
    assert "memory" in str(excinfo.value).lower()


def test_fiji_tool_error_not_double_wrapped() -> None:
    def _raise_fiji() -> None:
        raise FijiToolError("already friendly")

    with pytest.raises(FijiToolError, match="already friendly"):
        run_with_timeout(_raise_fiji)
