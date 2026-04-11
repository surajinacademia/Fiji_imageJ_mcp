"""Optional FastMCP ``Context`` injection across fastmcp versions."""

from __future__ import annotations

from typing import cast

try:
    from fastmcp.server.dependencies import (
        OptionalCurrentContext as OptionalCurrentContext,
    )
except ImportError:
    from docket.dependencies import Dependency
    from fastmcp.server.context import Context, _current_context

    class _OptionalCurrentContextDep(Dependency):
        async def __aenter__(self) -> Context | None:
            return _current_context.get()

    def OptionalCurrentContext() -> Context | None:  # noqa: N802
        return cast("Context | None", _OptionalCurrentContextDep())
