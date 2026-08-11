from __future__ import annotations

from pathlib import Path

import pytest

from fiji_mcp import bridge
from fiji_mcp import tools as minimal
from fiji_mcp.bridge import FijiError, Outcome, Settings


class FakeImage:
    def __init__(
        self,
        title: str,
        width: int,
        height: int,
        *,
        image_id: int = 1,
        channels: int = 1,
        slices: int = 1,
        frames: int = 1,
        bit_depth: int = 8,
    ) -> None:
        self._title = title
        self._width = width
        self._height = height
        self._image_id = image_id
        self._channels = channels
        self._slices = slices
        self._frames = frames
        self._bit_depth = bit_depth
        self.show_count = 0

    def getTitle(self) -> str:
        return self._title

    def getWidth(self) -> int:
        return self._width

    def getHeight(self) -> int:
        return self._height

    def getID(self) -> int:
        return self._image_id

    def getNChannels(self) -> int:
        return self._channels

    def getNSlices(self) -> int:
        return self._slices

    def getNFrames(self) -> int:
        return self._frames

    def getBitDepth(self) -> int:
        return self._bit_depth

    def show(self) -> None:
        self.show_count += 1


class FakeResultsTable:
    def __init__(
        self,
        headings: list[str],
        rows: list[list[object]],
        *,
        defined_columns: list[bool] | None = None,
    ) -> None:
        self._headings = headings
        self._rows = rows
        self._defined_columns = (
            [True] * len(headings) if defined_columns is None else list(defined_columns)
        )
        if len(self._defined_columns) != len(headings):
            raise ValueError("defined_columns must align with headings")
        self.column_exists_calls: list[int] = []
        self.requested_cells: list[tuple[int, int]] = []
        self.requested_string_cells: list[tuple[int, int]] = []

    def getLastColumn(self) -> int:
        return len(self._headings) - 1

    def getColumnHeading(self, column: int) -> str:
        return self._headings[column]

    def columnExists(self, column: int) -> bool:
        self.column_exists_calls.append(column)
        return self._defined_columns[column]

    def getValueAsDouble(self, column: int, row: int) -> float:
        self.requested_cells.append((column, row))
        value = self._rows[row][column]
        return float("nan") if value is None or isinstance(value, str) else float(value)

    def getStringValue(self, column: int, row: int) -> str:
        self.requested_string_cells.append((column, row))
        value = self._rows[row][column]
        return value if isinstance(value, str) else "NaN"

    def size(self) -> int:
        return len(self._rows)


class FakeWindowManager:
    def __init__(self, active: FakeImage | None, images: list[FakeImage]) -> None:
        self._active = active
        self._images = images
        self.temp_current: FakeImage | None = None

    def getCurrentImage(self) -> FakeImage | None:
        return self._active

    def getIDList(self) -> list[int]:
        return [image.getID() for image in self._images]

    def getImage(self, image_id: int) -> FakeImage | None:
        return next(
            (image for image in self._images if image.getID() == image_id), None
        )

    def setTempCurrentImage(self, image: FakeImage) -> None:
        self.temp_current = image
        self._active = image


class FakeResultsTableClass:
    def __init__(self, results: FakeResultsTable | None) -> None:
        self._results = results

    def getResultsTable(self) -> FakeResultsTable | None:
        return self._results


class FakeIJ:
    def __init__(
        self,
        *,
        version: str = "2.16.0/1.54p",
        active: FakeImage | None = None,
        open_images: list[FakeImage] | None = None,
        opened: FakeImage | None = None,
        results: FakeResultsTable | None = None,
        error_messages: list[str | None] | None = None,
        write_saved_file: bool = True,
    ) -> None:
        self._version = version
        self.WindowManager = FakeWindowManager(active, open_images or [])
        self.ResultsTable = FakeResultsTableClass(results)
        self.IJ = self
        self._opened = opened
        self.open_count = 0
        self.save_count = 0
        self.saved_path: str | None = None
        self.parent_exists_when_saved = False
        self._error_messages = error_messages or []
        self.error_message_calls = 0
        self.write_saved_file = write_saved_file

    def getVersion(self) -> str:
        return self._version

    def openImage(self, path: str) -> FakeImage | None:
        self.open_count += 1
        return self._opened

    def save(self, _image: FakeImage, path: str) -> None:
        self.save_count += 1
        self.saved_path = path
        self.parent_exists_when_saved = Path(path).parent.is_dir()
        if self.write_saved_file:
            Path(path).write_bytes(b"saved")

    def getErrorMessage(self) -> str | None:
        self.error_message_calls += 1
        return self._error_messages.pop(0) if self._error_messages else None


def _direct_read(_name: str, function):
    return function(object())


def _direct_mutation(fake_ij: FakeIJ):
    return lambda _name, prepare, dispatch: dispatch(fake_ij, prepare(fake_ij))


def test_get_results_preserves_heading_and_row_order(monkeypatch):
    fake = FakeResultsTable(
        headings=["Area", "", "Area"],
        rows=[
            [1.5, None, float("nan")],
            [2.5, "cell", float("inf")],
            [3.5, "tail", float("-inf")],
        ],
    )
    monkeypatch.setattr(minimal, "_results_table", lambda _ij: fake)
    monkeypatch.setattr(minimal, "run_read", _direct_read)

    result = minimal.get_results(offset=0, limit=500)

    assert result["columns"] == ["Area", "", "Area"]
    assert result["rows"] == [
        [1.5, "NaN", "NaN"],
        [2.5, "cell", "Infinity"],
        [3.5, "tail", "-Infinity"],
    ]
    assert result["offset"] == 0
    assert result["returned"] == 3
    assert result["total_rows"] == 3


def test_get_results_preserves_defined_results_table_cell_conventions(monkeypatch):
    fake = FakeResultsTable(
        headings=["asymmetric", "explicit_nan", "text", "empty", "plus", "minus"],
        rows=[
            [1.25, float("nan"), "stored text", "", float("inf"), float("-inf")],
            [None, 2.5, "tail", "", float("inf"), float("-inf")],
        ],
    )
    monkeypatch.setattr(minimal, "_results_table", lambda _ij: fake)
    monkeypatch.setattr(minimal, "run_read", _direct_read)

    result = minimal.get_results()

    assert result["rows"] == [
        [1.25, "NaN", "stored text", "", "Infinity", "-Infinity"],
        ["NaN", 2.5, "tail", "", "Infinity", "-Infinity"],
    ]


def test_get_results_skips_undefined_column_slots_without_cell_access(monkeypatch):
    fake = FakeResultsTable(
        headings=["Area", "", "Mean"],
        rows=[[1.0, "must not access", 3.0], [2.0, "must not access", 4.0]],
        defined_columns=[True, False, True],
    )
    monkeypatch.setattr(minimal, "_results_table", lambda _ij: fake)
    monkeypatch.setattr(minimal, "run_read", _direct_read)

    result = minimal.get_results()

    assert result["rows"] == [[1.0, None, 3.0], [2.0, None, 4.0]]
    assert fake.column_exists_calls == [0, 1, 2]
    assert fake.requested_cells == [(0, 0), (2, 0), (0, 1), (2, 1)]
    assert fake.requested_string_cells == []


def test_get_results_propagates_numeric_accessor_errors(monkeypatch):
    fake = FakeResultsTable(headings=["Area"], rows=[[1.0]])
    monkeypatch.setattr(minimal, "_results_table", lambda _ij: fake)
    monkeypatch.setattr(minimal, "run_read", _direct_read)

    def fail_numeric(_column: int, _row: int) -> float:
        raise RuntimeError("numeric accessor failed")

    monkeypatch.setattr(fake, "getValueAsDouble", fail_numeric)

    with pytest.raises(RuntimeError, match="numeric accessor failed"):
        minimal.get_results()


def test_get_results_propagates_string_accessor_errors(monkeypatch):
    fake = FakeResultsTable(headings=["Label"], rows=[["stored text"]])
    monkeypatch.setattr(minimal, "_results_table", lambda _ij: fake)
    monkeypatch.setattr(minimal, "run_read", _direct_read)

    def fail_string(_column: int, _row: int) -> str:
        raise RuntimeError("string accessor failed")

    monkeypatch.setattr(fake, "getStringValue", fail_string)

    with pytest.raises(RuntimeError, match="string accessor failed"):
        minimal.get_results()


def test_get_results_retries_whole_page_for_exact_concurrent_modification(monkeypatch):
    fake = FakeResultsTable(headings=["Area", "Mean"], rows=[[1.0, 2.0], [3.0, 4.0]])
    concurrent_modification = type(
        "ConcurrentModificationException",
        (Exception,),
        {"__module__": "java.util"},
    )
    attempts = 0
    original_value = fake.getValueAsDouble

    def concurrent_once(column: int, row: int) -> float:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise concurrent_modification()
        return original_value(column, row)

    monkeypatch.setattr(fake, "getValueAsDouble", concurrent_once)
    bridge._reset_runtime_for_tests(ready_ij=FakeIJ(results=fake))
    monkeypatch.setattr(bridge, "_jvm_is_healthy", lambda _ij: True)
    try:
        result = minimal.get_results()
    finally:
        bridge._reset_runtime_for_tests()

    assert result["rows"] == [[1.0, 2.0], [3.0, 4.0]]
    assert all(cell is not None for row in result["rows"] for cell in row)
    assert attempts == 5
    assert fake.column_exists_calls == [0, 1, 0, 1]


def test_get_results_translates_nonallowlisted_accessor_errors(monkeypatch):
    fake = FakeResultsTable(headings=["Area"], rows=[[1.0]])
    attempts = 0

    def fail_numeric(_column: int, _row: int) -> float:
        nonlocal attempts
        attempts += 1
        raise RuntimeError("unexpected numeric accessor failure")

    monkeypatch.setattr(fake, "getValueAsDouble", fail_numeric)
    bridge._reset_runtime_for_tests(ready_ij=FakeIJ(results=fake))
    monkeypatch.setattr(bridge, "_jvm_is_healthy", lambda _ij: True)
    try:
        with pytest.raises(FijiError) as raised:
            minimal.get_results()
    finally:
        bridge._reset_runtime_for_tests()

    assert attempts == 1
    assert raised.value.code == "java_bridge_failure"
    assert raised.value.outcome is Outcome.FAILED


def test_get_results_returns_a_partial_nonzero_page(monkeypatch):
    fake = FakeResultsTable(headings=["Area"], rows=[[1], [2], [3]])
    monkeypatch.setattr(minimal, "_results_table", lambda _ij: fake)
    monkeypatch.setattr(minimal, "run_read", _direct_read)

    result = minimal.get_results(offset=2, limit=2)

    assert result == {
        "columns": ["Area"],
        "rows": [[3]],
        "offset": 2,
        "returned": 1,
        "total_rows": 3,
    }


def test_get_results_empty_table_keeps_headings(monkeypatch):
    fake = FakeResultsTable(headings=["Area"], rows=[])
    monkeypatch.setattr(minimal, "_results_table", lambda _ij: fake)
    monkeypatch.setattr(minimal, "run_read", _direct_read)

    assert minimal.get_results() == {
        "columns": ["Area"],
        "rows": [],
        "offset": 0,
        "returned": 0,
        "total_rows": 0,
    }


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"offset": -1}, "offset must be non-negative"),
        ({"limit": 0}, "limit must be between 1 and 5000"),
        ({"limit": 5_001}, "limit must be between 1 and 5000"),
    ],
)
def test_get_results_validates_page_before_java(monkeypatch, kwargs, message):
    monkeypatch.setattr(
        minimal,
        "run_read",
        lambda *_args: (_ for _ in ()).throw(AssertionError("called")),
    )

    with pytest.raises(FijiError, match=message) as raised:
        minimal.get_results(**kwargs)

    assert raised.value.outcome is Outcome.FAILED


def test_open_image_dispatches_once_and_returns_metadata(monkeypatch, tmp_path):
    path = tmp_path / "cells.tif"
    path.write_bytes(b"fixture")
    image = FakeImage(title="cells.tif", width=32, height=16)
    fake_ij = FakeIJ(opened=image)
    monkeypatch.setattr(minimal, "get_settings", lambda: Settings(tmp_path, "headless"))
    monkeypatch.setattr(minimal, "run_mutation", _direct_mutation(fake_ij))

    result = minimal.open_image(str(path))

    assert result == {
        "path": str(path.resolve()),
        "image": {
            "title": "cells.tif",
            "width": 32,
            "height": 16,
            "channels": 1,
            "slices": 1,
            "frames": 1,
            "bit_depth": 8,
        },
    }
    assert fake_ij.open_count == 1
    assert fake_ij.WindowManager.temp_current is image


def test_open_image_shows_image_in_gui_mode(monkeypatch, tmp_path):
    path = tmp_path / "cells.tif"
    path.write_bytes(b"fixture")
    image = FakeImage(title="cells.tif", width=32, height=16)
    fake_ij = FakeIJ(opened=image)
    monkeypatch.setattr(minimal, "get_settings", lambda: Settings(tmp_path, "gui"))
    monkeypatch.setattr(minimal, "run_mutation", _direct_mutation(fake_ij))

    minimal.open_image(str(path))

    assert fake_ij.open_count == 1
    assert image.show_count == 1
    assert fake_ij.WindowManager.temp_current is None


def test_open_image_rejects_missing_path_before_dispatch(monkeypatch, tmp_path):
    monkeypatch.setattr(
        minimal,
        "run_mutation",
        lambda *_args: (_ for _ in ()).throw(AssertionError("called")),
    )

    with pytest.raises(FijiError, match="Image file not found") as raised:
        minimal.open_image(str(tmp_path / "missing.tif"))

    assert raised.value.code == "missing_file"
    assert raised.value.outcome is Outcome.FAILED


def test_open_image_rejects_empty_path_before_dispatch(monkeypatch):
    monkeypatch.setattr(
        minimal,
        "run_mutation",
        lambda *_args: (_ for _ in ()).throw(AssertionError("called")),
    )

    with pytest.raises(FijiError, match="path must not be empty") as raised:
        minimal.open_image("   ")

    assert raised.value.outcome is Outcome.FAILED


def test_open_image_null_result_is_definite_failure_after_one_dispatch(
    monkeypatch, tmp_path
):
    path = tmp_path / "unreadable.tif"
    path.write_bytes(b"fixture")
    fake_ij = FakeIJ(opened=None)
    monkeypatch.setattr(minimal, "get_settings", lambda: Settings(tmp_path, "headless"))
    monkeypatch.setattr(minimal, "run_mutation", _direct_mutation(fake_ij))

    with pytest.raises(FijiError) as raised:
        minimal.open_image(str(path))

    assert fake_ij.open_count == 1
    assert raised.value.code == "unreadable_image"
    assert raised.value.outcome is Outcome.FAILED


@pytest.mark.parametrize(
    ("suffix", "image_format"),
    [
        (".tif", "tif"),
        (".tiff", "tiff"),
        (".jpg", "jpg"),
        (".png", "png"),
        (".gif", "gif"),
        (".bmp", "bmp"),
        (".fits", "fits"),
        (".pgm", "pgm"),
        (".zip", "zip"),
        (".raw", "raw"),
        (".avi", "avi"),
    ],
)
def test_save_image_preserves_exact_lowercase_suffix(
    monkeypatch, tmp_path, suffix, image_format
):
    output = tmp_path / "nested" / f"result{suffix}"
    fake_ij = FakeIJ(active=FakeImage("active", 4, 4))
    monkeypatch.setattr(minimal, "run_mutation", _direct_mutation(fake_ij))

    result = minimal.save_image(str(output))

    requested_path = output.resolve()
    assert result["path"] == str(requested_path)
    assert result["format"] == image_format
    assert result["image"]["title"] == "active"
    assert fake_ij.save_count == 1
    assert fake_ij.saved_path == str(requested_path)
    assert fake_ij.parent_exists_when_saved is True
    assert requested_path.is_file()


def test_save_image_preserves_tiff_when_tif_sibling_exists(monkeypatch, tmp_path):
    output = tmp_path / "nested" / "result.tiff"
    tif_sibling = output.with_suffix(".tif")
    tif_sibling.parent.mkdir()
    tif_sibling.write_bytes(b"original tif")
    fake_ij = FakeIJ(active=FakeImage("active", 4, 4))
    monkeypatch.setattr(minimal, "run_mutation", _direct_mutation(fake_ij))

    result = minimal.save_image(str(output))

    requested_path = output.resolve()
    assert result["path"] == str(requested_path)
    assert result["format"] == "tiff"
    assert fake_ij.save_count == 1
    assert fake_ij.saved_path == str(requested_path)
    assert requested_path.is_file()
    assert tif_sibling.read_bytes() == b"original tif"


@pytest.mark.parametrize(
    "suffix",
    [
        ".jpeg",
        ".JPEG",
        ".TIF",
        ".tIfF",
        ".JpG",
        ".PnG",
        ".GiF",
        ".BmP",
        ".FiTs",
        ".PgM",
        ".ZiP",
        ".RaW",
        ".AvI",
    ],
)
def test_save_image_rejects_nonexact_suffix_before_dispatch(
    monkeypatch, tmp_path, suffix
):
    monkeypatch.setattr(
        minimal,
        "run_mutation",
        lambda *_args: (_ for _ in ()).throw(AssertionError("called")),
    )

    with pytest.raises(FijiError, match="Unsupported image extension") as raised:
        minimal.save_image(str(tmp_path / f"result{suffix}"))

    assert raised.value.code == "unsupported_format"
    assert raised.value.outcome is Outcome.FAILED


def test_save_image_rejects_jpeg_without_touching_jpg_sibling(monkeypatch, tmp_path):
    output = tmp_path / "result.jpeg"
    jpg_sibling = output.with_suffix(".jpg")
    jpg_sibling.write_bytes(b"original jpg")
    monkeypatch.setattr(
        minimal,
        "run_mutation",
        lambda *_args: (_ for _ in ()).throw(AssertionError("called")),
    )

    with pytest.raises(FijiError, match="Unsupported image extension") as raised:
        minimal.save_image(str(output))

    assert raised.value.code == "unsupported_format"
    assert raised.value.outcome is Outcome.FAILED
    assert jpg_sibling.read_bytes() == b"original jpg"


def test_save_image_rejects_unsupported_suffix_before_dispatch(monkeypatch, tmp_path):
    monkeypatch.setattr(
        minimal,
        "run_mutation",
        lambda *_args: (_ for _ in ()).throw(AssertionError("called")),
    )

    with pytest.raises(FijiError, match="Unsupported image extension") as raised:
        minimal.save_image(str(tmp_path / "result.webp"))

    assert raised.value.outcome is Outcome.FAILED


def test_save_image_rejects_existing_directory_before_dispatch(monkeypatch, tmp_path):
    output = tmp_path / "output.png"
    output.mkdir()
    monkeypatch.setattr(
        minimal,
        "run_mutation",
        lambda *_args: (_ for _ in ()).throw(AssertionError("called")),
    )

    with pytest.raises(FijiError, match="directory") as raised:
        minimal.save_image(str(output))

    assert raised.value.outcome is Outcome.FAILED


def test_save_image_rejects_existing_exact_output_in_prepare_under_lock(
    monkeypatch, tmp_path
):
    output = tmp_path / "result.tiff"
    output.write_bytes(b"original tiff")
    fake_ij = FakeIJ(active=FakeImage("active", 4, 4))
    bridge._reset_runtime_for_tests(ready_ij=fake_ij)
    monkeypatch.setattr(bridge, "_jvm_is_healthy", lambda _ij: True)
    try:
        with pytest.raises(FijiError, match="already exists") as raised:
            minimal.save_image(str(output))
    finally:
        bridge._reset_runtime_for_tests()

    assert raised.value.code == "output_exists"
    assert raised.value.outcome is Outcome.FAILED
    assert fake_ij.save_count == 0
    assert output.read_bytes() == b"original tiff"


def test_save_image_clears_stale_imagej_error_before_dispatch(monkeypatch, tmp_path):
    output = tmp_path / "result.png"
    fake_ij = FakeIJ(
        active=FakeImage("active", 4, 4),
        error_messages=["stale error", None],
    )
    monkeypatch.setattr(minimal, "run_mutation", _direct_mutation(fake_ij))

    result = minimal.save_image(str(output))

    assert result["path"] == str(output.resolve())
    assert fake_ij.save_count == 1
    assert fake_ij.error_message_calls == 2


def test_save_image_reports_new_imagej_error_after_one_dispatch(monkeypatch, tmp_path):
    output = tmp_path / "result.png"
    fake_ij = FakeIJ(
        active=FakeImage("active", 4, 4),
        error_messages=[None, "disk full"],
    )
    monkeypatch.setattr(minimal, "run_mutation", _direct_mutation(fake_ij))

    with pytest.raises(FijiError, match="disk full") as raised:
        minimal.save_image(str(output))

    assert raised.value.code == "save_failed"
    assert raised.value.outcome is Outcome.UNKNOWN
    assert fake_ij.save_count == 1
    assert fake_ij.error_message_calls == 2


def test_save_image_rejects_silent_no_file_after_one_dispatch(monkeypatch, tmp_path):
    output = tmp_path / "result.png"
    fake_ij = FakeIJ(
        active=FakeImage("active", 4, 4),
        error_messages=[None, None],
        write_saved_file=False,
    )
    monkeypatch.setattr(minimal, "run_mutation", _direct_mutation(fake_ij))

    with pytest.raises(FijiError, match="did not create") as raised:
        minimal.save_image(str(output))

    assert raised.value.code == "save_failed"
    assert raised.value.outcome is Outcome.UNKNOWN
    assert fake_ij.save_count == 1
    assert fake_ij.error_message_calls == 2


def test_save_image_requires_active_image_before_dispatch(monkeypatch, tmp_path):
    fake_ij = FakeIJ(active=None)
    monkeypatch.setattr(minimal, "run_mutation", _direct_mutation(fake_ij))

    with pytest.raises(FijiError, match="No active image") as raised:
        minimal.save_image(str(tmp_path / "result.tif"))

    assert fake_ij.save_count == 0
    assert raised.value.code == "no_active_image"
    assert raised.value.outcome is Outcome.FAILED


def test_save_image_requires_filename_suffix_before_dispatch(monkeypatch, tmp_path):
    monkeypatch.setattr(
        minimal,
        "run_mutation",
        lambda *_args: (_ for _ in ()).throw(AssertionError("called")),
    )

    with pytest.raises(FijiError, match="filename extension") as raised:
        minimal.save_image(str(tmp_path / "result"))

    assert raised.value.outcome is Outcome.FAILED


def test_get_state_reports_complete_live_shape(monkeypatch):
    active = FakeImage(
        "temporary",
        32,
        16,
        image_id=2,
        channels=2,
        slices=3,
        frames=4,
        bit_depth=16,
    )
    listed = FakeImage("listed", 8, 6, image_id=1)
    fake_ij = FakeIJ(
        version="2.16.0/1.54p",
        active=active,
        open_images=[listed],
        results=FakeResultsTable(headings=["Area", "Mean"], rows=[[1, 2]]),
    )
    calls = 0

    def read_once(_name, function):
        nonlocal calls
        calls += 1
        return function(fake_ij)

    monkeypatch.setattr(
        minimal, "get_settings", lambda: Settings(Path("/fiji"), "headless")
    )
    monkeypatch.setattr(minimal, "runtime_snapshot", lambda: {"lifecycle": "READY"})
    monkeypatch.setattr(minimal, "run_read", read_once)

    result = minimal.get_state()

    assert set(result) == {
        "lifecycle",
        "version",
        "mode",
        "active_image",
        "open_images",
        "results",
    }
    assert result["lifecycle"] == "READY"
    assert result["version"] == "2.16.0/1.54p"
    assert result["mode"] == "headless"
    assert result["active_image"]["title"] == "temporary"
    assert [image["title"] for image in result["open_images"]] == [
        "listed",
        "temporary",
    ]
    assert result["results"] == {"columns": ["Area", "Mean"], "total_rows": 1}
    assert calls == 1


def test_get_state_deduplicates_active_image_by_imagej_id(monkeypatch):
    active = FakeImage("active", 32, 16, image_id=7)
    fake_ij = FakeIJ(active=active, open_images=[active])
    monkeypatch.setattr(
        minimal, "get_settings", lambda: Settings(Path("/fiji"), "headless")
    )
    monkeypatch.setattr(minimal, "runtime_snapshot", lambda: {"lifecycle": "READY"})
    monkeypatch.setattr(minimal, "run_read", lambda _name, fn: fn(fake_ij))

    result = minimal.get_state()

    assert [image["title"] for image in result["open_images"]] == ["active"]
