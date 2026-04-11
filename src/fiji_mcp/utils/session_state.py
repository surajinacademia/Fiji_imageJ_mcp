"""In-process session trace: tool invocations in order (MCP server lifetime)."""

from __future__ import annotations

import contextvars
import threading
from collections import deque
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

_macro_trace_suppress = contextvars.ContextVar(
    "fiji_mcp_macro_trace_suppress", default=False
)

_MAX_EVENTS = 500


@dataclass(frozen=True)
class SessionEvent:
    seq: int
    tool: str
    summary: str
    detail: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "tool": self.tool,
            "summary": self.summary,
            "detail": dict(self.detail),
        }


_lock = threading.Lock()
_events: deque[SessionEvent] = deque(maxlen=_MAX_EVENTS)
_seq = 0


@contextmanager
def suppress_macro_tool_trace() -> Iterator[None]:
    """Disable ``run_macro`` session rows while nested tools (batch/workflow) log their own steps."""
    tok = _macro_trace_suppress.set(True)
    try:
        yield
    finally:
        _macro_trace_suppress.reset(tok)


def macro_trace_suppressed() -> bool:
    return _macro_trace_suppress.get()


def log_tool_event(
    tool: str, summary: str, detail: dict[str, Any] | None = None
) -> None:
    """Append one trace row (bounded deque). Safe from multiple threads."""
    global _seq
    payload = dict(detail) if detail else {}
    with _lock:
        _seq += 1
        _events.append(
            SessionEvent(seq=_seq, tool=tool, summary=summary, detail=payload)
        )


def clear_tool_events() -> int:
    """Drop all events; returns number cleared. Sequence numbers restart at zero for a fresh trace."""
    global _seq
    with _lock:
        n = len(_events)
        _events.clear()
        _seq = 0
        return n


def get_tool_events(limit: int = 100) -> list[dict[str, Any]]:
    """Most recent ``limit`` events in chronological order."""
    if limit < 1:
        limit = 1
    with _lock:
        snap = list(_events)
    return [e.to_dict() for e in snap[-limit:]]
