"""Environment-backed runtime settings for Fiji MCP."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

VALID_MODES = {"gui", "headless", "auto", "smart"}


@dataclass(frozen=True)
class Settings:
    """Runtime settings loaded from environment variables."""

    fiji_path: str | None
    fiji_java_home: str | None
    fiji_mode: str
    operation_timeout_seconds: float
    screenshot_max_dim: int
    screenshot_quality: int
    screenshot_cache_size: int
    gc_every_n_operations: int
    test_image_path: str | None
    max_macro_chars: int
    data_roots: tuple[Path, ...]


def _parse_mode(raw_mode: str | None) -> str:
    mode = (raw_mode or "smart").strip().lower()
    if mode not in VALID_MODES:
        valid = ", ".join(sorted(VALID_MODES))
        raise ValueError(f"Invalid FIJI_MODE={raw_mode!r}. Expected one of: {valid}")
    return mode


def _parse_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as error:
        raise ValueError(f"Environment variable {name} must be an integer") from error


def _parse_int_bounded(name: str, default: int, *, lo: int, hi: int) -> int:
    value = _parse_int(name, default)
    if not lo <= value <= hi:
        raise ValueError(
            f"Environment variable {name} must be between {lo} and {hi} (got {value})"
        )
    return value


def _parse_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError as error:
        raise ValueError(f"Environment variable {name} must be numeric") from error


def _parse_float_bounded(name: str, default: float, *, lo: float, hi: float) -> float:
    value = _parse_float(name, default)
    if not lo <= value <= hi:
        raise ValueError(
            f"Environment variable {name} must be between {lo} and {hi} (got {value})"
        )
    return value


def _parse_data_roots() -> tuple[Path, ...]:
    """Optional allowlist: ``FIJI_DATA_ROOTS`` is ``os.pathsep``-separated absolute or user paths."""
    raw = os.environ.get("FIJI_DATA_ROOTS", "").strip()
    if not raw:
        return ()
    seen: set[str] = set()
    roots: list[Path] = []
    for part in raw.split(os.pathsep):
        p = part.strip()
        if not p:
            continue
        try:
            resolved = Path(p).expanduser().resolve(strict=False)
        except (OSError, RuntimeError) as error:
            raise ValueError(f"Invalid FIJI_DATA_ROOTS entry {p!r}: {error}") from error
        key = os.path.normcase(str(resolved))
        if key not in seen:
            seen.add(key)
            roots.append(resolved)
    return tuple(roots)


def load_settings() -> Settings:
    """Load settings once from environment variables."""
    fiji_path = os.environ.get("FIJI_PATH")
    if fiji_path:
        fiji_path = str(Path(fiji_path).expanduser())

    return Settings(
        fiji_path=fiji_path,
        fiji_java_home=os.environ.get("FIJI_JAVA_HOME"),
        fiji_mode=_parse_mode(os.environ.get("FIJI_MODE")),
        operation_timeout_seconds=_parse_float_bounded(
            "FIJI_OPERATION_TIMEOUT_SECONDS", 60.0, lo=1.0, hi=86400.0
        ),
        screenshot_max_dim=_parse_int_bounded(
            "FIJI_SCREENSHOT_MAX_DIM", 1920, lo=64, hi=8192
        ),
        screenshot_quality=_parse_int_bounded(
            "FIJI_SCREENSHOT_QUALITY", 85, lo=1, hi=100
        ),
        screenshot_cache_size=_parse_int_bounded(
            "FIJI_SCREENSHOT_CACHE_SIZE", 5, lo=1, hi=500
        ),
        gc_every_n_operations=_parse_int_bounded(
            "FIJI_GC_EVERY_N_OPERATIONS", 10, lo=1, hi=10_000
        ),
        test_image_path=os.environ.get("FIJI_TEST_IMAGE"),
        max_macro_chars=_parse_int_bounded(
            "FIJI_MAX_MACRO_CHARS", 500_000, lo=4096, hi=10_000_000
        ),
        data_roots=_parse_data_roots(),
    )
