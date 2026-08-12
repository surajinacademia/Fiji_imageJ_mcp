"""Thin Fiji state, image I/O, and Results-table handlers."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Literal

from fastmcp.tools.tool import ToolResult
from fastmcp.utilities.types import Image as MCPImage

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
from fiji_mcp.imaging import (
    RenderedPNG,
    compare_paths,
    render_active_image,
    render_results,
)

_SAVE_FORMATS = {
    ".tif": "tif",
    ".tiff": "tiff",
    ".jpg": "jpg",
    ".png": "png",
    ".gif": "gif",
    ".bmp": "bmp",
    ".fits": "fits",
    ".pgm": "pgm",
    ".zip": "zip",
    ".raw": "raw",
    ".avi": "avi",
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


def _script_failed(error_text: str) -> FijiError:
    detail = error_text.strip()[-_LOG_TAIL_CHARS:]
    return FijiError(
        "script_failed",
        f"Groovy script failed: {detail}",
        retryable=False,
        outcome=Outcome.UNKNOWN,
        recovery="Correct the reported Groovy error, inspect Fiji state, and retry.",
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
    value = results_table.getValueAsDouble(column, row)
    numeric = float(value)
    if math.isnan(numeric):
        text_value = results_table.getStringValue(column, row)
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
    columns: list[str] = []
    defined_columns: list[bool] = []
    for column in range(column_count):
        heading = results_table.getColumnHeading(column)
        columns.append("" if heading is None else str(heading))
        defined_columns.append(bool(results_table.columnExists(column)))
    stop = min(total_rows, offset + limit)
    rows = [
        [
            _result_cell(results_table, column, row) if defined else None
            for column, defined in enumerate(defined_columns)
        ]
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
    requested_suffix = requested_path.suffix
    if not requested_suffix:
        raise _failed(
            "invalid_path",
            "save_image requires a filename extension.",
            "Add an output filename extension such as .tif or .png and retry.",
        )
    image_format = _SAVE_FORMATS.get(requested_suffix)
    if image_format is None:
        raise _failed(
            "unsupported_format",
            f"Unsupported image extension: {requested_path.suffix}",
            f"Use one of these exact lowercase suffixes: {', '.join(_SAVE_FORMATS)}.",
        )
    try:
        is_directory = requested_path.is_dir()
    except OSError as error:
        raise _failed(
            "invalid_path",
            f"Could not check output path: {error}",
            "Choose a writable output path and retry.",
        ) from error
    if is_directory:
        raise _failed(
            "invalid_path",
            f"Output path is a directory: {requested_path}",
            "Choose an output filename instead and retry.",
        )

    def prepare(ij: Any) -> Any:
        image = ij.WindowManager.getCurrentImage()
        if image is None:
            raise _failed(
                "no_active_image",
                "No active image is available to save.",
                "Open or select an image, then retry.",
            )
        try:
            requested_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise _failed(
                "invalid_path",
                f"Could not create output directory: {error}",
                "Choose a writable output path and retry.",
            ) from error
        try:
            output_exists = requested_path.exists()
        except OSError as error:
            raise _failed(
                "invalid_path",
                f"Could not check output path: {error}",
                "Choose a writable output path and retry.",
            ) from error
        if output_exists:
            raise _failed(
                "output_exists",
                f"Output path already exists: {requested_path}",
                "Choose a new output path and retry.",
            )
        return image

    def dispatch(ij: Any, image: Any) -> dict[str, Any]:
        ij.IJ.getErrorMessage()
        ij.IJ.save(image, str(requested_path))
        error_message = ij.IJ.getErrorMessage()
        if error_message:
            raise _save_failed(f"Fiji could not save image: {error_message}")
        try:
            saved = requested_path.is_file()
        except OSError as error:
            raise _save_failed(f"Could not verify saved image: {error}") from error
        if not saved:
            raise _save_failed(
                f"Fiji did not create the requested image: {requested_path}"
            )
        return {
            "path": str(requested_path),
            "format": image_format,
            "image": image_summary(image),
        }

    return run_mutation("save_image", prepare, dispatch)


_COMMAND_LIMIT_MIN = 1
_COMMAND_LIMIT_MAX = 100
_LOG_TAIL_CHARS = 4_000
_JSON_PARAMETER_TYPES = frozenset(
    {
        "boolean",
        "byte",
        "short",
        "int",
        "long",
        "float",
        "double",
        "char",
        "java.lang.Boolean",
        "java.lang.Byte",
        "java.lang.Short",
        "java.lang.Integer",
        "java.lang.Long",
        "java.lang.Float",
        "java.lang.Double",
        "java.lang.Character",
        "java.lang.String",
        "java.io.File",
        "java.nio.file.Path",
    }
)


def _command_text(value: Any) -> str:
    """Return one normalized string from command metadata."""
    return "" if value is None else str(value).strip()


def _legacy_descriptor(command: dict[str, Any]) -> str:
    descriptor = command.get("_legacy_descriptor")
    return (
        _command_text(descriptor)
        if descriptor is not None
        else _command_text(command.get("class_name"))
    )


def _command_sort_key(
    command: dict[str, Any],
) -> tuple[str, str, str, str, str, str, str, str]:
    name = _command_text(command.get("name"))
    class_name = _command_text(command.get("class_name"))
    descriptor = _legacy_descriptor(command)
    menu_path = _command_text(command.get("menu_path"))
    return (
        name.casefold(),
        name,
        class_name.casefold(),
        class_name,
        descriptor.casefold(),
        descriptor,
        menu_path.casefold(),
        menu_path,
    )


def _public_command(command: dict[str, Any]) -> dict[str, Any]:
    """Drop bridge-local metadata before returning a catalog record."""
    return {key: value for key, value in command.items() if not key.startswith("_")}


def _command_service(ij: Any) -> Any:
    """Resolve the supported SciJava command service from Fiji's context."""
    import scyjava as sj

    command_service = sj.jimport("org.scijava.command.CommandService")
    return ij.context().service(command_service)


def _imagej1_menus() -> Any:
    """Resolve the ImageJ1 menu registry class through the supported bridge."""
    import scyjava as sj

    return sj.jimport("ij.Menus")


def _input_type_name(item: Any) -> str:
    input_type = item.getType()
    get_name = getattr(input_type, "getName", None)
    return _command_text(get_name() if callable(get_name) else input_type)


def _is_autofilled(item: Any) -> bool:
    try:
        is_auto_fill = getattr(item, "isAutoFill", None)
        return bool(is_auto_fill()) if callable(is_auto_fill) else False
    except Exception:
        return False


def _scijava_metadata_and_route(
    command_info: Any,
) -> tuple[list[dict[str, Any]], str]:
    inputs: list[dict[str, Any]] = []
    route = "structured_parameters"
    for item in command_info.inputs():
        input_type = _input_type_name(item)
        required = bool(item.isRequired())
        inputs.append(
            {
                "name": _command_text(item.getName()),
                "type": input_type,
                "required": required,
                "description": _command_text(item.getDescription()),
            }
        )
        if (
            required
            and not _is_autofilled(item)
            and input_type not in _JSON_PARAMETER_TYPES
        ):
            route = "script_fallback"
    return inputs, route


def _scijava_menu_path(command_info: Any) -> str:
    try:
        get_menu_path = getattr(command_info, "getMenuPath", None)
        if not callable(get_menu_path):
            return ""
        menu_path = get_menu_path()
        if menu_path is None:
            return ""
        if isinstance(menu_path, str):
            return _command_text(menu_path)
        get_menu_string = getattr(menu_path, "getMenuString", None)
        return _command_text(get_menu_string()) if callable(get_menu_string) else ""
    except Exception:
        return ""


def _parse_legacy_descriptor(value: Any) -> tuple[str, str]:
    """Split a menu descriptor's delegate class without inspecting arguments."""
    descriptor = "" if value is None else str(value)
    class_name = descriptor.strip().split("(", maxsplit=1)[0].strip()
    return class_name, descriptor


def _is_plain_legacy_delegate(command: dict[str, Any]) -> bool:
    class_name = _command_text(command.get("class_name"))
    return bool(class_name) and _legacy_descriptor(command) == class_name


def _legacy_action_identity(command: dict[str, Any]) -> tuple[str, str, str]:
    return (
        _command_text(command.get("name")),
        _command_text(command.get("class_name")),
        _legacy_descriptor(command),
    )


def _deduplicate_commands(commands: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Prefer matching SciJava commands without collapsing legacy actions."""
    scijava_by_class: dict[str, dict[str, Any]] = {}
    for command in commands:
        class_name = _command_text(command.get("class_name"))
        if command.get("family") != "scijava" or not class_name:
            continue
        existing = scijava_by_class.get(class_name)
        if existing is None or _command_sort_key(command) < _command_sort_key(existing):
            scijava_by_class[class_name] = command

    deduplicated: list[dict[str, Any]] = []
    seen_scijava_classes: set[str] = set()
    seen_legacy_actions: set[tuple[str, str, str]] = set()
    for command in commands:
        class_name = _command_text(command.get("class_name"))
        family = command.get("family")
        if family == "scijava" and class_name:
            if class_name in seen_scijava_classes:
                continue
            seen_scijava_classes.add(class_name)
            deduplicated.append(scijava_by_class[class_name])
            continue

        if family != "imagej1" or not class_name:
            deduplicated.append(command)
            continue

        matching_scijava = scijava_by_class.get(class_name)
        if (
            matching_scijava is not None
            and _is_plain_legacy_delegate(command)
            and _command_text(matching_scijava.get("name"))
            == _command_text(command.get("name"))
        ):
            continue

        identity = _legacy_action_identity(command)
        if identity in seen_legacy_actions:
            continue
        seen_legacy_actions.add(identity)
        deduplicated.append(command)

    return sorted(deduplicated, key=_command_sort_key)


def _collect_commands(ij: Any) -> list[dict[str, Any]]:
    """Merge the SciJava registry and ImageJ1 menu registry deterministically."""
    service = _command_service(ij)
    commands: list[dict[str, Any]] = []
    for command_info in service.getCommands():
        name = _command_text(command_info.getTitle())
        inputs, route = _scijava_metadata_and_route(command_info)
        commands.append(
            {
                "name": name,
                "class_name": _command_text(command_info.getDelegateClassName()),
                "menu_path": _scijava_menu_path(command_info),
                "family": "scijava",
                "invocation_route": route,
                "inputs": inputs,
                "_command_info": command_info,
                "_command_service": service,
            }
        )

    for entry in _imagej1_menus().getCommands().entrySet():
        name = _command_text(entry.getKey())
        class_name, descriptor = _parse_legacy_descriptor(entry.getValue())
        commands.append(
            {
                "name": name,
                "class_name": class_name,
                "menu_path": "",
                "family": "imagej1",
                "invocation_route": ("legacy_options" if name else "script_fallback"),
                "inputs": [],
                "_legacy_descriptor": descriptor,
            }
        )
    return _deduplicate_commands(commands)


def _command_candidates_text(commands: list[dict[str, Any]]) -> str:
    candidates = sorted(
        [
            (
                _command_text(command.get("name")) or "<unnamed command>",
                _command_text(command.get("class_name")) or "<no delegate class>",
                _legacy_descriptor(command),
            )
            for command in commands
        ],
        key=lambda candidate: (
            candidate[0].casefold(),
            candidate[1].casefold(),
            candidate[0],
            candidate[1],
            candidate[2].casefold(),
            candidate[2],
        ),
    )
    return ", ".join(f"{name} ({class_name})" for name, class_name, _ in candidates)


def _ambiguous_command(
    name: str,
    candidates: list[dict[str, Any]],
    commands: list[dict[str, Any]],
) -> FijiError:
    delegate_classes = {
        _command_text(command.get("class_name")) for command in candidates
    }
    display_names = [_command_text(command.get("name")) for command in candidates]
    catalog_names = [_command_text(command.get("name")) for command in commands]
    catalog_classes = [_command_text(command.get("class_name")) for command in commands]
    recovery = "Use run_script with IJM or Groovy for this command."
    if (
        len(delegate_classes) == 1
        and all(display_names)
        and all(
            catalog_names.count(display_name) == 1 for display_name in display_names
        )
        and all(display_name not in catalog_classes for display_name in display_names)
    ):
        recovery = (
            "Use an exact case-sensitive display name from search_commands and retry."
        )
    elif (
        len(delegate_classes) > 1
        and all(delegate_classes)
        and all(
            catalog_classes.count(delegate_class) == 1
            for delegate_class in delegate_classes
        )
    ):
        recovery = "Use an exact delegate class from search_commands and retry."
    return _failed(
        "ambiguous_command",
        f"Command '{name}' is ambiguous. Candidate commands: "
        f"{_command_candidates_text(candidates)}.",
        recovery,
    )


def _resolve_command(commands: list[dict[str, Any]], name: str) -> dict[str, Any]:
    """Resolve by exact class, exact title, then unique case-insensitive title."""
    target = _command_text(name)
    class_matches = [
        command
        for command in commands
        if _command_text(command.get("class_name")) == target
    ]
    if len(class_matches) == 1:
        return class_matches[0]
    if len(class_matches) > 1:
        raise _ambiguous_command(target, class_matches, commands)

    exact_name_matches = [
        command for command in commands if _command_text(command.get("name")) == target
    ]
    if len(exact_name_matches) == 1:
        return exact_name_matches[0]
    if len(exact_name_matches) > 1:
        raise _ambiguous_command(target, exact_name_matches, commands)

    folded_target = target.casefold()
    folded_name_matches = [
        command
        for command in commands
        if _command_text(command.get("name")).casefold() == folded_target
    ]
    if len(folded_name_matches) == 1:
        return folded_name_matches[0]
    if len(folded_name_matches) > 1:
        raise _ambiguous_command(target, folded_name_matches, commands)

    raise _failed(
        "command_not_found",
        f"No command matches '{target}'.",
        "Use search_commands to find an exact command name or delegate class and retry.",
    )


def _invocation_route(command: dict[str, Any]) -> str:
    route = command.get("invocation_route")
    if route in {"structured_parameters", "legacy_options", "script_fallback"}:
        return str(route)
    if command.get("family") == "scijava":
        return "structured_parameters"
    if command.get("family") == "imagej1":
        return "legacy_options"
    return "script_fallback"


def _validate_route_inputs(
    command: dict[str, Any],
    *,
    parameters: dict[str, Any] | None,
    options: str | None,
) -> str:
    """Reject inputs that cannot be safely dispatched through this route."""
    route = _invocation_route(command)
    name = _command_text(command.get("name")) or "the selected command"
    if route == "script_fallback":
        raise _failed(
            "invalid_parameter",
            f"Command '{name}' requires a script fallback; use run_script instead.",
            "Use run_script with IJM or Groovy for this command.",
        )
    if route == "legacy_options" and parameters is not None:
        raise _failed(
            "invalid_parameter",
            f"Command '{name}' accepts a legacy options string; use run_script "
            "for structured or custom input.",
            "Pass options=... for this ImageJ1 command, or use run_script.",
        )
    if route == "structured_parameters" and options is not None:
        raise _failed(
            "invalid_parameter",
            f"Command '{name}' accepts structured parameters; use run_script "
            "for a legacy options string.",
            "Pass parameters={...} for this SciJava command, or use run_script.",
        )
    return route


def _validate_command_arguments(
    name: str,
    parameters: dict[str, Any] | None,
    options: str | None,
) -> str:
    if not isinstance(name, str) or not name.strip():
        raise _failed(
            "invalid_parameter",
            "name must be a non-empty command name or delegate class.",
            "Use search_commands to find a command name or delegate class and retry.",
        )
    if parameters is not None and not isinstance(parameters, dict):
        raise _failed(
            "invalid_parameter",
            "parameters must be a dictionary when provided.",
            "Pass structured parameters as a dictionary or use options for ImageJ1.",
        )
    if options is not None and not isinstance(options, str):
        raise _failed(
            "invalid_parameter",
            "options must be a string when provided.",
            "Pass a legacy options string or use structured parameters for SciJava.",
        )
    if parameters is not None and options is not None:
        raise _failed(
            "invalid_parameter",
            "parameters and options are mutually exclusive.",
            "Pass structured parameters or one legacy options string, not both.",
        )
    return name.strip()


def _active_image_after_execution(ij: Any) -> dict[str, Any] | None:
    image = ij.WindowManager.getCurrentImage()
    return image_summary(image) if image is not None else None


def _log_tail(ij: Any) -> str:
    log = ij.IJ.getLog()
    return "" if log is None else str(log)[-_LOG_TAIL_CHARS:]


def _run_ijm_macro(ij: Any, code: str) -> tuple[Any, str]:
    """Run one synchronous IJM macro while retaining its bounded stdout tail."""
    import scyjava as sj

    system = sj.jimport("java.lang.System")
    byte_array_output_stream = sj.jimport("java.io.ByteArrayOutputStream")
    print_stream = sj.jimport("java.io.PrintStream")
    previous_stdout = system.out
    captured = byte_array_output_stream()
    stream = print_stream(captured, True, "UTF-8")
    try:
        system.setOut(stream)
        result = ij.IJ.runMacro(code)
        stream.flush()
        return result, str(captured.toString("UTF-8"))[-_LOG_TAIL_CHARS:]
    finally:
        system.setOut(previous_stdout)
        try:
            stream.close()
        except Exception:
            pass


def _run_groovy_script(ij: Any, code: str) -> Any:
    """Run one SciJava Groovy module synchronously on the bridge thread."""
    import scyjava as sj

    script_info = sj.jimport("org.scijava.script.ScriptInfo")
    string_reader = sj.jimport("java.io.StringReader")
    string_writer = sj.jimport("java.io.StringWriter")
    info = script_info(ij.context(), "fiji-mcp.groovy", string_reader(code))
    # SciJava 2.100.0 initializes ScriptInfo parameter maps lazily via inputs().
    info.inputs()
    info.parseParameters()
    module = info.createModule()
    module.setContext(ij.context())
    module.initialize()
    errors = string_writer()
    module.setErrorWriter(errors)
    module.run()
    error_text = str(errors.toString())
    if error_text.strip():
        raise _script_failed(error_text)
    return module.getOutputs()


def _combined_log_tail(log_tail: str, captured_stdout: str) -> str:
    return f"{log_tail}{captured_stdout}"[-_LOG_TAIL_CHARS:]


def _command_info_for(ij: Any, command: dict[str, Any]) -> tuple[Any, Any]:
    """Return the catalogued SciJava service and its exact CommandInfo."""
    command_info = command.get("_command_info")
    service = command.get("_command_service")
    if command_info is not None and service is not None:
        return service, command_info

    service = _command_service(ij)
    class_name = _command_text(command.get("class_name"))
    name = _command_text(command.get("name"))
    matches = [
        info
        for info in service.getCommands()
        if _command_text(info.getDelegateClassName()) == class_name
        and _command_text(info.getTitle()) == name
    ]
    if len(matches) == 1:
        return service, matches[0]
    raise _failed(
        "command_not_found",
        f"SciJava metadata for command '{name}' is no longer available.",
        "Run search_commands again and choose an exact command name or delegate class.",
    )


def _command_response(
    ij: Any,
    command: dict[str, Any],
    route: str,
    outputs: Any,
) -> dict[str, Any]:
    return {
        "name": _command_text(command.get("name")),
        "class_name": _command_text(command.get("class_name")),
        "family": _command_text(command.get("family")),
        "invocation_route": route,
        "outputs": to_jsonable(outputs),
        "log_tail": _log_tail(ij),
        "active_image": _active_image_after_execution(ij),
    }


def search_commands(query: str, limit: int = 20) -> dict[str, Any]:
    """Search the deterministic Fiji command catalog by metadata substring."""
    if not isinstance(query, str):
        raise _failed(
            "invalid_parameter",
            "query must be a string.",
            "Pass a command name, class, menu-path fragment, or an empty string.",
        )
    if (
        isinstance(limit, bool)
        or not isinstance(limit, int)
        or not (_COMMAND_LIMIT_MIN <= limit <= _COMMAND_LIMIT_MAX)
    ):
        raise _failed(
            "invalid_parameter",
            "limit must be between 1 and 100.",
            "Use a limit from 1 through 100 and retry.",
        )
    needle = query.strip().casefold()

    def search(ij: Any) -> dict[str, Any]:
        catalog = _collect_commands(ij)
        matches = [
            command
            for command in catalog
            if needle in _command_text(command.get("name")).casefold()
            or needle in _command_text(command.get("class_name")).casefold()
            or needle in _command_text(command.get("menu_path")).casefold()
        ]
        returned = [_public_command(command) for command in matches[:limit]]
        return {
            "query": query,
            "returned": len(returned),
            "total": len(matches),
            "commands": returned,
        }

    return run_read("search_commands", search)


def run_command(
    name: str,
    parameters: dict[str, Any] | None = None,
    options: str | None = None,
) -> dict[str, Any]:
    """Run one resolved SciJava or ImageJ1 command exactly once."""
    target = _validate_command_arguments(name, parameters, options)

    def prepare(
        ij: Any,
    ) -> tuple[dict[str, Any], str, Any | None, Any | None, Any | None]:
        command = _resolve_command(_collect_commands(ij), target)
        route = _validate_route_inputs(
            command,
            parameters=parameters,
            options=options,
        )
        if route == "structured_parameters":
            service, command_info = _command_info_for(ij, command)
            input_map = ij.py.to_java(parameters or {})
            return command, route, service, command_info, input_map
        return command, route, None, None, None

    def dispatch(
        ij: Any,
        prepared: tuple[dict[str, Any], str, Any | None, Any | None, Any | None],
    ) -> dict[str, Any]:
        command, route, service, command_info, input_map = prepared
        if route == "structured_parameters":
            assert service is not None
            assert command_info is not None
            command_module = service.run(command_info, True, input_map).get()
            return _command_response(
                ij,
                command,
                route,
                command_module.getOutputs(),
            )

        ij.IJ.run(_command_text(command.get("name")), options or "")
        return _command_response(ij, command, route, None)

    return run_mutation("run_command", prepare, dispatch)


def _validate_script_arguments(language: str, code: str) -> str:
    if not isinstance(language, str) or language not in {"ijm", "groovy"}:
        raise _failed(
            "unsupported_language",
            "language must be ijm or groovy.",
            "Use language='ijm' or language='groovy' and retry.",
        )
    if not isinstance(code, str) or not code.strip():
        raise _failed(
            "invalid_parameter",
            "code must be a non-empty script string.",
            "Provide non-empty IJM or Groovy code and retry.",
        )
    return language


def run_script(language: Literal["ijm", "groovy"], code: str) -> dict[str, Any]:
    """Run one IJM macro or Groovy script exactly once."""
    selected_language = _validate_script_arguments(language, code)

    def prepare(_ij: Any) -> str:
        return selected_language

    def dispatch(ij: Any, prepared_language: str) -> dict[str, Any]:
        captured_stdout = ""
        if prepared_language == "ijm":
            result, captured_stdout = _run_ijm_macro(ij, code)
        else:
            result = _run_groovy_script(ij, code)
        return {
            "language": prepared_language,
            "result": to_jsonable(result),
            "log_tail": _combined_log_tail(_log_tail(ij), captured_stdout),
            "active_image": _active_image_after_execution(ij),
        }

    return run_mutation("run_script", prepare, dispatch)


def _validate_screenshot_target(target: str) -> Literal["active_image", "results"]:
    if not isinstance(target, str) or target not in {"active_image", "results"}:
        raise _failed(
            "invalid_target",
            "target must be active_image or results.",
            "Use target='active_image' or target='results' and retry.",
        )
    return "active_image" if target == "active_image" else "results"


def _resolve_render_output_path(save_path: str | None) -> Path | None:
    if save_path is None:
        return None
    output_path = _resolve_path(save_path)
    try:
        if output_path.is_dir():
            raise _failed(
                "invalid_path",
                f"Output path is a directory: {output_path}",
                "Choose an output filename instead and retry.",
            )
        output_path.parent.mkdir(parents=True, exist_ok=True)
    except FijiError:
        raise
    except OSError as error:
        raise _failed(
            "invalid_path",
            f"Could not create output directory: {output_path.parent}",
            "Choose a writable output path and retry.",
        ) from error
    return output_path


def _save_rendered_png(
    rendered: RenderedPNG, output_path: Path | None
) -> dict[str, Any]:
    metadata = dict(rendered.metadata)
    if output_path is None:
        return metadata
    try:
        output_path.write_bytes(rendered.png)
        if output_path.read_bytes() != rendered.png:
            raise OSError("saved PNG bytes differ from rendered bytes")
    except OSError as error:
        raise _failed(
            "save_failed",
            f"Could not save rendered PNG: {output_path}",
            "Choose a writable output path and retry.",
        ) from error
    metadata["save_path"] = str(output_path)
    return metadata


def _rendered_tool_result(
    rendered: RenderedPNG, output_path: Path | None
) -> ToolResult:
    """Return exactly one native MCP PNG content block and structured metadata."""
    metadata = _save_rendered_png(rendered, output_path)
    return ToolResult(
        content=[MCPImage(data=rendered.png, format="png").to_image_content()],
        structured_content=metadata,
    )


def screenshot(
    target: Literal["active_image", "results"], save_path: str | None = None
) -> ToolResult:
    """Render the active current plane or the first 100 live Results rows as PNG."""
    selected_target = _validate_screenshot_target(target)
    output_path = _resolve_render_output_path(save_path)

    def capture(ij: Any) -> RenderedPNG:
        if selected_target == "active_image":
            return render_active_image(ij)
        results = _read_results(ij, offset=0, limit=100)
        return render_results(
            results["columns"], results["rows"], results["total_rows"]
        )

    return _rendered_tool_result(run_read("screenshot", capture), output_path)


def compare_screenshots(
    before_path: str, after_path: str, save_path: str | None = None
) -> ToolResult:
    """Compare two local rendered images without acquiring or initializing Fiji."""
    output_path = _resolve_render_output_path(save_path)
    return _rendered_tool_result(compare_paths(before_path, after_path), output_path)
