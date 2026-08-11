"""Isolated, synchronous runtime bridge for a single Fiji JVM."""

from __future__ import annotations

import errno
import json
import math
import os
import threading
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Literal, TypeVar

P = TypeVar("P")
T = TypeVar("T")

_MAX_DEPTH = 4
_MAX_ITEMS = 100
_MAX_STRING = 4_000
_MAX_JSON_BYTES = 65_536
_MISSING = object()


class Lifecycle(str, Enum):
    """The lifecycle of the process-local Fiji JVM."""

    NEW = "NEW"
    STARTING = "STARTING"
    READY = "READY"
    FAILED = "FAILED"


class Outcome(str, Enum):
    """Whether an operation is known not to have completed."""

    FAILED = "failed"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Settings:
    """The only runtime settings owned by the isolated bridge."""

    fiji_path: Path
    mode: Literal["headless", "gui"]


class FijiError(RuntimeError):
    """A structured error surfaced from the Fiji runtime boundary."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool,
        outcome: Outcome,
        recovery: str,
    ) -> None:
        self.code = code
        self.message = message
        self.retryable = retryable
        self.outcome = outcome
        self.recovery = recovery
        super().__init__(
            f"[{code}] {message} retryable={str(retryable).lower()} "
            f"outcome={outcome.value}. Next: {recovery}"
        )


def _qualified_python_type(value: Any) -> str:
    value_type = type(value)
    return f"{value_type.__module__}.{value_type.__qualname__}"


def _truncate_string(value: str) -> str:
    if len(value) <= _MAX_STRING:
        return value
    return value[: _MAX_STRING - 1] + "…"


def _summary(value: Any) -> str:
    """Produce a bounded diagnostic summary without inspecting object contents."""
    try:
        return str(value)[:_MAX_STRING]
    except Exception:
        return f"<{_qualified_python_type(value)}>"


def _java_type_name(value: Any) -> str | None:
    """Return the Java runtime class name when this is a Java proxy."""
    try:
        get_class = getattr(value, "getClass", None)
        if not callable(get_class):
            return None
        java_class = get_class()
        get_name = getattr(java_class, "getName", None)
        if not callable(get_name):
            return None
        name = get_name()
        return str(name) if name is not None else None
    except Exception:
        return None


def _call_named(value: Any, method_name: str, *args: Any) -> Any:
    """Call one explicitly supported Java API method, or return a sentinel."""
    try:
        method = getattr(value, method_name, None)
        if not callable(method):
            return _MISSING
        return method(*args)
    except Exception:
        return _MISSING


def _unbox_java_primitive(value: Any, java_type: str | None) -> Any:
    """Return a Python primitive for supported boxed Java values."""
    if java_type == "java.lang.Boolean":
        raw_value = _call_named(value, "booleanValue")
        return bool(raw_value) if raw_value is not _MISSING else _MISSING

    integer_methods = {
        "java.lang.Byte": "byteValue",
        "java.lang.Short": "shortValue",
        "java.lang.Integer": "intValue",
        "java.lang.Long": "longValue",
    }
    integer_method = integer_methods.get(java_type)
    if integer_method is not None:
        raw_value = _call_named(value, integer_method)
        if raw_value is _MISSING:
            return _MISSING
        try:
            return int(raw_value)
        except (TypeError, ValueError):
            return _MISSING

    float_methods = {
        "java.lang.Float": "floatValue",
        "java.lang.Double": "doubleValue",
    }
    float_method = float_methods.get(java_type)
    if float_method is not None:
        raw_value = _call_named(value, float_method)
        if raw_value is _MISSING:
            return _MISSING
        try:
            return float(raw_value)
        except (TypeError, ValueError):
            return _MISSING

    if java_type == "java.lang.Character":
        raw_value = _call_named(value, "charValue")
        if raw_value is _MISSING:
            return _MISSING
        return _truncate_string(str(raw_value))

    if java_type == "java.lang.String":
        raw_value = _call_named(value, "toString")
        if raw_value is _MISSING:
            return _MISSING
        return _truncate_string(str(raw_value))

    return _MISSING


def _integer_from_method(value: Any, method_name: str, *args: Any) -> int | None:
    raw_value = _call_named(value, method_name, *args)
    if raw_value is _MISSING:
        return None
    unboxed = _unbox_java_primitive(raw_value, _java_type_name(raw_value))
    if unboxed is not _MISSING:
        raw_value = unboxed
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return None


def _text_from_method(value: Any, method_name: str) -> str | None:
    raw_value = _call_named(value, method_name)
    if raw_value is _MISSING or raw_value is None:
        return None
    unboxed = _unbox_java_primitive(raw_value, _java_type_name(raw_value))
    if isinstance(unboxed, str):
        return unboxed
    return _truncate_string(str(raw_value))


def _image_summary_if_supported(
    image: Any, java_type: str | None
) -> dict[str, Any] | None:
    """Read fixed metadata only; intentionally never request image pixel data."""
    if java_type == "ij.ImagePlus" or (
        java_type is not None and java_type.endswith(".ImagePlus")
    ):
        title = _text_from_method(image, "getTitle")
        width = _integer_from_method(image, "getWidth")
        height = _integer_from_method(image, "getHeight")
        channels = _integer_from_method(image, "getNChannels")
        slices = _integer_from_method(image, "getNSlices")
        frames = _integer_from_method(image, "getNFrames")
        bit_depth = _integer_from_method(image, "getBitDepth")
        if None not in (title, width, height, channels, slices, frames, bit_depth):
            return {
                "title": title,
                "width": width,
                "height": height,
                "channels": channels,
                "slices": slices,
                "frames": frames,
                "bit_depth": bit_depth,
            }

    if java_type is not None and java_type.endswith("Dataset"):
        title = _text_from_method(image, "getName")
        dimensions = _integer_from_method(image, "numDimensions")
        bit_depth = _integer_from_method(image, "getValidBits")
        if title is None or dimensions is None or bit_depth is None or dimensions < 2:
            return None

        width = _integer_from_method(image, "dimension", 0)
        height = _integer_from_method(image, "dimension", 1)
        channels = _integer_from_method(image, "dimension", 2) if dimensions > 2 else 1
        slices = _integer_from_method(image, "dimension", 3) if dimensions > 3 else 1
        frames = _integer_from_method(image, "dimension", 4) if dimensions > 4 else 1
        if None not in (width, height, channels, slices, frames):
            return {
                "title": title,
                "width": width,
                "height": height,
                "channels": channels,
                "slices": slices,
                "frames": frames,
                "bit_depth": bit_depth,
            }
    return None


def image_summary(image: Any) -> dict[str, Any]:
    """Return bounded metadata for an ImagePlus or Dataset, never pixel arrays."""
    summary = _image_summary_if_supported(image, _java_type_name(image))
    if summary is None:
        raise TypeError("image_summary requires an ImagePlus or Dataset")
    return summary


def _results_table_summary(value: Any, java_type: str | None) -> dict[str, int] | None:
    if java_type != "ij.measure.ResultsTable" and not (
        java_type is not None and java_type.endswith(".ResultsTable")
    ):
        return None
    rows = _integer_from_method(value, "size")
    last_column = _integer_from_method(value, "getLastColumn")
    if rows is None or last_column is None:
        return None
    return {"rows": rows, "columns": last_column + 1}


def _bounded_java_iterator(iterator: Any) -> tuple[list[Any], int] | None:
    """Read at most the limit plus one item from a Java Iterator."""
    items: list[Any] = []
    for _ in range(_MAX_ITEMS):
        has_next = _call_named(iterator, "hasNext")
        if has_next is _MISSING:
            return None
        if not bool(has_next):
            return items, 0
        item = _call_named(iterator, "next")
        if item is _MISSING:
            return None
        items.append(item)

    has_next = _call_named(iterator, "hasNext")
    if has_next is _MISSING or not bool(has_next):
        return (items, 0) if has_next is not _MISSING else None
    if _call_named(iterator, "next") is _MISSING:
        return None
    return items, 1


def _bounded_python_iterable(value: Any) -> tuple[list[Any], int] | None:
    """Read at most the limit plus one item without materializing the iterable."""
    try:
        iterator = iter(value)
        items: list[Any] = []
        for _ in range(_MAX_ITEMS):
            item = next(iterator, _MISSING)
            if item is _MISSING:
                return items, 0
            items.append(item)
        return items, int(next(iterator, _MISSING) is not _MISSING)
    except Exception:
        return None


def _bounded_items(value: Any) -> tuple[list[Any], int] | None:
    iterator = _call_named(value, "iterator")
    if iterator is not _MISSING:
        return _bounded_java_iterator(iterator)
    return _bounded_python_iterable(value)


def _string_map_key(value: Any) -> str | None:
    if isinstance(value, str):
        return _truncate_string(value)
    unboxed = _unbox_java_primitive(value, _java_type_name(value))
    return unboxed if isinstance(unboxed, str) else None


def _convert_java_map(value: Any, *, depth: int, seen: set[int]) -> Any:
    entry_set = _call_named(value, "entrySet")
    if entry_set is _MISSING:
        return _MISSING
    bounded_entries = _bounded_items(entry_set)
    if bounded_entries is None:
        return _MISSING
    entries, truncated_items = bounded_entries

    pairs: list[tuple[Any, Any]] = []
    for entry in entries:
        key = _call_named(entry, "getKey")
        item = _call_named(entry, "getValue")
        if key is _MISSING or item is _MISSING:
            return _MISSING
        pairs.append((key, item))

    string_keys = [_string_map_key(key) for key, _ in pairs]
    if truncated_items == 0 and all(key is not None for key in string_keys):
        return {
            key: _convert(item, depth=depth + 1, seen=seen)
            for key, (_, item) in zip(string_keys, pairs, strict=True)
        }

    converted_entries = [
        {
            "key": _convert(key, depth=depth + 1, seen=seen),
            "value": _convert(item, depth=depth + 1, seen=seen),
        }
        for key, item in pairs
    ]
    if truncated_items:
        converted_entries.append({"truncated_items": truncated_items})
    return {"map_entries": converted_entries}


def _convert_java_collection(value: Any, *, depth: int, seen: set[int]) -> Any:
    bounded_items = _bounded_items(value)
    if bounded_items is None:
        return _MISSING
    items, truncated_items = bounded_items
    converted = [_convert(item, depth=depth + 1, seen=seen) for item in items]
    if truncated_items:
        converted.append({"truncated_items": truncated_items})
    return converted


def _stable_set_key(value: Any) -> str:
    return (
        f"{_java_type_name(value) or _qualified_python_type(value)}:{_summary(value)}"
    )


def _convert(value: Any, *, depth: int, seen: set[int]) -> Any:
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
        return value
    if isinstance(value, str):
        return _truncate_string(value)
    if depth >= _MAX_DEPTH:
        return {"truncated": True, "reason": "maximum depth reached"}

    identity = id(value)
    if identity in seen:
        return {"cycle": True}
    seen.add(identity)
    try:
        if isinstance(value, dict):
            items = list(value.items())
            if all(isinstance(key, str) for key, _ in items):
                converted = {
                    _truncate_string(key): _convert(item, depth=depth + 1, seen=seen)
                    for key, item in items[:_MAX_ITEMS]
                }
                if len(items) > _MAX_ITEMS:
                    converted["__truncated_items__"] = len(items) - _MAX_ITEMS
                return converted
            entries = [
                {
                    "key": _convert(key, depth=depth + 1, seen=seen),
                    "value": _convert(item, depth=depth + 1, seen=seen),
                }
                for key, item in items[:_MAX_ITEMS]
            ]
            if len(items) > _MAX_ITEMS:
                entries.append({"truncated_items": len(items) - _MAX_ITEMS})
            return {"map_entries": entries}

        if isinstance(value, (list, tuple)):
            items = list(value)
            converted = [
                _convert(item, depth=depth + 1, seen=seen)
                for item in items[:_MAX_ITEMS]
            ]
            if len(items) > _MAX_ITEMS:
                converted.append({"truncated_items": len(items) - _MAX_ITEMS})
            return converted

        if isinstance(value, (set, frozenset)):
            items = sorted(value, key=_stable_set_key)
            converted = [
                _convert(item, depth=depth + 1, seen=seen)
                for item in items[:_MAX_ITEMS]
            ]
            if len(items) > _MAX_ITEMS:
                converted.append({"truncated_items": len(items) - _MAX_ITEMS})
            return converted

        java_type = _java_type_name(value)
        unboxed = _unbox_java_primitive(value, java_type)
        if unboxed is not _MISSING:
            return _convert(unboxed, depth=depth, seen=seen)

        image = _image_summary_if_supported(value, java_type)
        if image is not None:
            return image

        table = _results_table_summary(value, java_type)
        if table is not None:
            return table

        converted_map = _convert_java_map(value, depth=depth, seen=seen)
        if converted_map is not _MISSING:
            return converted_map

        converted_collection = _convert_java_collection(value, depth=depth, seen=seen)
        if converted_collection is not _MISSING:
            return converted_collection

        return {
            "java_type": java_type or _qualified_python_type(value),
            "summary": _summary(value),
        }
    finally:
        seen.discard(identity)


def to_jsonable(value: Any) -> Any:
    """Convert a Fiji result into bounded, standard-JSON-compatible data."""
    converted = _convert(value, depth=0, seen=set())
    try:
        encoded = json.dumps(converted, ensure_ascii=False, allow_nan=False).encode(
            "utf-8"
        )
    except (TypeError, ValueError):
        encoded = b""
    if encoded and len(encoded) <= _MAX_JSON_BYTES:
        return converted
    return {
        "truncated": True,
        "reason": "serialized result exceeds 64 KiB",
        "java_type": _java_type_name(value) or _qualified_python_type(value),
        "summary": _summary(value),
    }


_OPERATION_LOCK = threading.RLock()
_LIFECYCLE = Lifecycle.NEW
_IJ: Any | None = None
_SETTINGS: Settings | None = None


def _is_eintr(error: BaseException) -> bool:
    return isinstance(error, InterruptedError) or (
        isinstance(error, OSError) and error.errno == errno.EINTR
    )


def _resolve_and_validate_root(raw_path: str) -> Path:
    root = Path(raw_path).expanduser().resolve()
    if not (root / "jars").is_dir() or not (root / "plugins").is_dir():
        raise FijiError(
            "invalid_configuration",
            f"{root} must contain jars/ and plugins/.",
            retryable=False,
            outcome=Outcome.FAILED,
            recovery="Point FIJI_PATH at the Fiji root.",
        )
    return root


def load_settings(environ: dict[str, str] | None = None) -> Settings:
    """Read and validate the Fiji root and execution mode."""
    env = os.environ if environ is None else environ
    raw_path = env.get("FIJI_PATH", "").strip()
    if not raw_path:
        raise FijiError(
            "invalid_configuration",
            "FIJI_PATH is required.",
            retryable=False,
            outcome=Outcome.FAILED,
            recovery="Set FIJI_PATH to the Fiji root and retry.",
        )
    root: Path | None = None
    for attempt in range(2):
        try:
            root = _resolve_and_validate_root(raw_path)
            break
        except FijiError:
            raise
        except (OSError, RuntimeError) as error:
            if attempt == 0 and _is_eintr(error):
                continue
            raise FijiError(
                "invalid_configuration",
                f"Could not validate FIJI_PATH: {error}",
                retryable=False,
                outcome=Outcome.FAILED,
                recovery="Check FIJI_PATH permissions and retry.",
            ) from error
    assert root is not None
    mode = env.get("FIJI_MODE", "headless").strip().lower()
    if mode not in {"headless", "gui"}:
        raise FijiError(
            "invalid_configuration",
            "FIJI_MODE must be headless or gui.",
            retryable=False,
            outcome=Outcome.FAILED,
            recovery="Set FIJI_MODE=headless or FIJI_MODE=gui.",
        )
    return Settings(root, mode)  # type: ignore[arg-type]


def _redirect_java_stdout() -> None:
    import scyjava as sj

    system = sj.jimport("java.lang.System")
    system.setOut(system.err)


def _start_fiji(settings: Settings) -> Any:
    import scyjava as sj

    sj.when_jvm_starts(_redirect_java_stdout)
    import imagej

    mode = "headless" if settings.mode == "headless" else "interactive"
    return imagej.init(str(settings.fiji_path), mode=mode)


def get_ij() -> Any:
    """Return the single JVM gateway, starting it lazily when necessary."""
    global _IJ, _LIFECYCLE, _SETTINGS
    with _OPERATION_LOCK:
        if _LIFECYCLE is Lifecycle.READY:
            assert _IJ is not None
            return _IJ
        if _LIFECYCLE is Lifecycle.FAILED:
            raise FijiError(
                "jvm_failed",
                "The Fiji JVM is not reusable.",
                retryable=False,
                outcome=Outcome.FAILED,
                recovery="restart the MCP server.",
            )
        # Invalid configuration occurs before STARTING and remains fixable in-process.
        settings = load_settings()
        _LIFECYCLE = Lifecycle.STARTING
        try:
            _IJ = _start_fiji(settings)
        except Exception as error:
            _LIFECYCLE = Lifecycle.FAILED
            raise FijiError(
                "jvm_start_failed",
                str(error),
                retryable=False,
                outcome=Outcome.FAILED,
                recovery="Fix the reported cause and restart the MCP server.",
            ) from error
        _SETTINGS = settings
        _LIFECYCLE = Lifecycle.READY
        return _IJ


def _exception_type_name(error: BaseException) -> str:
    error_type = type(error)
    module_name = error_type.__module__
    class_name = error_type.__name__
    qualified_type = (
        class_name
        if class_name.startswith(f"{module_name}.")
        else f"{module_name}.{class_name}"
    )
    java_type = str(getattr(error, "__javaclass__", ""))
    return java_type or qualified_type


def _is_allowlisted_read_retry(error: BaseException) -> bool:
    return _is_eintr(error) or (
        _exception_type_name(error) == "java.util.ConcurrentModificationException"
    )


def _jvm_is_healthy(ij: Any) -> bool:
    try:
        import scyjava as sj

        return bool(sj.jvm_started()) and bool(ij.getVersion())
    except Exception:
        return False


def _mark_jvm_failed() -> None:
    global _LIFECYCLE
    _LIFECYCLE = Lifecycle.FAILED


def _dead_jvm_error(outcome: Outcome) -> FijiError:
    return FijiError(
        "jvm_failed",
        "The Fiji JVM stopped or failed and is not reusable.",
        retryable=False,
        outcome=outcome,
        recovery="restart the MCP server.",
    )


def _translate(error: BaseException, operation: str, outcome: Outcome) -> FijiError:
    if isinstance(error, FijiError):
        return error
    if _exception_type_name(error) == "java.awt.HeadlessException":
        return FijiError(
            "gui_required",
            f"{operation} requires a Fiji GUI.",
            retryable=False,
            outcome=outcome,
            recovery="Use a scripted/headless route or restart with FIJI_MODE=gui.",
        )
    if outcome is Outcome.UNKNOWN:
        return FijiError(
            "unknown_outcome",
            f"{operation} may have completed before the bridge failed: {error}",
            retryable=False,
            outcome=outcome,
            recovery="Inspect get_state or screenshot before deciding whether to repeat it.",
        )
    return FijiError(
        "java_bridge_failure",
        f"{operation}: {error}",
        retryable=False,
        outcome=outcome,
        recovery="Retry explicitly only if state inspection shows it is safe, or restart the server.",
    )


def _run_read_phase(operation: str, ij: Any, function: Callable[[Any], T]) -> T:
    try:
        return function(ij)
    except FijiError:
        raise
    except Exception as first:
        if _LIFECYCLE is not Lifecycle.READY or not _jvm_is_healthy(ij):
            _mark_jvm_failed()
            raise _dead_jvm_error(Outcome.FAILED) from first
        if not _is_allowlisted_read_retry(first):
            raise _translate(first, operation, Outcome.FAILED) from first
        try:
            return function(ij)
        except Exception as second:
            if not _jvm_is_healthy(ij):
                _mark_jvm_failed()
                raise _dead_jvm_error(Outcome.FAILED) from second
            raise _translate(second, operation, Outcome.FAILED) from second


def run_read(operation: str, function: Callable[[Any], T]) -> T:
    """Run a read-only Fiji operation with one safe retry at most."""
    with _OPERATION_LOCK:
        return _run_read_phase(operation, get_ij(), function)


def run_mutation(
    operation: str,
    prepare: Callable[[Any], P],
    dispatch: Callable[[Any, P], T],
) -> T:
    """Run a mutation with a retryable pre-dispatch phase and one dispatch."""
    with _OPERATION_LOCK:
        ij = get_ij()
        try:
            prepared = _run_read_phase(f"{operation}.prepare", ij, prepare)
        except FijiError:
            raise
        try:
            return dispatch(ij, prepared)
        except FijiError:
            raise
        except Exception as error:
            if not _jvm_is_healthy(ij):
                _mark_jvm_failed()
                raise _dead_jvm_error(Outcome.UNKNOWN) from error
            raise _translate(error, operation, Outcome.UNKNOWN) from error


def get_settings() -> Settings:
    """Return settings associated with the initialized Fiji gateway."""
    get_ij()
    assert _SETTINGS is not None
    return _SETTINGS


def runtime_snapshot() -> dict[str, Any]:
    """Return the observable runtime lifecycle and initialized settings."""
    return {
        "lifecycle": _LIFECYCLE.value,
        "path": str(_SETTINGS.fiji_path) if _SETTINGS else None,
        "mode": _SETTINGS.mode if _SETTINGS else None,
    }


def _reset_runtime_for_tests(*, ready_ij: Any | None = None) -> None:
    """Reset process state for isolated unit tests only."""
    global _IJ, _LIFECYCLE, _SETTINGS
    _IJ = ready_ij
    _LIFECYCLE = Lifecycle.READY if ready_ij is not None else Lifecycle.NEW
    _SETTINGS = None
