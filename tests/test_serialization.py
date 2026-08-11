from __future__ import annotations

import json
import math
import os
import subprocess
import sys

import pytest

from fiji_mcp import bridge
from fiji_mcp.bridge import to_jsonable


class _JavaClass:
    def __init__(self, name: str) -> None:
        self._name = name

    def getName(self) -> str:
        return self._name


class _JavaBoolean:
    def __init__(self, value: bool) -> None:
        self._value = value

    def booleanValue(self) -> bool:
        return self._value

    def getClass(self) -> _JavaClass:
        return _JavaClass("java.lang.Boolean")


class _JavaInteger:
    def __init__(self, value: int) -> None:
        self._value = value

    def intValue(self) -> int:
        return self._value

    def getClass(self) -> _JavaClass:
        return _JavaClass("java.lang.Integer")


class _JavaDouble:
    def __init__(self, value: float) -> None:
        self._value = value

    def doubleValue(self) -> float:
        return self._value

    def getClass(self) -> _JavaClass:
        return _JavaClass("java.lang.Double")


class _JavaString:
    def __init__(self, value: str) -> None:
        self._value = value

    def getClass(self) -> _JavaClass:
        return _JavaClass("java.lang.String")

    def toString(self) -> str:
        return self._value


class _JavaCharacter:
    def __init__(self, value: str) -> None:
        self._value = value

    def charValue(self) -> str:
        return self._value

    def getClass(self) -> _JavaClass:
        return _JavaClass("java.lang.Character")


class _MapEntry:
    def __init__(self, key: object, value: object) -> None:
        self._key = key
        self._value = value

    def getKey(self) -> object:
        return self._key

    def getValue(self) -> object:
        return self._value


class _JavaMap:
    def __init__(self, entries: list[_MapEntry]) -> None:
        self._entries = entries

    def entrySet(self) -> list[_MapEntry]:
        return self._entries

    def getClass(self) -> _JavaClass:
        return _JavaClass("java.util.LinkedHashMap")


class _EntrySetOnly:
    def __init__(self, entries: list[_MapEntry]) -> None:
        self._entries = entries

    def entrySet(self) -> list[_MapEntry]:
        return self._entries


class _JavaIterator:
    def __init__(self, values: list[object]) -> None:
        self._values = values
        self._index = 0
        self.next_calls = 0

    def hasNext(self) -> bool:
        return self._index < len(self._values)

    def next(self) -> object:
        self.next_calls += 1
        value = self._values[self._index]
        self._index += 1
        return value


class _JavaIterable:
    def __init__(self, values: list[object]) -> None:
        self._iterator = _JavaIterator(values)

    def getClass(self) -> _JavaClass:
        return _JavaClass("java.util.ArrayList")

    def iterator(self) -> _JavaIterator:
        return self._iterator


class _JavaEntrySet:
    def __init__(self, entries: list[_MapEntry]) -> None:
        self._iterator = _JavaIterator(entries)

    def iterator(self) -> _JavaIterator:
        return self._iterator


class _IteratorMap:
    def __init__(self, entries: list[_MapEntry]) -> None:
        self._entry_set = _JavaEntrySet(entries)

    def entrySet(self) -> _JavaEntrySet:
        return self._entry_set

    def getClass(self) -> _JavaClass:
        return _JavaClass("java.util.LinkedHashMap")


class _GuardedInfiniteJavaIterator:
    def __init__(self, value: object) -> None:
        self._value = value
        self.next_calls = 0

    def hasNext(self) -> bool:
        return True

    def next(self) -> object:
        self.next_calls += 1
        if self.next_calls > 101:
            raise AssertionError("serializer consumed more than 101 Java items")
        return self._value


class _GuardedInfiniteJavaIterable:
    def __init__(self, value: object) -> None:
        self._iterator = _GuardedInfiniteJavaIterator(value)

    def getClass(self) -> _JavaClass:
        return _JavaClass("java.util.ArrayList")

    def iterator(self) -> _GuardedInfiniteJavaIterator:
        return self._iterator


class _GuardedInfiniteJavaMap:
    def __init__(self) -> None:
        self._iterator = _GuardedInfiniteJavaIterator(_MapEntry("key", "value"))

    def entrySet(self) -> _GuardedInfiniteJavaMap:
        return self

    def getClass(self) -> _JavaClass:
        return _JavaClass("java.util.LinkedHashMap")

    def iterator(self) -> _GuardedInfiniteJavaIterator:
        return self._iterator


class _NoStringification:
    def __init__(self) -> None:
        self.string_calls = 0

    def __str__(self) -> str:
        self.string_calls += 1
        raise AssertionError("serializer must not stringify an oversized container")

    def toString(self) -> str:
        return str(self)


class _OversizedJavaCollection(_NoStringification):
    def __init__(self) -> None:
        super().__init__()
        self._iterator = _GuardedInfiniteJavaIterator("x" * 4_000)

    def getClass(self) -> _JavaClass:
        return _JavaClass("java.util.ArrayList")

    def iterator(self) -> _GuardedInfiniteJavaIterator:
        return self._iterator


class _OversizedJavaMap(_NoStringification):
    def __init__(self) -> None:
        super().__init__()
        self._iterator = _GuardedInfiniteJavaIterator(_MapEntry("key", "x" * 4_000))

    def entrySet(self) -> _OversizedJavaMap:
        return self

    def getClass(self) -> _JavaClass:
        return _JavaClass("java.util.LinkedHashMap")

    def iterator(self) -> _GuardedInfiniteJavaIterator:
        return self._iterator


class _IteratorOnly:
    def __init__(self, values: list[object]) -> None:
        self._iterator = _JavaIterator(values)

    def iterator(self) -> _JavaIterator:
        return self._iterator


class _ImagePlus:
    def getBitDepth(self) -> int:
        return 16

    def getClass(self) -> _JavaClass:
        return _JavaClass("ij.ImagePlus")

    def getHeight(self) -> int:
        return 48

    def getNChannels(self) -> int:
        return 2

    def getNFrames(self) -> int:
        return 4

    def getNSlices(self) -> int:
        return 3

    def getPixels(self) -> object:
        raise AssertionError("pixel data must not be serialized")

    def getTitle(self) -> str:
        return "cells"

    def getWidth(self) -> int:
        return 64


class _Dataset:
    def dimension(self, index: int) -> int:
        return (32, 24, 2, 3, 4)[index]

    def getClass(self) -> _JavaClass:
        return _JavaClass("net.imagej.Dataset")

    def getName(self) -> str:
        return "dataset"

    def getPixels(self) -> object:
        raise AssertionError("pixel data must not be serialized")

    def getValidBits(self) -> int:
        return 32

    def numDimensions(self) -> int:
        return 5


class _AxisType:
    def __init__(self, label: str) -> None:
        self._label = label

    def getLabel(self) -> str:
        return self._label


class _Axis:
    def __init__(self, label: str) -> None:
        self._type = _AxisType(label)

    def type(self) -> _AxisType:
        return self._type


class _ReorderedAxisDataset(_Dataset):
    _dimensions = (5, 3, 64, 2, 48)
    _axes = ("Time", "Z", "X", "Channel", "Y")

    def axis(self, index: int) -> _Axis:
        return _Axis(self._axes[index])

    def dimension(self, index: int) -> int:
        return self._dimensions[index]


class _AxisDataset(_Dataset):
    def __init__(self, labels: tuple[str, ...], dimensions: tuple[int, ...]) -> None:
        self._axes = labels
        self._dimensions = dimensions
        self.axis_calls = 0

    def axis(self, index: int) -> _Axis:
        self.axis_calls += 1
        return _Axis(self._axes[index])

    def dimension(self, index: int) -> int:
        return self._dimensions[index]

    def numDimensions(self) -> int:
        return len(self._dimensions)


class _OversizedAxisDataset(_Dataset):
    def __init__(self, dimensions: int) -> None:
        self._dimensions = dimensions
        self.axis_calls = 0

    def axis(self, index: int) -> _Axis:
        self.axis_calls += 1
        return _Axis("X")

    def numDimensions(self) -> int:
        return self._dimensions


class _CompositeImage(_ImagePlus):
    def getClass(self) -> _JavaClass:
        return _JavaClass("ij.CompositeImage")


class _ResultsTable:
    def getClass(self) -> _JavaClass:
        return _JavaClass("ij.measure.ResultsTable")

    def getLastColumn(self) -> int:
        return 2

    def size(self) -> int:
        return 7


class _PluginResult:
    def __init__(self, summary: str) -> None:
        self._summary = summary

    def getClass(self) -> _JavaClass:
        return _JavaClass("example.PluginResult")

    def __str__(self) -> str:
        return self._summary


class _BoundedInfiniteList(list[int]):
    def __init__(self) -> None:
        self.yield_count = 0

    def __iter__(self):
        while True:
            self.yield_count += 1
            if self.yield_count > 101:
                raise AssertionError("serializer consumed more than 101 list values")
            yield self.yield_count

    def __len__(self) -> int:
        raise AssertionError("serializer must not trust a list subclass length")


class _InstrumentedHugeList(list[int]):
    def __init__(self) -> None:
        super().__init__(range(10_000))
        self.yield_count = 0

    def __iter__(self):
        for value in super().__iter__():
            self.yield_count += 1
            yield value


class _BoundedInfiniteTuple(tuple[int, ...]):
    def __new__(cls) -> _BoundedInfiniteTuple:
        instance = super().__new__(cls)
        instance.yield_count = 0
        return instance

    def __iter__(self):
        while True:
            self.yield_count += 1
            if self.yield_count > 101:
                raise AssertionError("serializer consumed more than 101 tuple values")
            yield self.yield_count

    def __len__(self) -> int:
        raise AssertionError("serializer must not trust a tuple subclass length")


class _BoundedInfiniteSet(set[int]):
    def __init__(self) -> None:
        self.yield_count = 0

    def __iter__(self):
        while True:
            self.yield_count += 1
            if self.yield_count > 101:
                raise AssertionError("serializer consumed more than 101 set values")
            yield self.yield_count

    def __len__(self) -> int:
        raise AssertionError("serializer must not trust a set subclass length")


class _BoundedInfiniteDict(dict[str, int]):
    def __init__(self, first_key: str | None = None) -> None:
        self.first_key = first_key
        self.yield_count = 0

    def items(self):
        while True:
            self.yield_count += 1
            if self.yield_count > 101:
                raise AssertionError("serializer consumed more than 101 map entries")
            key = self.first_key if self.yield_count == 1 else f"key-{self.yield_count}"
            yield key, self.yield_count

    def __len__(self) -> int:
        raise AssertionError("serializer must not trust a dict subclass length")


class _LongTypeCollection:
    def __init__(self) -> None:
        self._iterator = _JavaIterator(["x" * 4_000] * 100)

    def getClass(self) -> _JavaClass:
        return _JavaClass("x" * 70_000)

    def iterator(self) -> _JavaIterator:
        return self._iterator


class _ExplodingCoercion:
    def __bool__(self) -> bool:
        raise RuntimeError("bool failed")

    def __float__(self) -> float:
        raise RuntimeError("float failed")

    def __int__(self) -> int:
        raise RuntimeError("int failed")

    def __str__(self) -> str:
        raise RuntimeError("str failed")


class _ExplodingJavaPrimitive:
    def __init__(self, java_type: str, method_name: str) -> None:
        self._java_type = java_type
        self._method_name = method_name

    def __getattr__(self, name: str):
        if name == self._method_name:
            return lambda: _ExplodingCoercion()
        raise AttributeError(name)

    def getClass(self) -> _JavaClass:
        return _JavaClass(self._java_type)


class _TenThousandTailPair:
    def __init__(self) -> None:
        self.reads = 0

    def __iter__(self) -> _TenThousandTailPair:
        return self

    def __next__(self) -> object:
        self.reads += 1
        if self.reads == 1:
            return "probe"
        if self.reads == 2:
            return "value"
        if self.reads > 3:
            raise AssertionError("serializer read beyond the bounded pair probe")
        return "extra"


class _ProbePairMapping(dict[str, int]):
    def __init__(self, probe: _TenThousandTailPair) -> None:
        self._probe = probe

    def items(self):
        yield from ((f"key-{index}", index) for index in range(100))
        yield self._probe


def test_non_finite_numbers_are_standard_json_values():
    assert to_jsonable([math.nan, math.inf, -math.inf]) == [
        "NaN",
        "Infinity",
        "-Infinity",
    ]


def test_non_string_map_keys_use_ordered_entries():
    result = to_jsonable({1: "one", "1": "string one"})
    assert result == {
        "map_entries": [
            {"key": 1, "value": "one"},
            {"key": "1", "value": "string one"},
        ]
    }


def test_cycles_are_bounded():
    value: list[object] = []
    value.append(value)
    assert to_jsonable(value) == [{"cycle": True}]


def test_collections_and_strings_are_truncated():
    result = to_jsonable({"items": list(range(101)), "text": "x" * 4001})
    assert len(result["items"]) == 101
    assert result["items"][-1] == {"truncated_items": 1}
    assert result["text"].endswith("…")
    assert len(result["text"]) == 4000


def test_oversized_payload_falls_back_to_metadata():
    result = to_jsonable({str(index): "x" * 4000 for index in range(100)})
    assert result["truncated"] is True
    assert result["reason"] == "serialized result exceeds 64 KiB"
    assert len(json.dumps(result).encode("utf-8")) <= 65_536


@pytest.mark.parametrize(
    ("container_factory", "java_type"),
    [
        (_OversizedJavaCollection, "java.util.ArrayList"),
        (_OversizedJavaMap, "java.util.LinkedHashMap"),
    ],
)
def test_oversized_java_containers_do_not_stringify_after_sampling(
    container_factory, java_type: str
):
    value = container_factory()

    result = to_jsonable(value)

    assert value._iterator.next_calls == 101
    assert value.string_calls == 0
    assert result == {
        "truncated": True,
        "reason": "serialized result exceeds 64 KiB",
        "java_type": java_type,
    }
    assert len(json.dumps(result, ensure_ascii=False).encode("utf-8")) <= 65_536


def test_maximum_depth_is_explicit():
    result = to_jsonable([[[[["too deep"]]]]])
    assert result[0][0][0][0] == {
        "truncated": True,
        "reason": "maximum depth reached",
    }


def test_python_sets_are_stably_sorted():
    assert to_jsonable({"gamma", "alpha", "beta"}) == ["alpha", "beta", "gamma"]


def test_java_map_uses_object_when_all_keys_are_strings():
    result = to_jsonable(
        _JavaMap([_MapEntry("first", 1), _MapEntry("second", _JavaBoolean(True))])
    )
    assert result == {"first": 1, "second": True}


def test_java_map_uses_ordered_entries_when_any_key_is_not_a_string():
    result = to_jsonable(_JavaMap([_MapEntry(1, "one"), _MapEntry("1", "string one")]))
    assert result == {
        "map_entries": [
            {"key": 1, "value": "one"},
            {"key": "1", "value": "string one"},
        ]
    }


def test_java_character_key_uses_ordered_entries():
    assert to_jsonable(_JavaMap([_MapEntry(_JavaCharacter("x"), "character")])) == {
        "map_entries": [{"key": "x", "value": "character"}]
    }


def test_java_character_key_forces_ordered_entries_with_same_java_string_key():
    result = to_jsonable(
        _JavaMap(
            [
                _MapEntry(_JavaCharacter("x"), "character"),
                _MapEntry(_JavaString("x"), "string"),
            ]
        )
    )
    assert result == {
        "map_entries": [
            {"key": "x", "value": "character"},
            {"key": "x", "value": "string"},
        ]
    }


def test_java_string_key_remains_a_json_object_key():
    assert to_jsonable(_JavaMap([_MapEntry(_JavaString("x"), "string")])) == {
        "x": "string"
    }


def test_java_iterable_is_bounded_without_materializing_all_items():
    values = _JavaIterable(list(range(101)))
    result = to_jsonable(values)
    assert result == [*range(100), {"truncated_items": 1}]
    assert values._iterator.next_calls == 101


def test_named_java_collection_apis_do_not_require_proxy_metadata():
    assert to_jsonable(_EntrySetOnly([_MapEntry("key", 1)])) == {"key": 1}
    assert to_jsonable(_IteratorOnly(["one", "two"])) == ["one", "two"]


def test_imageplus_and_dataset_return_metadata_without_pixel_data():
    assert to_jsonable(_ImagePlus()) == {
        "title": "cells",
        "width": 64,
        "height": 48,
        "channels": 2,
        "slices": 3,
        "frames": 4,
        "bit_depth": 16,
    }
    assert to_jsonable(_Dataset()) == {
        "title": "dataset",
        "width": 32,
        "height": 24,
        "channels": 2,
        "slices": 3,
        "frames": 4,
        "bit_depth": 32,
    }


def test_image_summary_has_the_same_bounded_metadata_shape():
    assert bridge.image_summary(_ImagePlus()) == {
        "title": "cells",
        "width": 64,
        "height": 48,
        "channels": 2,
        "slices": 3,
        "frames": 4,
        "bit_depth": 16,
    }


def test_results_table_returns_counts_without_rows():
    assert to_jsonable(_ResultsTable()) == {"rows": 7, "columns": 3}


def test_unknown_java_proxy_uses_java_type_and_summary():
    assert to_jsonable(_PluginResult("plugin-result")) == {
        "java_type": "example.PluginResult",
        "summary": "plugin-result",
    }


def test_unknown_java_proxy_summary_is_capped():
    result = to_jsonable(_PluginResult("x" * 4001))
    assert result["java_type"] == "example.PluginResult"
    assert len(result["summary"]) == 4000


def test_java_boxed_primitives_become_json_primitives():
    assert to_jsonable(
        [_JavaBoolean(True), _JavaInteger(7), _JavaDouble(1.25), _JavaString("value")]
    ) == [True, 7, 1.25, "value"]


def test_exact_builtin_sequences_report_exact_omissions_without_full_copies():
    result = to_jsonable(list(range(102)))
    assert result[-1] == {"truncated_items": 2}


def test_huge_list_subclasses_are_not_fully_materialized():
    value = _InstrumentedHugeList()
    result = to_jsonable(value)
    assert value.yield_count == 101
    assert result[-1] == {"truncated_items_at_least": 1}


@pytest.mark.parametrize(
    "value",
    [
        _BoundedInfiniteList(),
        _BoundedInfiniteTuple(),
        _BoundedInfiniteSet(),
    ],
)
def test_hostile_python_container_subclasses_are_sampled_at_101(value: object):
    result = to_jsonable(value)
    assert value.yield_count == 101  # type: ignore[attr-defined]
    assert result[-1] == {"truncated_items_at_least": 1}


def test_hostile_mapping_subclasses_are_sampled_at_101():
    value = _BoundedInfiniteDict()
    result = to_jsonable(value)
    assert value.yield_count == 101
    assert result["map_entries"][-1] == {"truncated_items_at_least": 1}


def test_java_iterators_report_exact_and_lower_bound_truncation_truthfully():
    exact = _JavaIterable(list(range(101)))
    assert to_jsonable(exact)[-1] == {"truncated_items": 1}
    assert exact._iterator.next_calls == 101

    beyond_one = _JavaIterable(list(range(102)))
    assert to_jsonable(beyond_one)[-1] == {"truncated_items_at_least": 2}
    assert beyond_one._iterator.next_calls == 101

    large = _JavaIterable(list(range(10_000)))
    assert to_jsonable(large)[-1] == {"truncated_items_at_least": 2}
    assert large._iterator.next_calls == 101


def test_infinite_java_iterators_and_maps_stop_after_one_probe():
    values = _GuardedInfiniteJavaIterable("value")
    assert to_jsonable(values)[-1] == {"truncated_items_at_least": 2}
    assert values._iterator.next_calls == 101

    mapping = _GuardedInfiniteJavaMap()
    result = to_jsonable(mapping)
    assert result["map_entries"][-1] == {"truncated_items_at_least": 2}
    assert mapping._iterator.next_calls == 101


def test_java_maps_distinguish_exact_and_unknown_remainders():
    exact = _IteratorMap([_MapEntry(f"key-{index}", index) for index in range(101)])
    result = to_jsonable(exact)
    assert result["__truncated_items__"] == 1

    unknown = _IteratorMap([_MapEntry(f"key-{index}", index) for index in range(102)])
    result = to_jsonable(unknown)
    assert result["map_entries"][-1] == {"truncated_items_at_least": 2}

    large = _IteratorMap([_MapEntry(f"key-{index}", index) for index in range(10_000)])
    result = to_jsonable(large)
    assert result["map_entries"][-1] == {"truncated_items_at_least": 2}
    assert large._entry_set._iterator.next_calls == 101


def test_string_key_collisions_and_reserved_markers_use_ordered_entries():
    first = "x" * 4_001
    second = "x" * 4_000 + "y"
    python_result = to_jsonable({first: 1, second: 2})
    assert [entry["value"] for entry in python_result["map_entries"]] == [1, 2]

    java_result = to_jsonable(
        _JavaMap([_MapEntry(_JavaString(first), 1), _MapEntry(_JavaString(second), 2)])
    )
    assert [entry["value"] for entry in java_result["map_entries"]] == [1, 2]

    exact = {
        "__truncated_items__": "preserve",
        **{f"key-{index}": index for index in range(100)},
    }
    result = to_jsonable(exact)
    assert result["map_entries"][0] == {
        "key": "__truncated_items__",
        "value": "preserve",
    }
    assert result["map_entries"][-1] == {"truncated_items": 1}

    unknown = _BoundedInfiniteDict("__truncated_items_at_least__")
    result = to_jsonable(unknown)
    assert result["map_entries"][0] == {
        "key": "__truncated_items_at_least__",
        "value": 1,
    }
    assert result["map_entries"][-1] == {"truncated_items_at_least": 1}


def test_oversized_fallback_caps_long_proxy_type_names():
    result = to_jsonable(_LongTypeCollection())
    assert result["truncated"] is True
    assert len(json.dumps(result, ensure_ascii=False).encode("utf-8")) <= 65_536
    assert len(result.get("java_type", "")) <= 4_000


@pytest.mark.parametrize(
    "value",
    [
        _ExplodingJavaPrimitive("java.lang.Boolean", "booleanValue"),
        _ExplodingJavaPrimitive("java.lang.Integer", "intValue"),
        _ExplodingJavaPrimitive("java.lang.Double", "doubleValue"),
        _ExplodingJavaPrimitive("java.lang.String", "toString"),
    ],
)
def test_proxy_coercion_failures_become_bounded_opaque_summaries(value: object):
    result = to_jsonable(value)
    assert result["java_type"].startswith("java.lang.")
    assert len(result["summary"]) <= 4_000


def test_dataset_axis_metadata_controls_dimension_assignment():
    assert to_jsonable(_ReorderedAxisDataset()) == {
        "title": "dataset",
        "width": 64,
        "height": 48,
        "channels": 2,
        "slices": 3,
        "frames": 5,
        "bit_depth": 32,
    }


def test_complete_imageplus_contract_recognizes_composite_images_without_pixels():
    assert to_jsonable(_CompositeImage()) == {
        "title": "cells",
        "width": 64,
        "height": 48,
        "channels": 2,
        "slices": 3,
        "frames": 4,
        "bit_depth": 16,
    }


def test_set_order_uses_canonical_converted_json_across_hash_seeds():
    code = r"""
import json
from fiji_mcp.bridge import to_jsonable

class JavaClass:
    def __init__(self, name): self.name = name
    def getName(self): return self.name

class JavaIterator:
    def __init__(self, values): self.values, self.index = values, 0
    def hasNext(self): return self.index < len(self.values)
    def next(self):
        value = self.values[self.index]
        self.index += 1
        return value

class Value:
    def __init__(self, token, value): self.token, self.value = token, value
    def getClass(self): return JavaClass("java.util.ArrayList")
    def iterator(self): return JavaIterator([self.value])
    def __str__(self): return "same summary"
    def __hash__(self): return hash(self.token)
    def __eq__(self, other): return self is other

print(json.dumps(to_jsonable({Value("alpha", 1), Value("beta", 2), Value("gamma", 3), Value("delta", 4)})))
"""
    outputs = []
    for hash_seed in ("1", "2", "3"):
        environment = {**os.environ, "PYTHONHASHSEED": hash_seed}
        outputs.append(
            subprocess.check_output(  # noqa: S603 - runs this test's literal code
                [sys.executable, "-c", code], env=environment, text=True
            ).strip()
        )
    assert outputs == ["[[1], [2], [3], [4]]"] * 3


def test_mapping_probe_pair_parser_stops_after_three_subitems():
    probe = _TenThousandTailPair()
    result = to_jsonable(_ProbePairMapping(probe))
    assert probe.reads == 3
    assert result["java_type"].endswith("._ProbePairMapping")


@pytest.mark.parametrize("dimensions", [-1, 17])
def test_dataset_axis_probes_are_capped_before_any_axis_call(dimensions: int):
    dataset = _OversizedAxisDataset(dimensions)
    result = to_jsonable(dataset)
    assert dataset.axis_calls == 0
    assert result["java_type"] == "net.imagej.Dataset"


def test_unrecognized_axis_metadata_never_falls_back_to_position():
    dataset = _AxisDataset(("Latitude", "Longitude"), (80, 40))
    result = to_jsonable(dataset)
    assert dataset.axis_calls == 2
    assert result["java_type"] == "net.imagej.Dataset"


def test_partial_standard_axis_metadata_requires_xy_but_defaults_other_axes():
    valid = _AxisDataset(("X", "Y"), (64, 48))
    assert to_jsonable(valid) == {
        "title": "dataset",
        "width": 64,
        "height": 48,
        "channels": 1,
        "slices": 1,
        "frames": 1,
        "bit_depth": 32,
    }

    missing_y = _AxisDataset(("X", "Z"), (64, 3))
    result = to_jsonable(missing_y)
    assert result["java_type"] == "net.imagej.Dataset"
