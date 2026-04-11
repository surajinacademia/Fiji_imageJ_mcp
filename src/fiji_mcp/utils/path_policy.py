"""Host filesystem policy for open/save tools (optional root allowlist)."""

from __future__ import annotations

from pathlib import Path

from fiji_mcp.config.settings import Settings
from fiji_mcp.utils.error_handler import FijiToolError


def resolve_user_path(raw: str) -> Path:
    """Expand ``~`` and return an absolute, normalized path (non-strict resolve)."""
    expanded = Path(raw).expanduser()
    try:
        return expanded.resolve(strict=False)
    except (OSError, RuntimeError) as error:
        raise FijiToolError(f"Invalid path {raw!r}: {error}") from error


def ensure_path_allowed(resolved: Path, settings: Settings, *, operation: str) -> None:
    """If ``FIJI_DATA_ROOTS`` is set, require ``resolved`` to lie under one of those roots."""
    roots = settings.data_roots
    if not roots:
        return
    ok = any(resolved == root or resolved.is_relative_to(root) for root in roots)
    if not ok:
        roots_display = ", ".join(str(r) for r in roots)
        raise FijiToolError(
            f"{operation} path is outside allowed directories (FIJI_DATA_ROOTS={roots_display}): "
            f"{resolved}. Adjust FIJI_DATA_ROOTS or use a path under an allowed root."
        )
