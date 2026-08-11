"""Thin Fiji state, image I/O, and Results-table handlers."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from fiji_mcp.bridge import (
    FijiError,
    Outcome,
    get_settings,
    image_summary,
    run_mutation,
    run_read,
    runtime_snapshot,
    to_jsonable,
)

_SAVE_SUFFIXES = {
    ".tif": ".tif",
    ".tiff": ".tif",
    ".png": ".png",
    ".jpg": ".jpg",
    ".jpeg": ".jpg",
    ".gif": ".gif",
    ".bmp": ".bmp",
    ".fits": ".fits",
    ".pgm": ".pgm",
    ".zip": ".zip",
    ".raw": ".raw",
    ".avi": ".avi",
}


def _failed(code: str, message: str, recovery: str) -> FijiError:
    return FijiError(
        code,
        message,
        retryable=False,
        outcome=Outcome.FAILED,
        recovery=recovery,
    )


def _save_failed(message: str) -> FijiError:
    return FijiError(
        "save_failed",
        message,
        retryable=False,
        outcome=Outcome.UNKNOWN,
        recovery="Inspect the output path before retrying.",
    )


def _resolve_path(path: str) -> Path:
    if not isinstance(path, str) or not path.strip():
        raise _failed(
            "invalid_path",
            "path must not be empty.",
            "Provide a non-empty local file path and retry.",
        )
    try:
        return Path(path).expanduser().resolve()
    except (OSError, RuntimeError, ValueError) as error:
        raise _failed(
            "invalid_path",
            f"Could not resolve path: {error}",
            "Provide a valid local file path and retry.",
        ) from error


def _results_table(ij: Any) -> Any:
    return ij.ResultsTable.getResultsTable()


def _result_cell(results_table: Any, column: int, row: int) -> Any:
    try:
        value = results_table.getValueAsDouble(column, row)
    except Exception:
        return None
    if value is None or isinstance(value, str):
        return value

    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return to_jsonable(value)
    if math.isnan(numeric):
        try:
            text_value = results_table.getStringValue(column, row)
        except Exception:
            text_value = None
        if text_value is not None and str(text_value) != "NaN":
            return str(text_value)
    return to_jsonable(value)


def _read_results(ij: Any, offset: int, limit: int) -> dict[str, Any]:
    """Read one ordered page from Fiji's live Results table."""
    results_table = _results_table(ij)
    if results_table is None:
        return {
            "columns": [],
            "rows": [],
            "offset": offset,
            "returned": 0,
            "total_rows": 0,
        }

    total_rows = int(results_table.size())
    column_count = max(int(results_table.getLastColumn()) + 1, 0)
    columns = [
        ""
        if (heading := results_table.getColumnHeading(column)) is None
        else str(heading)
        for column in range(column_count)
    ]
    stop = min(total_rows, offset + limit)
    rows = [
        [_result_cell(results_table, column, row) for column in range(column_count)]
        for row in range(offset, stop)
    ]
    return {
        "columns": columns,
        "rows": rows,
        "offset": offset,
        "returned": len(rows),
        "total_rows": total_rows,
    }


def _validate_page(offset: int, limit: int) -> None:
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise _failed(
            "invalid_pagination",
            "offset must be non-negative.",
            "Use an offset of zero or greater and retry.",
        )
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 5_000:
        raise _failed(
            "invalid_pagination",
            "limit must be between 1 and 5000.",
            "Use a limit from 1 through 5000 and retry.",
        )


def _image_id(image: Any) -> int | None:
    try:
        return int(image.getID())
    except Exception:
        return None


def get_results(offset: int = 0, limit: int = 500) -> dict[str, Any]:
    """Return one ordered page from Fiji's live Results table."""
    _validate_page(offset, limit)
    return run_read(
        "get_results", lambda ij: _read_results(ij, offset=offset, limit=limit)
    )


def get_state() -> dict[str, Any]:
    """Return one live snapshot of Fiji's images and Results table."""
    settings = get_settings()

    def read_state(ij: Any) -> dict[str, Any]:
        window_manager = ij.WindowManager
        active = window_manager.getCurrentImage()
        open_images: list[dict[str, Any]] = []
        seen_ids: set[int] = set()
        image_ids = window_manager.getIDList()
        for listed_id in [] if image_ids is None else image_ids:
            image = window_manager.getImage(listed_id)
            if image is None:
                continue
            image_id = _image_id(image)
            if image_id is not None and image_id in seen_ids:
                continue
            open_images.append(image_summary(image))
            if image_id is not None:
                seen_ids.add(image_id)

        active_image = image_summary(active) if active is not None else None
        active_id = _image_id(active) if active is not None else None
        if active_image is not None and (
            active_id is None or active_id not in seen_ids
        ):
            open_images.append(active_image)

        results = _read_results(ij, offset=0, limit=1)
        return {
            "lifecycle": runtime_snapshot()["lifecycle"],
            "version": str(ij.getVersion()),
            "mode": settings.mode,
            "active_image": active_image,
            "open_images": open_images,
            "results": {
                "columns": results["columns"],
                "total_rows": results["total_rows"],
            },
        }

    return run_read("get_state", read_state)


def open_image(path: str) -> dict[str, Any]:
    """Open one local image and make it Fiji's current image."""
    image_path = _resolve_path(path)
    try:
        exists = image_path.is_file()
    except OSError as error:
        raise _failed(
            "invalid_path",
            f"Could not check image path: {error}",
            "Check the local image path and retry.",
        ) from error
    if not exists:
        raise _failed(
            "missing_file",
            f"Image file not found: {image_path}",
            "Check the local image path and retry.",
        )
    settings = get_settings()

    def prepare(_ij: Any) -> Path:
        return image_path

    def dispatch(ij: Any, prepared_path: Path) -> dict[str, Any]:
        image = ij.IJ.openImage(str(prepared_path))
        if image is None:
            raise _failed(
                "unreadable_image",
                f"Fiji could not read image: {prepared_path}",
                "Use a format Fiji supports or open it through a plugin/script.",
            )
        if settings.mode == "headless":
            ij.WindowManager.setTempCurrentImage(image)
        else:
            image.show()
        return {"path": str(prepared_path), "image": image_summary(image)}

    return run_mutation("open_image", prepare, dispatch)


def save_image(path: str) -> dict[str, Any]:
    """Save Fiji's active image using the filename's extension."""
    requested_path = _resolve_path(path)
    requested_suffix = requested_path.suffix.lower()
    if not requested_suffix:
        raise _failed(
            "invalid_path",
            "save_image requires a filename extension.",
            "Add an output filename extension such as .tif or .png and retry.",
        )
    canonical_suffix = _SAVE_SUFFIXES.get(requested_suffix)
    if canonical_suffix is None:
        raise _failed(
            "unsupported_format",
            f"Unsupported image extension: {requested_path.suffix}",
            "Use a supported image extension and retry.",
        )
    effective_path = requested_path.with_suffix(canonical_suffix)
    for target_path in (requested_path, effective_path):
        try:
            is_directory = target_path.is_dir()
        except OSError as error:
            raise _failed(
                "invalid_path",
                f"Could not check output path: {error}",
                "Choose a writable output path and retry.",
            ) from error
        if is_directory:
            raise _failed(
                "invalid_path",
                f"Output path is a directory: {target_path}",
                "Choose an output filename instead and retry.",
            )
    image_format = canonical_suffix.removeprefix(".")

    def prepare(ij: Any) -> Any:
        image = ij.WindowManager.getCurrentImage()
        if image is None:
            raise _failed(
                "no_active_image",
                "No active image is available to save.",
                "Open or select an image, then retry.",
            )
        try:
            effective_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise _failed(
                "invalid_path",
                f"Could not create output directory: {error}",
                "Choose a writable output path and retry.",
            ) from error
        return image

    def dispatch(ij: Any, image: Any) -> dict[str, Any]:
        ij.IJ.getErrorMessage()
        ij.IJ.save(image, str(effective_path))
        error_message = ij.IJ.getErrorMessage()
        if error_message:
            raise _save_failed(f"Fiji could not save image: {error_message}")
        try:
            saved = effective_path.is_file()
        except OSError as error:
            raise _save_failed(f"Could not verify saved image: {error}") from error
        if not saved:
            raise _save_failed(
                f"Fiji did not create the requested image: {effective_path}"
            )
        return {
            "path": str(effective_path),
            "format": image_format,
            "image": image_summary(image),
        }

    return run_mutation("save_image", prepare, dispatch)
