"""Process-wide logging for stdio MCP: logs must go to stderr only."""

from __future__ import annotations

import logging
import os
import sys

_configured = False


def configure_server_logging() -> None:
    """Attach a stderr handler and set levels from ``FIJI_LOG_LEVEL`` (default ``WARNING``).

    Stdio MCP reserves stdout for JSON-RPC; this keeps library noise off stdout.
    """
    global _configured
    if _configured:
        return
    _configured = True

    level_name = (os.environ.get("FIJI_LOG_LEVEL") or "WARNING").strip().upper()
    level = getattr(logging, level_name, logging.WARNING)

    root = logging.getLogger()
    root.setLevel(level)

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"),
    )
    root.addHandler(handler)

    for noisy in ("urllib3", "httpx", "httpcore", "imagej", "jpype"):
        logging.getLogger(noisy).setLevel(max(logging.WARNING, level))
