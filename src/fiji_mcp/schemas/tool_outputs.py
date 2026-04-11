"""Structured tool responses for MCP output schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class HealthCheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: Literal[True] = Field(default=True, description="Bridge responded successfully.")
    initialized: bool = Field(description="PyImageJ context is ready.")
    fiji_path: str | None = Field(description="Resolved Fiji installation path, if known.")
    mode: str = Field(description="Runtime mode, e.g. interactive or headless.")
    imagej_version: str = Field(description="ImageJ/Fiji version string from the Java side.")
    operation_timeout_seconds: float = Field(
        description="Per-operation timeout from FIJI_OPERATION_TIMEOUT_SECONDS."
    )


class MacroRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: Literal[True] = Field(default=True, description="Macro finished without raising on the Java side.")
    result: str = Field(description="String return value from ImageJ1.runMacro, often empty.")
    log_tail: str = Field(
        description="Tail of the ImageJ log window (last ~4000 chars), useful for debugging."
    )


class OpenImageResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: Literal[True] = Field(default=True, description="Image opened and shown in Fiji.")
    title: str = Field(description="Window title of the opened image.")
    width: int = Field(ge=0)
    height: int = Field(ge=0)
    path: str = Field(description="Absolute path that was opened.")


class SaveImageResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: Literal[True] = Field(default=True, description="Image written to disk.")
    path: str = Field(description="Output file path.")
    title: str = Field(description="Title of the image that was saved.")
    format: str = Field(description="Format hint passed to ImageJ saveAs (e.g. tiff, png).")


class BatchMacroStepSuccess(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step: int = Field(ge=1, description="1-based index in the batch.")
    ok: Literal[True] = Field(default=True, description="This step completed.")
    result: MacroRunResult = Field(description="Macro output for this step.")


class BatchMacroStepFailure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step: int = Field(ge=1)
    ok: Literal[False] = Field(default=False, description="This step failed.")
    error: str = Field(description="Error message or stack summary.")


class RunBatchMacrosResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool = Field(description="True only if every step succeeded.")
    total_steps: int = Field(ge=0, description="Number of macros requested.")
    completed_steps: int = Field(ge=0, description="Steps attempted before stop (may be less than total if stopped early).")
    failed_steps: int = Field(ge=0, description="Count of steps with ok=false.")
    results: list[BatchMacroStepSuccess | BatchMacroStepFailure] = Field(
        description="Per-step outcomes in order.",
    )


class CommandEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Human-readable command or plugin title.")
    class_name: str = Field(description="Java delegate class name when known.")
    menu_path: str = Field(description="Menu path from CommandService, if any.")
    source: str = Field(description="Discovery source: CommandService or Menus.")


class ListAllCommandsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: Literal[True] = Field(default=True)
    total: int = Field(ge=0, description="Total commands discovered.")
    returned: int = Field(ge=0, description="Number of commands in this response (capped by limit).")
    commands: list[CommandEntry] = Field(description="Slice of commands up to limit.")


class SearchCommandsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: Literal[True] = Field(default=True)
    query: str = Field(description="Search string used.")
    total_matches: int = Field(ge=0)
    matches: list[CommandEntry] = Field(description="Merged keyword and fuzzy matches.")


class PluginInputMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Parameter name.")
    type: str = Field(description="Java or SciJava type string.")
    required: bool = Field(description="Whether the command marks this input required.")
    description: str = Field(description="Help text when exposed by the command.")


class DescribePluginResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: Literal[True] = Field(default=True)
    command: CommandEntry = Field(description="Matched command record.")
    inputs: list[PluginInputMeta] = Field(description="Declared inputs when CommandService exposes them.")
    inputs_available: bool = Field(description="True if any input metadata was returned.")
    note: str = Field(description="Guidance when metadata is incomplete (legacy plugins).")


class ExtensionEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    url: str


class ListExtensionsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: Literal[True] = Field(default=True)
    extensions: list[ExtensionEntry]
    count: int = Field(ge=0)
    note: str = Field(description="How extension list was obtained or why it may be empty.")


class OpenImageSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    title: str
    width: int
    height: int
    type: int = Field(description="ImageJ image type constant.")


class ListOpenImagesResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: Literal[True] = Field(default=True)
    count: int = Field(ge=0)
    images: list[OpenImageSummary]


class GetImageInfoResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: Literal[True] = Field(default=True)
    title: str
    width: int
    height: int
    slices: int
    frames: int
    channels: int
    bit_depth: int
    mean: float
    std_dev: float
    min: float
    max: float


class ScreenshotResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: Literal[True] = Field(default=True)
    capture_mode: Literal["full_screen", "active_image", "results_table"] = Field(
        description=(
            "full_screen: primary-monitor Robot capture; active_image: current ImagePlus; "
            "results_table: rendered Results window data."
        ),
    )
    mime_type: str = Field(description="MIME type of the encoded image.")
    format: str = Field(description="Encoder output format label.")
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    from_cache: bool = Field(description="True if a recent identical capture was reused.")
    image_base64: str = Field(description="Base64-encoded image bytes for inline display.")


class WorkflowStepInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    macro: str = Field(
        default="",
        description="ImageJ macro text to run for this step.",
    )
    screenshot_after: bool = Field(
        default=True,
        description="When verify_each_step is true, capture screenshot after macro unless false.",
    )
    screenshot_capture: Literal["full_screen", "active_image", "results_table"] = Field(
        default="full_screen",
        description="Passed to screenshot_fiji when verifying this step (non-full_screen modes avoid desktop capture).",
    )


class WorkflowStepSuccess(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step: int = Field(ge=1)
    ok: Literal[True] = Field(default=True)
    result: MacroRunResult
    screenshot: ScreenshotResult | None = Field(
        default=None,
        description="Present when verify_each_step and screenshot_after allowed capture.",
    )


class WorkflowStepFailure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step: int = Field(ge=1)
    ok: Literal[False] = Field(default=False)
    error: str


class RunWorkflowResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool = Field(description="True if every step succeeded.")
    results: list[WorkflowStepSuccess | WorkflowStepFailure] = Field(default_factory=list)
    total_steps: int | None = Field(default=None, description="Set on full completion summary.")
    failed_steps: int | None = Field(default=None, description="Count of failed steps on full summary.")
    completed_steps: int | None = Field(
        default=None,
        description="On early abort, number of fully completed steps before the failure.",
    )
    failed_step: int | None = Field(
        default=None,
        description="On early abort, 1-based index of the first hard failure.",
    )
