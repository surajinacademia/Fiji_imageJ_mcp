"""Discovery and introspection tools for Fiji commands and image state."""

from __future__ import annotations

import difflib
from typing import Annotated, Any

import scyjava as sj
from mcp.types import ToolAnnotations
from pydantic import Field

from fiji_mcp.fiji_bridge import get_ij
from fiji_mcp.mcp_instance import mcp
from fiji_mcp.schemas.tool_outputs import (
    CommandEntry,
    DescribePluginResult,
    ExtensionEntry,
    GetImageInfoResult,
    ListAllCommandsResult,
    ListExtensionsResult,
    ListOpenImagesResult,
    OpenImageSummary,
    PluginInputMeta,
    SearchCommandsResult,
)
from fiji_mcp.utils.error_handler import FijiToolError, run_with_timeout

_ANN_READ = ToolAnnotations(readOnlyHint=True, idempotentHint=True)
_ANN_QUERY = ToolAnnotations(readOnlyHint=True, idempotentHint=True)

CommandName = Annotated[
    str,
    Field(
        description="Command or plugin title as shown in Fiji (exact or partial match).",
        examples=["Gaussian Blur...", "Measure"],
    ),
]
SearchQuery = Annotated[
    str,
    Field(
        description="Keyword to match against command titles and Java class names; fuzzy match augments results.",
        examples=["segment", "blur"],
    ),
]
ListLimit = Annotated[
    int,
    Field(ge=1, le=50_000, description="Maximum number of commands or matches to return."),
]
ImageTitle = Annotated[
    str | None,
    Field(
        description="Exact window title to inspect; omit or null to use the current front image.",
    ),
]


def _safe_call(obj: Any, method: str, default: Any = None) -> Any:
    if obj is None or not hasattr(obj, method):
        return default
    try:
        return getattr(obj, method)()
    except Exception:
        return default


def _get_command_service(ij: Any) -> Any:
    command_service_class = sj.jimport("org.scijava.command.CommandService")
    return ij.context().service(command_service_class)


def _collect_commands() -> list[dict[str, str]]:
    ij = get_ij()
    commands: list[dict[str, str]] = []
    seen: set[str] = set()

    # Primary source: ImageJ2 CommandService
    try:
        service = _get_command_service(ij)
        for command_info in list(service.getCommands()):
            title = _safe_call(command_info, "getTitle", "") or _safe_call(
                command_info, "getName", ""
            )
            class_name = _safe_call(command_info, "getDelegateClassName", "")
            menu_path = _safe_call(command_info, "getMenuPath", "")
            menu = "" if menu_path is None else str(menu_path)
            key = f"{class_name}:{title}"
            if key in seen:
                continue
            seen.add(key)
            commands.append(
                {
                    "name": str(title),
                    "class_name": str(class_name),
                    "menu_path": menu,
                    "source": "CommandService",
                }
            )
    except Exception:
        # Keep best-effort behavior by falling back to ImageJ1 menus.
        pass

    # Fallback/augment: ImageJ1 menu map
    try:
        menus = sj.jimport("ij.Menus")
        menu_commands = menus.getCommands()
        for entry in list(menu_commands.entrySet()):
            name = str(entry.getKey())
            class_name = str(entry.getValue())
            key = f"{class_name}:{name}"
            if key in seen:
                continue
            seen.add(key)
            commands.append(
                {
                    "name": name,
                    "class_name": class_name,
                    "menu_path": "",
                    "source": "Menus",
                }
            )
    except Exception:
        pass

    commands.sort(key=lambda item: item["name"].lower())
    return commands


@mcp.tool(
    annotations=_ANN_QUERY,
    description=(
        "Enumerate Fiji/ImageJ commands from SciJava CommandService and legacy ij.Menus. "
        "Large installs return thousands of entries; lower limit for faster responses."
    ),
)
def list_all_commands(limit: ListLimit = 500) -> ListAllCommandsResult:
    """List Fiji/ImageJ commands discovered from CommandService and Menus."""
    if limit < 1:
        raise FijiToolError("limit must be >= 1. Use list_all_commands(limit=100) or similar.")

    def _list() -> ListAllCommandsResult:
        commands = _collect_commands()
        slice_raw = commands[:limit]
        return ListAllCommandsResult(
            total=len(commands),
            returned=min(limit, len(commands)),
            commands=[CommandEntry.model_validate(c) for c in slice_raw],
        )

    return run_with_timeout(_list)


@mcp.tool(
    annotations=_ANN_QUERY,
    description=(
        "Search installed commands by substring on name/class, plus fuzzy title matching. "
        "Use before describe_plugin to find the exact menu label."
    ),
)
def search_commands(query: SearchQuery, limit: ListLimit = 25) -> SearchCommandsResult:
    """Search command names and class names by keyword/fuzzy similarity."""
    if not query or not query.strip():
        raise FijiToolError(
            "query is empty. Pass a substring such as 'threshold' or a plugin class fragment."
        )
    if limit < 1:
        raise FijiToolError("limit must be >= 1.")

    query_lower = query.strip().lower()

    def _search() -> SearchCommandsResult:
        commands = _collect_commands()
        keyword_matches = [
            c
            for c in commands
            if query_lower in c["name"].lower() or query_lower in c["class_name"].lower()
        ]
        fuzzy_names = difflib.get_close_matches(
            query_lower,
            [c["name"].lower() for c in commands],
            n=limit,
            cutoff=0.55,
        )
        fuzzy_matches = [c for c in commands if c["name"].lower() in fuzzy_names]

        merged: list[dict[str, str]] = []
        seen: set[str] = set()
        for command in keyword_matches + fuzzy_matches:
            key = f"{command['class_name']}:{command['name']}"
            if key in seen:
                continue
            seen.add(key)
            merged.append(command)
            if len(merged) >= limit:
                break

        return SearchCommandsResult(
            query=query,
            total_matches=len(merged),
            matches=[CommandEntry.model_validate(c) for c in merged],
        )

    return run_with_timeout(_search)


@mcp.tool(
    annotations=_ANN_READ,
    description=(
        "Resolve one command by name and return SciJava input metadata when available. "
        "Legacy ImageJ1-only plugins may omit inputs; use run_macro in that case."
    ),
)
def describe_plugin(command_name: CommandName) -> DescribePluginResult:
    """Describe a command/plugin including command metadata and inputs when available."""
    if not command_name or not command_name.strip():
        raise FijiToolError(
            "command_name is empty. Pass a title from list_all_commands or search_commands."
        )

    target = command_name.strip().lower()

    def _describe() -> DescribePluginResult:
        ij = get_ij()
        commands = _collect_commands()
        match = next((c for c in commands if c["name"].lower() == target), None)
        if match is None:
            for command in commands:
                if target in command["name"].lower():
                    match = command
                    break
        if match is None:
            raise FijiToolError(
                f"No command found matching '{command_name}'. "
                "Run search_commands with a shorter substring, then describe_plugin on an exact title."
            )

        inputs: list[PluginInputMeta] = []
        try:
            service = _get_command_service(ij)
            info = service.getCommand(match["class_name"])
            if info is not None:
                for item in list(info.inputs()):
                    inputs.append(
                        PluginInputMeta(
                            name=str(_safe_call(item, "getName", "")),
                            type=str(_safe_call(item, "getType", "")),
                            required=bool(_safe_call(item, "isRequired", False)),
                            description=str(_safe_call(item, "getDescription", "")),
                        )
                    )
        except Exception:
            # Best effort: legacy plugins may not expose parameter metadata.
            pass

        return DescribePluginResult(
            command=CommandEntry.model_validate(match),
            inputs=inputs,
            inputs_available=len(inputs) > 0,
            note=(
                "Legacy plugins may not expose complete parameter metadata; "
                "macro syntax may still be required."
            ),
        )

    return run_with_timeout(_describe)


@mcp.tool(
    annotations=_ANN_READ,
    description=(
        "List configured ImageJ update sites (name and URL) when the updater classes are present. "
        "May return an empty list on minimal installs; see note field."
    ),
)
def list_extensions() -> ListExtensionsResult:
    """Best-effort list of update sites/extensions available in this Fiji install."""

    def _list() -> ListExtensionsResult:
        _ = get_ij()
        update_sites: list[ExtensionEntry] = []
        note = "Update site introspection unavailable in this runtime."
        try:
            imagej_updater = sj.jimport("net.imagej.updater.FilesCollection")
            updater = imagej_updater()
            for site in list(updater.getUpdateSites().values()):
                update_sites.append(
                    ExtensionEntry(
                        name=str(site.getName()),
                        url=str(site.getURL()),
                    )
                )
            note = "Loaded from net.imagej.updater.FilesCollection."
        except Exception:
            pass

        return ListExtensionsResult(extensions=update_sites, count=len(update_sites), note=note)

    return run_with_timeout(_list)


@mcp.tool(
    annotations=_ANN_READ,
    description="List open image windows with id, title, dimensions, and ImageJ type constant."
)
def list_open_images() -> ListOpenImagesResult:
    """List currently open ImageJ windows/images."""

    def _list() -> ListOpenImagesResult:
        _ = get_ij()
        window_manager = sj.jimport("ij.WindowManager")
        id_list = window_manager.getIDList()
        if id_list is None:
            return ListOpenImagesResult(count=0, images=[])
        images: list[OpenImageSummary] = []
        for image_id in list(id_list):
            image = window_manager.getImage(image_id)
            if image is None:
                continue
            images.append(
                OpenImageSummary(
                    id=int(image_id),
                    title=str(image.getTitle()),
                    width=int(image.getWidth()),
                    height=int(image.getHeight()),
                    type=int(image.getType()),
                )
            )
        return ListOpenImagesResult(count=len(images), images=images)

    return run_with_timeout(_list)


@mcp.tool(
    annotations=_ANN_READ,
    description=(
        "Read dimensions, channel/frame/slice counts, bit depth, and ROI statistics for one image. "
        "Uses the front image when image_title is omitted."
    ),
)
def get_image_info(image_title: ImageTitle = None) -> GetImageInfoResult:
    """Return metadata/statistics for active image or a named image."""

    def _info() -> GetImageInfoResult:
        _ = get_ij()
        window_manager = sj.jimport("ij.WindowManager")
        if image_title:
            image = window_manager.getImage(image_title)
        else:
            image = window_manager.getCurrentImage()
        if image is None:
            raise FijiToolError(
                "No active image found. Open an image (open_image) or pass image_title matching a window title."
            )

        stats = image.getStatistics()
        return GetImageInfoResult(
            title=str(image.getTitle()),
            width=int(image.getWidth()),
            height=int(image.getHeight()),
            slices=int(image.getNSlices()),
            frames=int(image.getNFrames()),
            channels=int(image.getNChannels()),
            bit_depth=int(image.getBitDepth()),
            mean=float(stats.mean),
            std_dev=float(stats.stdDev),
            min=float(stats.min),
            max=float(stats.max),
        )

    return run_with_timeout(_info)
