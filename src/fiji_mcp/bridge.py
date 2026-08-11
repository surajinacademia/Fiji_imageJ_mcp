"""Isolated, synchronous runtime bridge for a single Fiji JVM."""

from __future__ import annotations

import errno
import heapq
import json
import math
import os
import threading
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from itertools import islice
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


@dataclass(frozen=True)
class _BoundedItems:
    """A sample plus truthful information about values intentionally omitted."""

    items: list[Any]
    exact_omitted: int = 0
    at_least_omitted: int = 0
    probe: Any = _MISSING


def _cap_text(value: str) -> str:
    return value[:_MAX_STRING]


def _truncate_string(value: str) -> str:
    if len(value) <= _MAX_STRING:
        return value
    return value[: _MAX_STRING - 1] + "…"


def _safe_text(value: Any) -> str | None:
    try:
        return str(value)
    except Exception:
        return None


def _qualified_python_type(value: Any) -> str:
    value_type = type(value)
    return _cap_text(f"{value_type.__module__}.{value_type.__qualname__}")


def _summary(value: Any) -> str:
    """Produce a bounded diagnostic summary without inspecting object contents."""
    return _cap_text(_safe_text(value) or "<unavailable>")


def _call_named(value: Any, method_name: str, *args: Any) -> Any:
    """Call one explicitly supported Java API method, or return a sentinel."""
    try:
        method = getattr(value, method_name, None)
        if not callable(method):
            return _MISSING
        return method(*args)
    except Exception:
        return _MISSING


def _java_type_name(value: Any) -> str | None:
    """Return a capped Java runtime class name when this is a Java proxy."""
    get_class = _call_named(value, "getClass")
    if get_class is _MISSING:
        return None
    name = _call_named(get_class, "getName")
    if name is _MISSING or name is None:
        return None
    text = _safe_text(name)
    return _cap_text(text) if text is not None else None


def _resolved_type_name(value: Any, java_type: str | None = None) -> str:
    return java_type or _java_type_name(value) or _qualified_python_type(value)


def _safe_bool(value: Any) -> bool | None:
    try:
        return bool(value)
    except Exception:
        return None


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except Exception:
        return None


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except Exception:
        return None


def _unbox_java_primitive(value: Any, java_type: str | None) -> Any:
    """Return a Python primitive for supported boxed Java values."""
    if java_type == "java.lang.Boolean":
        raw_value = _call_named(value, "booleanValue")
        result = _safe_bool(raw_value) if raw_value is not _MISSING else None
        return result if result is not None else _MISSING

    integer_methods = {
        "java.lang.Byte": "byteValue",
        "java.lang.Short": "shortValue",
        "java.lang.Integer": "intValue",
        "java.lang.Long": "longValue",
    }
    integer_method = integer_methods.get(java_type)
    if integer_method is not None:
        raw_value = _call_named(value, integer_method)
        result = _safe_int(raw_value) if raw_value is not _MISSING else None
        return result if result is not None else _MISSING

    float_methods = {
        "java.lang.Float": "floatValue",
        "java.lang.Double": "doubleValue",
    }
    float_method = float_methods.get(java_type)
    if float_method is not None:
        raw_value = _call_named(value, float_method)
        result = _safe_float(raw_value) if raw_value is not _MISSING else None
        return result if result is not None else _MISSING

    if java_type in {"java.lang.Character", "java.lang.String"}:
        method_name = "charValue" if java_type == "java.lang.Character" else "toString"
        raw_value = _call_named(value, method_name)
        text = _safe_text(raw_value) if raw_value is not _MISSING else None
        return _truncate_string(text) if text is not None else _MISSING

    return _MISSING


def _integer_from_method(value: Any, method_name: str, *args: Any) -> int | None:
    raw_value = _call_named(value, method_name, *args)
    if raw_value is _MISSING:
        return None
    unboxed = _unbox_java_primitive(raw_value, _java_type_name(raw_value))
    return _safe_int(unboxed if unboxed is not _MISSING else raw_value)


def _text_from_method(value: Any, method_name: str) -> str | None:
    raw_value = _call_named(value, method_name)
    if raw_value is _MISSING or raw_value is None:
        return None
    unboxed = _unbox_java_primitive(raw_value, _java_type_name(raw_value))
    if isinstance(unboxed, str):
        return unboxed
    text = _safe_text(raw_value)
    return _truncate_string(text) if text is not None else None


def _fixed_image_summary(image: Any) -> dict[str, Any] | None:
    """Read only the fixed ImagePlus metadata contract, never pixel data."""
    title = _text_from_method(image, "getTitle")
    width = _integer_from_method(image, "getWidth")
    height = _integer_from_method(image, "getHeight")
    channels = _integer_from_method(image, "getNChannels")
    slices = _integer_from_method(image, "getNSlices")
    frames = _integer_from_method(image, "getNFrames")
    bit_depth = _integer_from_method(image, "getBitDepth")
    if None in (title, width, height, channels, slices, frames, bit_depth):
        return None
    return {
        "title": title,
        "width": width,
        "height": height,
        "channels": channels,
        "slices": slices,
        "frames": frames,
        "bit_depth": bit_depth,
    }


def _axis_label(axis: Any) -> str | None:
    axis_type = _call_named(axis, "type")
    if axis_type is _MISSING:
        return None
    for candidate in (axis_type, axis):
        for method_name in ("getLabel", "getName"):
            label = _text_from_method(candidate, method_name)
            if label is not None:
                return label.casefold()
        if isinstance(candidate, str):
            return candidate.casefold()
    text = _safe_text(axis_type)
    return text.casefold() if text is not None else None


def _dataset_dimension_summary(image: Any, dimensions: int) -> dict[str, int] | None:
    values = {"width": 1, "height": 1, "channels": 1, "slices": 1, "frames": 1}
    axis_fields = {
        "x": "width",
        "y": "height",
        "channel": "channels",
        "c": "channels",
        "z": "slices",
        "time": "frames",
        "t": "frames",
    }
    found_axis_metadata = False
    for index in range(dimensions):
        axis = _call_named(image, "axis", index)
        if axis is _MISSING:
            continue
        field = axis_fields.get(_axis_label(axis) or "")
        if field is None:
            continue
        size = _integer_from_method(image, "dimension", index)
        if size is not None:
            values[field] = size
            found_axis_metadata = True

    if found_axis_metadata:
        return values

    for index, field in enumerate(("width", "height", "channels", "slices", "frames")):
        if index >= dimensions:
            break
        size = _integer_from_method(image, "dimension", index)
        if size is None:
            return None
        values[field] = size
    return values


def _dataset_summary(image: Any, java_type: str | None) -> dict[str, Any] | None:
    if java_type is None or not java_type.endswith("Dataset"):
        return None
    title = _text_from_method(image, "getName")
    dimensions = _integer_from_method(image, "numDimensions")
    bit_depth = _integer_from_method(image, "getValidBits")
    if title is None or dimensions is None or bit_depth is None or dimensions < 0:
        return None
    values = _dataset_dimension_summary(image, dimensions)
    if values is None:
        return None
    return {"title": title, **values, "bit_depth": bit_depth}


def _image_summary_if_supported(
    image: Any, java_type: str | None
) -> dict[str, Any] | None:
    return _fixed_image_summary(image) or _dataset_summary(image, java_type)


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


def _marker_for(bounded: _BoundedItems) -> dict[str, int] | None:
    if bounded.exact_omitted:
        return {"truncated_items": bounded.exact_omitted}
    if bounded.at_least_omitted:
        return {"truncated_items_at_least": bounded.at_least_omitted}
    return None


def _mapping_marker_key(bounded: _BoundedItems) -> str | None:
    if bounded.exact_omitted:
        return "__truncated_items__"
    if bounded.at_least_omitted:
        return "__truncated_items_at_least__"
    return None


def _bounded_exact_sequence(value: list[Any] | tuple[Any, ...]) -> _BoundedItems:
    total = len(value)
    sample = value[: _MAX_ITEMS + 1]
    items = list(sample[:_MAX_ITEMS])
    return _BoundedItems(
        items,
        exact_omitted=max(total - _MAX_ITEMS, 0),
        probe=sample[_MAX_ITEMS] if len(sample) > _MAX_ITEMS else _MISSING,
    )


def _bounded_exact_mapping(value: dict[Any, Any]) -> _BoundedItems:
    total = len(value)
    sample = list(islice(value.items(), _MAX_ITEMS + 1))
    return _BoundedItems(
        sample[:_MAX_ITEMS],
        exact_omitted=max(total - _MAX_ITEMS, 0),
        probe=sample[_MAX_ITEMS] if len(sample) > _MAX_ITEMS else _MISSING,
    )


def _bounded_python_iterable(value: Any) -> _BoundedItems | None:
    """Consume at most 101 values; subclasses cannot force full traversal."""
    try:
        iterator = iter(value)
    except Exception:
        return None
    items: list[Any] = []
    for _ in range(_MAX_ITEMS):
        try:
            items.append(next(iterator))
        except StopIteration:
            return _BoundedItems(items)
        except Exception:
            return None
    try:
        probe = next(iterator)
    except StopIteration:
        return _BoundedItems(items)
    except Exception:
        return None
    return _BoundedItems(items, at_least_omitted=1, probe=probe)


def _bounded_java_iterator(iterator: Any) -> _BoundedItems | None:
    """Consume 100 values plus one probe, then only inspect hasNext()."""
    items: list[Any] = []
    for _ in range(_MAX_ITEMS):
        raw_has_next = _call_named(iterator, "hasNext")
        if raw_has_next is _MISSING:
            return None
        has_next = _safe_bool(raw_has_next)
        if has_next is None:
            return None
        if not has_next:
            return _BoundedItems(items)
        item = _call_named(iterator, "next")
        if item is _MISSING:
            return None
        items.append(item)

    raw_has_next = _call_named(iterator, "hasNext")
    if raw_has_next is _MISSING:
        return None
    has_next = _safe_bool(raw_has_next)
    if has_next is None:
        return None
    if not has_next:
        return _BoundedItems(items)
    probe = _call_named(iterator, "next")
    if probe is _MISSING:
        return None
    raw_has_more = _call_named(iterator, "hasNext")
    if raw_has_more is _MISSING:
        return None
    has_more = _safe_bool(raw_has_more)
    if has_more is None:
        return None
    if has_more:
        return _BoundedItems(items, at_least_omitted=2, probe=probe)
    return _BoundedItems(items, exact_omitted=1, probe=probe)


def _bounded_items(value: Any) -> _BoundedItems | None:
    iterator = _call_named(value, "iterator")
    if iterator is not _MISSING:
        return _bounded_java_iterator(iterator)
    if type(value) in {list, tuple}:
        return _bounded_exact_sequence(value)
    return _bounded_python_iterable(value)


def _string_map_key(value: Any) -> str | None:
    if isinstance(value, str):
        return _truncate_string(value)
    unboxed = _unbox_java_primitive(value, _java_type_name(value))
    return unboxed if isinstance(unboxed, str) else None


def _pair_from_entry(entry: Any) -> tuple[Any, Any] | None:
    key = _call_named(entry, "getKey")
    item = _call_named(entry, "getValue")
    return (key, item) if key is not _MISSING and item is not _MISSING else None


def _bounded_java_pairs(value: Any) -> _BoundedItems | None:
    entry_set = _call_named(value, "entrySet")
    if entry_set is _MISSING:
        return None
    bounded = _bounded_items(entry_set)
    if bounded is None:
        return None
    pairs = [_pair_from_entry(entry) for entry in bounded.items]
    if any(pair is None for pair in pairs):
        return None
    probe = (
        _pair_from_entry(bounded.probe) if bounded.probe is not _MISSING else _MISSING
    )
    return _BoundedItems(
        [pair for pair in pairs if pair is not None],
        exact_omitted=bounded.exact_omitted,
        at_least_omitted=bounded.at_least_omitted,
        probe=probe,
    )


def _mapping_pairs(value: Any) -> _BoundedItems | None:
    if type(value) is dict:
        return _bounded_exact_mapping(value)
    bounded = _bounded_python_iterable(_call_named(value, "items"))
    if bounded is None:
        return None
    pairs: list[tuple[Any, Any]] = []
    for pair in bounded.items:
        try:
            key, item = pair
        except Exception:
            return None
        pairs.append((key, item))
    probe: Any = _MISSING
    if bounded.probe is not _MISSING:
        try:
            probe = tuple(bounded.probe)
            if len(probe) != 2:
                return None
        except Exception:
            return None
    return _BoundedItems(
        pairs,
        exact_omitted=bounded.exact_omitted,
        at_least_omitted=bounded.at_least_omitted,
        probe=probe,
    )


def _object_map_keys(bounded: _BoundedItems) -> list[str] | None:
    keys = [_string_map_key(key) for key, _ in bounded.items]
    if any(key is None for key in keys):
        return None
    normalized = [key for key in keys if key is not None]
    marker_key = _mapping_marker_key(bounded)
    if len(normalized) != len(set(normalized)) or (
        marker_key is not None and marker_key in normalized
    ):
        return None
    if marker_key is None:
        return normalized
    if bounded.exact_omitted != 1 or not isinstance(bounded.probe, tuple):
        return None
    probe_key = _string_map_key(bounded.probe[0])
    if probe_key is None or probe_key in normalized or probe_key == marker_key:
        return None
    return normalized


def _convert_pairs(bounded: _BoundedItems, *, depth: int, seen: set[int]) -> Any:
    keys = _object_map_keys(bounded)
    marker = _marker_for(bounded)
    if keys is not None:
        converted = {
            key: _convert(item, depth=depth + 1, seen=seen)
            for key, (_, item) in zip(keys, bounded.items, strict=True)
        }
        marker_key = _mapping_marker_key(bounded)
        if marker is not None and marker_key is not None:
            converted[marker_key] = next(iter(marker.values()))
        return converted

    entries = [
        {
            "key": _convert(key, depth=depth + 1, seen=seen),
            "value": _convert(item, depth=depth + 1, seen=seen),
        }
        for key, item in bounded.items
    ]
    if marker is not None:
        entries.append(marker)
    return {"map_entries": entries}


def _canonical_element(value: Any, *, depth: int, seen: set[int]) -> tuple[str, Any]:
    converted = _convert(value, depth=depth + 1, seen=seen)
    try:
        encoded = json.dumps(
            converted,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        return encoded, json.loads(encoded)
    except Exception:
        opaque = {"truncated": True, "reason": "element conversion failed"}
        return json.dumps(opaque, sort_keys=True), opaque


def _convert_set(
    value: set[Any] | frozenset[Any], *, depth: int, seen: set[int]
) -> Any:
    if type(value) in {set, frozenset}:
        total = len(value)
        candidates = (
            _canonical_element(item, depth=depth, seen=seen) for item in value
        )
        selected = heapq.nsmallest(_MAX_ITEMS, candidates, key=lambda item: item[0])
        selected.sort(key=lambda item: item[0])
        bounded = _BoundedItems(
            [converted for _, converted in selected],
            exact_omitted=max(total - _MAX_ITEMS, 0),
        )
    else:
        sample = _bounded_python_iterable(value)
        if sample is None:
            return _MISSING
        selected = [
            _canonical_element(item, depth=depth, seen=seen) for item in sample.items
        ]
        selected.sort(key=lambda item: item[0])
        bounded = _BoundedItems(
            [converted for _, converted in selected],
            exact_omitted=sample.exact_omitted,
            at_least_omitted=sample.at_least_omitted,
        )
    converted = list(bounded.items)
    marker = _marker_for(bounded)
    if marker is not None:
        converted.append(marker)
    return converted


def _convert_sequence(
    bounded: _BoundedItems, *, depth: int, seen: set[int]
) -> list[Any]:
    converted = [_convert(item, depth=depth + 1, seen=seen) for item in bounded.items]
    marker = _marker_for(bounded)
    if marker is not None:
        converted.append(marker)
    return converted


def _opaque_result(value: Any, java_type: str | None = None) -> dict[str, str]:
    return {
        "java_type": _resolved_type_name(value, java_type),
        "summary": _summary(value),
    }


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
            bounded = _mapping_pairs(value)
            return (
                _convert_pairs(bounded, depth=depth, seen=seen)
                if bounded
                else _opaque_result(value)
            )

        if isinstance(value, (list, tuple)):
            bounded = (
                _bounded_exact_sequence(value)
                if type(value) in {list, tuple}
                else _bounded_python_iterable(value)
            )
            return (
                _convert_sequence(bounded, depth=depth, seen=seen)
                if bounded
                else _opaque_result(value)
            )

        if isinstance(value, (set, frozenset)):
            converted_set = _convert_set(value, depth=depth, seen=seen)
            return (
                converted_set
                if converted_set is not _MISSING
                else _opaque_result(value)
            )

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

        map_items = _bounded_java_pairs(value)
        if map_items is not None:
            return _convert_pairs(map_items, depth=depth, seen=seen)

        collection_items = _bounded_items(value)
        if collection_items is not None:
            return _convert_sequence(collection_items, depth=depth, seen=seen)

        return _opaque_result(value, java_type)
    finally:
        seen.discard(identity)


def _encoded_json(value: Any) -> bytes | None:
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except Exception:
        return None


def _oversized_fallback(value: Any) -> dict[str, Any]:
    fallback = {
        "truncated": True,
        "reason": "serialized result exceeds 64 KiB",
        "java_type": _resolved_type_name(value),
        "summary": _summary(value),
    }
    encoded = _encoded_json(fallback)
    if encoded is not None and len(encoded) <= _MAX_JSON_BYTES:
        return fallback
    return {"truncated": True, "reason": "serialized result exceeds 64 KiB"}


def to_jsonable(value: Any) -> Any:
    """Convert a Fiji result into bounded, standard-JSON-compatible data."""
    converted = _convert(value, depth=0, seen=set())
    encoded = _encoded_json(converted)
    if encoded is not None and len(encoded) <= _MAX_JSON_BYTES:
        return converted
    return _oversized_fallback(value)


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
