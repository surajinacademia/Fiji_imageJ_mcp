from __future__ import annotations

import json
import math

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


def test_oversized_payload_falls_back_to_summary():
    result = to_jsonable({str(index): "x" * 4000 for index in range(100)})
    assert result["truncated"] is True
    assert result["reason"] == "serialized result exceeds 64 KiB"
    assert len(json.dumps(result).encode("utf-8")) <= 65_536


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
