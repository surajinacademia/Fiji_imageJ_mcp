"""Focused command discovery, invocation, and script-boundary tests."""

from __future__ import annotations

import pytest
import scyjava as sj

from fiji_mcp import bridge
from fiji_mcp import tools as minimal
from fiji_mcp.bridge import FijiError, Outcome

COMMANDS = [
    {
        "name": "Blur",
        "class_name": "pkg.Blur",
        "menu_path": "Process > Filters",
        "family": "scijava",
        "invocation_route": "structured_parameters",
        "inputs": [
            {
                "name": "sigma",
                "type": "java.lang.Double",
                "required": True,
                "description": "Gaussian radius",
            }
        ],
    },
    {
        "name": "Legacy",
        "class_name": "ij.plugin.Legacy",
        "menu_path": "Plugins",
        "family": "imagej1",
        "invocation_route": "legacy_options",
        "inputs": [],
    },
]


class FakeJavaClass:
    def __init__(self, name: str) -> None:
        self._name = name

    def getName(self) -> str:
        return self._name


class FakeJavaInteger:
    def __init__(self, value: int) -> None:
        self._value = value

    def getClass(self) -> FakeJavaClass:
        return FakeJavaClass("java.lang.Integer")

    def intValue(self) -> int:
        return self._value


class FakeInput:
    def __init__(
        self,
        name: str,
        type_name: str,
        required: bool,
        description: str,
        *,
        auto_fill: bool = False,
    ) -> None:
        self._name = name
        self._type = FakeJavaClass(type_name)
        self._required = required
        self._description = description
        self._auto_fill = auto_fill

    def getDescription(self) -> str:
        return self._description

    def getName(self) -> str:
        return self._name

    def getType(self) -> FakeJavaClass:
        return self._type

    def isRequired(self) -> bool:
        return self._required

    def isAutoFill(self) -> bool:
        return self._auto_fill


class FakeMenuPath:
    def __init__(self, menu_string: str) -> None:
        self._menu_string = menu_string

    def getMenuString(self) -> str:
        return self._menu_string

    def __str__(self) -> str:
        raise AssertionError("getMenuString() must be used for menu paths")


class FakeCommandInfo:
    def __init__(
        self,
        title: str,
        class_name: str,
        menu_path: object,
        inputs: list[FakeInput],
    ) -> None:
        self._title = title
        self._class_name = class_name
        self._menu_path = menu_path
        self._inputs = inputs

    def getDelegateClassName(self) -> str:
        return self._class_name

    def getMenuPath(self) -> object:
        return self._menu_path

    def getTitle(self) -> str:
        return self._title

    def inputs(self) -> list[FakeInput]:
        return self._inputs


class FakeCommandInfoWithoutMenuPath(FakeCommandInfo):
    getMenuPath = None


class FakeFuture:
    def __init__(self, module: FakeCommandModule) -> None:
        self._module = module
        self.get_calls = 0

    def get(self) -> FakeCommandModule:
        self.get_calls += 1
        return self._module


class FakeCommandModule:
    def __init__(self, outputs: dict[str, object]) -> None:
        self._outputs = outputs

    def getOutputs(self) -> dict[str, object]:
        return self._outputs


class FakeCommandService:
    def __init__(
        self,
        commands: list[FakeCommandInfo],
        *,
        outputs: dict[str, object] | None = None,
    ) -> None:
        self._commands = commands
        self._future = FakeFuture(FakeCommandModule(outputs or {}))
        self.get_commands_calls = 0
        self.run_calls: list[tuple[object, bool, object]] = []

    def getCommands(self) -> list[FakeCommandInfo]:
        self.get_commands_calls += 1
        return self._commands

    def run(self, info: object, process: bool, parameters: object) -> FakeFuture:
        self.run_calls.append((info, process, parameters))
        return self._future


class FakeEntry:
    def __init__(self, key: str, value: object) -> None:
        self._key = key
        self._value = value

    def getKey(self) -> str:
        return self._key

    def getValue(self) -> object:
        return self._value


class FakeMenuMap:
    def __init__(self, entries: list[FakeEntry]) -> None:
        self._entries = entries

    def entrySet(self) -> list[FakeEntry]:
        return self._entries


class FakeMenus:
    def __init__(self, entries: list[FakeEntry]) -> None:
        self._commands = FakeMenuMap(entries)

    def getCommands(self) -> FakeMenuMap:
        return self._commands


class FakeContext:
    def __init__(self, service: FakeCommandService) -> None:
        self._service = service
        self.requested_service_types: list[object] = []

    def service(self, service_type: object) -> FakeCommandService:
        self.requested_service_types.append(service_type)
        return self._service


class FakeImage:
    def getBitDepth(self) -> int:
        return 16

    def getHeight(self) -> int:
        return 24

    def getNChannels(self) -> int:
        return 2

    def getNFrames(self) -> int:
        return 4

    def getNSlices(self) -> int:
        return 3

    def getTitle(self) -> str:
        return "after-command"

    def getWidth(self) -> int:
        return 32


class FakeWindowManager:
    def __init__(self, image: FakeImage | None) -> None:
        self._image = image

    def getCurrentImage(self) -> FakeImage | None:
        return self._image


class FakeLegacyIJ:
    def __init__(self, log: str) -> None:
        self._log = log
        self.run_calls: list[tuple[str, str]] = []
        self.run_macro_calls: list[str] = []

    def getLog(self) -> str:
        return self._log

    def run(self, name: str, options: str) -> None:
        self.run_calls.append((name, options))

    def runMacro(self, code: str) -> FakeJavaInteger:
        self.run_macro_calls.append(code)
        return FakeJavaInteger(11)


class FakeJavaMap:
    pass


class FakePy:
    def __init__(self, java_map: FakeJavaMap) -> None:
        self._java_map = java_map
        self.to_java_calls: list[dict[str, object]] = []
        self.run_macro_calls: list[str] = []
        self.run_script_calls: list[tuple[str, str]] = []

    def run_macro(self, code: str) -> FakeJavaInteger:
        self.run_macro_calls.append(code)
        return FakeJavaInteger(11)

    def run_script(self, language: str, code: str) -> FakeJavaInteger:
        self.run_script_calls.append((language, code))
        return FakeJavaInteger(12)

    def to_java(self, value: dict[str, object]) -> FakeJavaMap:
        self.to_java_calls.append(value)
        return self._java_map


class FakeStringReader:
    def __init__(self, text: str) -> None:
        self.text = text


class FakeStringWriter:
    def __init__(self) -> None:
        self.text = ""

    def write(self, text: str) -> None:
        self.text += text

    def toString(self) -> str:
        return self.text


class FakeGroovyModule:
    def __init__(self, calls: list[str], outputs: dict[str, object]) -> None:
        self.calls = calls
        self.outputs = outputs
        self.error_writer: FakeStringWriter | None = None

    def setContext(self, context: object) -> None:
        assert context == "context"
        self.calls.append("context")

    def initialize(self) -> None:
        self.calls.append("initialize")

    def setErrorWriter(self, writer: FakeStringWriter) -> None:
        self.error_writer = writer
        self.calls.append("writer")

    def run(self) -> None:
        self.calls.append("run")

    def getOutputs(self) -> dict[str, object]:
        self.calls.append("outputs")
        return self.outputs


class FakeIJ:
    def __init__(
        self,
        service: FakeCommandService,
        *,
        log: str = "",
        active_image: FakeImage | None = None,
    ) -> None:
        self._context = FakeContext(service)
        self.IJ = FakeLegacyIJ(log)
        self.py = FakePy(FakeJavaMap())
        self.WindowManager = FakeWindowManager(active_image)

    def context(self) -> FakeContext:
        return self._context


def _direct_mutation(fake_ij: FakeIJ):
    return lambda _name, prepare, dispatch: dispatch(fake_ij, prepare(fake_ij))


def _fake_scijava_info() -> FakeCommandInfo:
    return FakeCommandInfo(
        "Blur",
        "pkg.Blur",
        "Process > Filters",
        [FakeInput("sigma", "java.lang.Double", True, "Gaussian radius")],
    )


def _fake_jimport(menus: FakeMenus):
    def jimport(name: str) -> object:
        if name == "org.scijava.command.CommandService":
            return object()
        assert name == "ij.Menus"
        return menus

    return jimport


def _collect_catalog(
    monkeypatch,
    scijava_commands: list[FakeCommandInfo],
    legacy_entries: list[FakeEntry],
) -> list[dict[str, object]]:
    service = FakeCommandService(scijava_commands)
    monkeypatch.setattr(sj, "jimport", _fake_jimport(FakeMenus(legacy_entries)))
    return minimal._collect_commands(FakeIJ(service))


def test_search_allows_empty_query_and_caps_limit(monkeypatch):
    monkeypatch.setattr(minimal, "_collect_commands", lambda _ij: COMMANDS)
    monkeypatch.setattr(minimal, "run_read", lambda _name, fn: fn(object()))
    assert len(minimal.search_commands("", limit=2)["commands"]) == 2
    with pytest.raises(FijiError, match="between 1 and 100"):
        minimal.search_commands("", limit=101)


def test_search_consumes_the_collector_catalog_without_rededuplicating(monkeypatch):
    monkeypatch.setattr(minimal, "_collect_commands", lambda _ij: COMMANDS)
    monkeypatch.setattr(
        minimal,
        "_deduplicate_commands",
        lambda _commands: pytest.fail("collector output was deduplicated twice"),
    )
    monkeypatch.setattr(minimal, "run_read", lambda _name, fn: fn(object()))

    assert minimal.search_commands("Blur")["returned"] == 1


def test_search_query_is_required_even_when_empty_is_valid():
    with pytest.raises(TypeError):
        minimal.search_commands()  # type: ignore[call-arg]


def test_discovery_reports_the_invocation_route(monkeypatch):
    monkeypatch.setattr(minimal, "_collect_commands", lambda _ij: COMMANDS)
    monkeypatch.setattr(minimal, "run_read", lambda _name, fn: fn(object()))
    commands = minimal.search_commands("Blur")["commands"]
    assert commands[0]["invocation_route"] == "structured_parameters"


def test_collect_commands_merges_sorted_catalog_and_input_metadata(monkeypatch):
    scijava = _fake_scijava_info()
    service = FakeCommandService(
        [
            FakeCommandInfo("Zeta", "pkg.Zeta", "Plugins", []),
            scijava,
        ]
    )
    menus = FakeMenus(
        [
            FakeEntry("Blur", "pkg.Blur"),
            FakeEntry("Alpha", "ij.plugin.Alpha"),
            FakeEntry("No class", None),
            FakeEntry("No class", None),
        ]
    )
    fake_ij = FakeIJ(service)
    monkeypatch.setattr(sj, "jimport", _fake_jimport(menus))

    commands = minimal._collect_commands(fake_ij)

    assert [command["name"] for command in commands] == [
        "Alpha",
        "Blur",
        "No class",
        "No class",
        "Zeta",
    ]
    blur = next(command for command in commands if command["name"] == "Blur")
    assert blur["family"] == "scijava"
    assert blur["invocation_route"] == "structured_parameters"
    assert blur["inputs"] == [
        {
            "name": "sigma",
            "type": "java.lang.Double",
            "required": True,
            "description": "Gaussian radius",
        }
    ]
    assert all(
        command["invocation_route"] == "legacy_options"
        for command in commands
        if command["family"] == "imagej1"
    )


def test_collect_legacy_descriptors_preserves_same_class_actions(monkeypatch):
    descriptors = {
        "Smooth": 'ij.plugin.filter.Filters("smooth")',
        "Sharpen": 'ij.plugin.filter.Filters("sharpen")',
        "Find Edges": 'ij.plugin.filter.Filters("edge")',
        "Plain Filters": "  ij.plugin.filter.Filters  ",
    }
    commands = _collect_catalog(
        monkeypatch,
        [],
        [FakeEntry(name, descriptor) for name, descriptor in descriptors.items()],
    )
    legacy = {command["name"]: command for command in commands}

    assert set(legacy) == set(descriptors)
    assert {command["class_name"] for command in legacy.values()} == {
        "ij.plugin.filter.Filters"
    }
    assert {
        name: command["_legacy_descriptor"] for name, command in legacy.items()
    } == descriptors
    public = minimal._public_command(legacy["Smooth"])
    assert public["class_name"] == "ij.plugin.filter.Filters"
    assert not any(key.startswith("_") for key in public)


def test_collect_scijava_menu_path_uses_menu_string(monkeypatch):
    commands = _collect_catalog(
        monkeypatch,
        [
            FakeCommandInfo(
                "Blur",
                "pkg.Blur",
                FakeMenuPath("Process > Filters"),
                [],
            )
        ],
        [],
    )

    assert commands[0]["menu_path"] == "Process > Filters"


def test_collect_scijava_menu_path_handles_null_or_absent_metadata(monkeypatch):
    commands = _collect_catalog(
        monkeypatch,
        [
            FakeCommandInfo("No path", "pkg.NullPath", None, []),
            FakeCommandInfoWithoutMenuPath("Missing path", "pkg.NoPath", "", []),
        ],
        [],
    )

    assert {command["menu_path"] for command in commands} == {""}


@pytest.mark.parametrize(
    ("input_item", "route"),
    [
        (
            FakeInput("sigma", "java.lang.Double", True, "Gaussian radius"),
            "structured_parameters",
        ),
        (
            FakeInput("image", "net.imagej.Dataset", True, "Image input"),
            "script_fallback",
        ),
        (
            FakeInput(
                "image",
                "net.imagej.Dataset",
                True,
                "Image input",
                auto_fill=True,
            ),
            "structured_parameters",
        ),
        (
            FakeInput("image", "net.imagej.Dataset", False, "Optional image"),
            "structured_parameters",
        ),
    ],
    ids=[
        "required_primitive",
        "required_complex",
        "autofilled_complex",
        "optional_complex",
    ],
)
def test_scijava_route_is_derived_from_input_metadata(monkeypatch, input_item, route):
    commands = _collect_catalog(
        monkeypatch,
        [FakeCommandInfo("Command", "pkg.Command", "Plugins", [input_item])],
        [],
    )

    assert commands[0]["invocation_route"] == route
    assert commands[0]["inputs"] == [
        {
            "name": input_item.getName(),
            "type": input_item.getType().getName(),
            "required": input_item.isRequired(),
            "description": input_item.getDescription(),
        }
    ]


def test_scijava_record_wins_duplicate_delegate():
    merged = minimal._deduplicate_commands(
        [
            {
                "name": "Blur",
                "class_name": "pkg.Blur",
                "family": "imagej1",
                "inputs": [],
                "_legacy_descriptor": "pkg.Blur",
            },
            {
                "name": "Blur",
                "class_name": "pkg.Blur",
                "family": "scijava",
                "inputs": [{"name": "sigma"}],
            },
        ]
    )
    assert merged == [
        {
            "name": "Blur",
            "class_name": "pkg.Blur",
            "family": "scijava",
            "inputs": [{"name": "sigma"}],
        }
    ]


def test_deduplication_keeps_distinct_argument_bearing_legacy_actions():
    merged = minimal._deduplicate_commands(
        [
            {
                "name": "Smooth",
                "class_name": "ij.plugin.filter.Filters",
                "family": "imagej1",
                "_legacy_descriptor": 'ij.plugin.filter.Filters("smooth")',
            },
            {
                "name": "Sharpen",
                "class_name": "ij.plugin.filter.Filters",
                "family": "imagej1",
                "_legacy_descriptor": 'ij.plugin.filter.Filters("sharpen")',
            },
            {
                "name": "Find Edges",
                "class_name": "ij.plugin.filter.Filters",
                "family": "imagej1",
                "_legacy_descriptor": 'ij.plugin.filter.Filters("edge")',
            },
        ]
    )

    assert [command["name"] for command in merged] == [
        "Find Edges",
        "Sharpen",
        "Smooth",
    ]


def test_resolution_prefers_class_then_exact_display_name():
    assert minimal._resolve_command(COMMANDS, "pkg.Blur")["class_name"] == "pkg.Blur"
    assert minimal._resolve_command(COMMANDS, "Blur")["name"] == "Blur"


def test_ambiguous_case_insensitive_name_lists_classes():
    with pytest.raises(FijiError, match="pkg.One.*pkg.Two") as raised:
        minimal._resolve_command(
            [
                {"name": "Measure", "class_name": "pkg.One", "family": "scijava"},
                {"name": "MEASURE", "class_name": "pkg.Two", "family": "scijava"},
            ],
            "measure",
        )
    assert raised.value.code == "ambiguous_command"
    assert raised.value.retryable is False
    assert raised.value.outcome is Outcome.FAILED
    assert "class" in raised.value.recovery


def test_ambiguous_same_class_actions_list_each_name_class_pair():
    with pytest.raises(FijiError) as raised:
        minimal._resolve_command(
            [
                {
                    "name": "Smooth",
                    "class_name": "ij.plugin.filter.Filters",
                    "family": "imagej1",
                    "_legacy_descriptor": 'ij.plugin.filter.Filters("smooth")',
                },
                {
                    "name": "SMOOTH",
                    "class_name": "ij.plugin.filter.Filters",
                    "family": "imagej1",
                    "_legacy_descriptor": 'ij.plugin.filter.Filters("sharpen")',
                },
            ],
            "smooth",
        )

    message = str(raised.value)
    assert "Smooth (ij.plugin.filter.Filters)" in message
    assert "SMOOTH (ij.plugin.filter.Filters)" in message
    assert raised.value.recovery == (
        "Use an exact case-sensitive display name from search_commands and retry."
    )
    assert "delegate class" not in raised.value.recovery


def test_ambiguous_same_class_identical_names_require_script_fallback():
    candidates = minimal._deduplicate_commands(
        [
            {
                "name": "Smooth",
                "class_name": "ij.plugin.filter.Filters",
                "family": "scijava",
            },
            {
                "name": "Smooth",
                "class_name": "ij.plugin.filter.Filters",
                "family": "imagej1",
                "_legacy_descriptor": 'ij.plugin.filter.Filters("smooth")',
            },
        ]
    )

    with pytest.raises(FijiError) as raised:
        minimal._resolve_command(candidates, "Smooth")

    assert (
        raised.value.recovery == "Use run_script with IJM or Groovy for this command."
    )
    assert "display name" not in raised.value.recovery
    assert "delegate class" not in raised.value.recovery


def test_ambiguous_same_class_recovery_requires_globally_unique_display_names():
    commands = [
        {"name": "Foo", "class_name": "pkg.Shared", "family": "scijava"},
        {"name": "Bar", "class_name": "pkg.Shared", "family": "scijava"},
        {"name": "Foo", "class_name": "pkg.Other", "family": "scijava"},
    ]

    with pytest.raises(FijiError) as raised:
        minimal._resolve_command(commands, "pkg.Shared")

    assert (
        raised.value.recovery == "Use run_script with IJM or Groovy for this command."
    )
    assert "display name" not in raised.value.recovery
    assert "delegate class" not in raised.value.recovery


def test_ambiguous_same_class_recovery_respects_class_precedence():
    commands = [
        {"name": "pkg.Other", "class_name": "pkg.Shared", "family": "scijava"},
        {"name": "Bar", "class_name": "pkg.Shared", "family": "scijava"},
        {
            "name": "Unrelated mutation",
            "class_name": "pkg.Other",
            "family": "scijava",
        },
    ]

    assert (
        minimal._resolve_command(commands, "pkg.Other")["name"] == "Unrelated mutation"
    )
    with pytest.raises(FijiError) as raised:
        minimal._resolve_command(commands, "pkg.Shared")

    assert (
        raised.value.recovery == "Use run_script with IJM or Groovy for this command."
    )
    assert "display name" not in raised.value.recovery
    assert "delegate class" not in raised.value.recovery


def test_missing_command_is_deterministic():
    with pytest.raises(FijiError) as raised:
        minimal._resolve_command(COMMANDS, "does not exist")
    assert raised.value.code == "command_not_found"
    assert raised.value.retryable is False
    assert raised.value.outcome is Outcome.FAILED
    assert "search_commands" in raised.value.recovery


def test_run_command_rejects_parameters_and_options_together():
    with pytest.raises(FijiError, match="mutually exclusive") as raised:
        minimal.run_command("Blur", {"sigma": 2}, "sigma=2")
    assert raised.value.code == "invalid_parameter"
    assert raised.value.retryable is False
    assert raised.value.outcome is Outcome.FAILED


def test_run_command_consumes_the_collector_catalog_without_rededuplicating(
    monkeypatch,
):
    catalog = [
        {
            "name": "Invert",
            "class_name": "ij.plugin.filter.Filters",
            "menu_path": "Edit > Invert",
            "family": "imagej1",
            "inputs": [],
            "invocation_route": "legacy_options",
            "_legacy_descriptor": 'ij.plugin.filter.Filters("invert")',
        }
    ]
    monkeypatch.setattr(minimal, "_collect_commands", lambda _ij: catalog)
    monkeypatch.setattr(
        minimal,
        "_deduplicate_commands",
        lambda _commands: pytest.fail("collector output was deduplicated twice"),
    )
    monkeypatch.setattr(
        minimal,
        "run_mutation",
        lambda _name, prepare, _dispatch: prepare(object()),
    )

    prepared = minimal.run_command("Invert")
    assert prepared[0] is catalog[0]


def test_run_command_rejects_input_for_the_wrong_route():
    with pytest.raises(FijiError, match="legacy options string.*run_script"):
        minimal._validate_route_inputs(
            {"name": "Legacy", "family": "imagej1"},
            parameters={"sigma": 2},
            options=None,
        )
    with pytest.raises(FijiError, match="structured parameters.*run_script"):
        minimal._validate_route_inputs(
            {"name": "Modern", "family": "scijava"},
            parameters=None,
            options="sigma=2",
        )
    with pytest.raises(FijiError, match="script fallback.*run_script"):
        minimal._validate_route_inputs(
            {
                "name": "Complex",
                "family": "scijava",
                "invocation_route": "script_fallback",
            },
            parameters=None,
            options=None,
        )


def test_run_command_rejects_non_mapping_parameters_before_java(monkeypatch):
    monkeypatch.setattr(
        minimal,
        "run_mutation",
        lambda *_args: (_ for _ in ()).throw(AssertionError("called")),
    )
    with pytest.raises(FijiError) as raised:
        minimal.run_command("Blur", ["sigma=2"])  # type: ignore[arg-type]
    assert raised.value.code == "invalid_parameter"
    assert raised.value.retryable is False
    assert raised.value.outcome is Outcome.FAILED


def test_run_command_classifies_parameter_conversion_before_command_dispatch(
    monkeypatch,
):
    info = _fake_scijava_info()
    service = FakeCommandService([info])
    fake_ij = FakeIJ(service)
    conversion_calls: list[dict[str, object]] = []

    def fail_to_java(parameters: dict[str, object]) -> FakeJavaMap:
        conversion_calls.append(parameters)
        raise RuntimeError("cannot convert structured parameters")

    monkeypatch.setattr(
        sj,
        "jimport",
        _fake_jimport(FakeMenus([FakeEntry("Blur", "pkg.Blur")])),
    )
    monkeypatch.setattr(fake_ij.py, "to_java", fail_to_java)
    bridge._reset_runtime_for_tests(ready_ij=fake_ij)
    monkeypatch.setattr(bridge, "_jvm_is_healthy", lambda _ij: True)
    try:
        with pytest.raises(FijiError) as raised:
            minimal.run_command("pkg.Blur", parameters={"sigma": 2})
    finally:
        bridge._reset_runtime_for_tests()

    assert raised.value.outcome is Outcome.FAILED
    assert conversion_calls == [{"sigma": 2}]
    assert service.run_calls == []


def test_run_command_dispatches_scijava_once_with_one_java_map(monkeypatch):
    info = _fake_scijava_info()
    service = FakeCommandService([info], outputs={"answer": FakeJavaInteger(7)})
    fake_ij = FakeIJ(
        service,
        log="discard" + "x" * 4_000,
        active_image=FakeImage(),
    )
    monkeypatch.setattr(
        sj,
        "jimport",
        _fake_jimport(FakeMenus([FakeEntry("Blur", "pkg.Blur")])),
    )
    monkeypatch.setattr(minimal, "run_mutation", _direct_mutation(fake_ij))

    result = minimal.run_command("pkg.Blur", parameters={"sigma": 2})

    assert service.run_calls == [(info, True, fake_ij.py._java_map)]
    assert service._future.get_calls == 1
    assert fake_ij.py.to_java_calls == [{"sigma": 2}]
    assert fake_ij.IJ.run_calls == []
    assert result["outputs"] == {"answer": 7}
    assert result["log_tail"] == "x" * 4_000
    assert result["active_image"] == {
        "title": "after-command",
        "width": 32,
        "height": 24,
        "channels": 2,
        "slices": 3,
        "frames": 4,
        "bit_depth": 16,
    }


def test_run_command_dispatches_legacy_once_with_options(monkeypatch):
    service = FakeCommandService([])
    fake_ij = FakeIJ(service)
    monkeypatch.setattr(
        sj,
        "jimport",
        _fake_jimport(FakeMenus([FakeEntry("Legacy", "ij.plugin.Legacy")])),
    )
    monkeypatch.setattr(minimal, "run_mutation", _direct_mutation(fake_ij))

    result = minimal.run_command("Legacy", options="sigma=2")

    assert fake_ij.IJ.run_calls == [("Legacy", "sigma=2")]
    assert service.run_calls == []
    assert result["outputs"] is None


def test_run_groovy_script_runs_synchronously_and_preserves_outputs(monkeypatch):
    calls: list[str] = []
    module = FakeGroovyModule(calls, {"answer": FakeJavaInteger(42)})

    class FakeScriptInfo:
        def __init__(self, context, name, reader) -> None:
            assert context == "context"
            assert name == "fiji-mcp.groovy"
            assert reader.text == "#@output Integer answer\nanswer = 42"

        def inputs(self) -> list[object]:
            calls.append("inputs")
            return []

        def parseParameters(self) -> None:
            calls.append("parse")

        def createModule(self) -> FakeGroovyModule:
            calls.append("create")
            return module

    mapping = {
        "java.io.StringReader": FakeStringReader,
        "java.io.StringWriter": FakeStringWriter,
        "org.scijava.script.ScriptInfo": FakeScriptInfo,
    }
    monkeypatch.setattr(sj, "jimport", mapping.__getitem__)
    fake_ij = type("GroovyGateway", (), {"context": lambda self: "context"})()

    outputs = minimal._run_groovy_script(
        fake_ij, "#@output Integer answer\nanswer = 42"
    )

    assert outputs == {"answer": module.outputs["answer"]}
    assert calls == [
        "inputs",
        "parse",
        "create",
        "context",
        "initialize",
        "writer",
        "run",
        "outputs",
    ]


def test_run_groovy_script_reports_captured_failure_as_unknown(monkeypatch):
    calls: list[str] = []
    module = FakeGroovyModule(calls, {})
    original_run = module.run

    def fail_run() -> None:
        original_run()
        assert module.error_writer is not None
        module.error_writer.write("x" * 5_000)

    module.run = fail_run  # type: ignore[method-assign]

    class FakeScriptInfo:
        def __init__(self, _context, _name, _reader) -> None:
            pass

        def inputs(self) -> list[object]:
            calls.append("inputs")
            return []

        def parseParameters(self) -> None:
            calls.append("parse")

        def createModule(self) -> FakeGroovyModule:
            calls.append("create")
            return module

    mapping = {
        "java.io.StringReader": FakeStringReader,
        "java.io.StringWriter": FakeStringWriter,
        "org.scijava.script.ScriptInfo": FakeScriptInfo,
    }
    monkeypatch.setattr(sj, "jimport", mapping.__getitem__)
    fake_ij = type("GroovyGateway", (), {"context": lambda self: "context"})()

    with pytest.raises(FijiError) as raised:
        minimal._run_groovy_script(fake_ij, "throw new RuntimeException('x')")

    assert raised.value.code == "script_failed"
    assert raised.value.retryable is False
    assert raised.value.outcome is Outcome.UNKNOWN
    assert len(raised.value.message) <= 4_040


def test_run_groovy_script_maps_raised_module_error_to_captured_failure(monkeypatch):
    calls: list[str] = []
    module = FakeGroovyModule(calls, {})
    original_run = module.run

    def fail_run() -> None:
        original_run()
        assert module.error_writer is not None
        module.error_writer.write("captured-error\n" + "x" * 5_000)
        raise RuntimeError("raw module failure")

    module.run = fail_run  # type: ignore[method-assign]

    class FakeScriptInfo:
        def __init__(self, _context, _name, _reader) -> None:
            pass

        def inputs(self) -> list[object]:
            return []

        def parseParameters(self) -> None:
            pass

        def createModule(self) -> FakeGroovyModule:
            return module

    mapping = {
        "java.io.StringReader": FakeStringReader,
        "java.io.StringWriter": FakeStringWriter,
        "org.scijava.script.ScriptInfo": FakeScriptInfo,
    }
    monkeypatch.setattr(sj, "jimport", mapping.__getitem__)
    fake_ij = type("GroovyGateway", (), {"context": lambda self: "context"})()

    with pytest.raises(FijiError) as raised:
        minimal._run_groovy_script(fake_ij, "throw new RuntimeException('x')")

    assert raised.value.code == "script_failed"
    assert raised.value.retryable is False
    assert raised.value.outcome is Outcome.UNKNOWN
    assert isinstance(raised.value.__cause__, RuntimeError)
    assert "raw module failure" not in raised.value.message
    assert raised.value.message.endswith("x" * 100)
    assert len(raised.value.message) <= 4_040


def test_run_script_dispatches_only_ijm_and_groovy(monkeypatch):
    service = FakeCommandService([])
    fake_ij = FakeIJ(
        service,
        log="log",
        active_image=FakeImage(),
    )
    monkeypatch.setattr(minimal, "run_mutation", _direct_mutation(fake_ij))
    ijm_macro_calls: list[str] = []

    def run_ijm_macro(_ij, code):
        ijm_macro_calls.append(code)
        return FakeJavaInteger(11), ""

    monkeypatch.setattr(minimal, "_run_ijm_macro", run_ijm_macro, raising=False)
    groovy_script_calls: list[str] = []

    def run_groovy_script(_ij, code):
        groovy_script_calls.append(code)
        return FakeJavaInteger(12)

    monkeypatch.setattr(minimal, "_run_groovy_script", run_groovy_script, raising=False)

    ijm = minimal.run_script("ijm", "return 11;")
    groovy = minimal.run_script("groovy", "return 12")

    assert ijm_macro_calls == ["return 11;"]
    assert groovy_script_calls == ["return 12"]
    assert fake_ij.IJ.run_macro_calls == []
    assert fake_ij.py.run_macro_calls == []
    assert fake_ij.py.run_script_calls == []
    assert ijm["result"] == 11
    assert groovy["result"] == 12
    assert ijm["log_tail"] == "log"
    assert groovy["active_image"]["title"] == "after-command"


def test_ijm_stdout_capture_returns_text_and_restores_previous_stream(monkeypatch):
    original_stream = object()

    class FakeSystem:
        out = original_stream
        set_out_calls: list[object] = []

        @classmethod
        def setOut(cls, stream: object) -> None:
            cls.out = stream
            cls.set_out_calls.append(stream)

    class FakeBuffer:
        def __init__(self) -> None:
            self.text = ""

        def toString(self, encoding: str) -> str:
            assert encoding == "UTF-8"
            return self.text

    class FakePrintStream:
        def __init__(self, buffer: FakeBuffer, *_args: object) -> None:
            self.buffer = buffer
            self.flushed = False
            self.closed = False

        def close(self) -> None:
            self.closed = True

        def flush(self) -> None:
            self.flushed = True

        def write(self, text: str) -> None:
            self.buffer.text += text

    def jimport(name: str) -> object:
        mapping = {
            "java.lang.System": FakeSystem,
            "java.io.ByteArrayOutputStream": FakeBuffer,
            "java.io.PrintStream": FakePrintStream,
        }
        return mapping[name]

    class MacroRunner:
        def runMacro(self, code: str) -> FakeJavaInteger:
            assert code == 'print("ijm-output");'
            assert FakeSystem.out is not original_stream
            FakeSystem.out.write("ijm-output\n")
            return FakeJavaInteger(11)

    fake_ij = type("FakeIJMGateway", (), {"IJ": MacroRunner()})()
    monkeypatch.setattr(sj, "jimport", jimport)

    result, captured = minimal._run_ijm_macro(fake_ij, 'print("ijm-output");')

    assert result.intValue() == 11
    assert captured == "ijm-output\n"
    assert FakeSystem.out is original_stream
    assert FakeSystem.set_out_calls[-1] is original_stream


def test_ijm_stdout_capture_restores_previous_stream_after_macro_error(monkeypatch):
    original_stream = object()

    class FakeSystem:
        out = original_stream

        @classmethod
        def setOut(cls, stream: object) -> None:
            cls.out = stream

    class FakeBuffer:
        def toString(self, _encoding: str) -> str:
            return ""

    class FakePrintStream:
        def __init__(self, *_args: object) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

        def flush(self) -> None:
            pass

    def jimport(name: str) -> object:
        mapping = {
            "java.lang.System": FakeSystem,
            "java.io.ByteArrayOutputStream": FakeBuffer,
            "java.io.PrintStream": FakePrintStream,
        }
        return mapping[name]

    class MacroRunner:
        def runMacro(self, _code: str) -> None:
            assert FakeSystem.out is not original_stream
            raise RuntimeError("macro failed")

    fake_ij = type("FakeIJMGateway", (), {"IJ": MacroRunner()})()
    monkeypatch.setattr(sj, "jimport", jimport)

    with pytest.raises(RuntimeError, match="macro failed"):
        minimal._run_ijm_macro(fake_ij, 'print("ijm-output");')

    assert FakeSystem.out is original_stream


@pytest.mark.parametrize("language", ["python", "javascript", "", []])
def test_run_script_accepts_only_ijm_and_groovy(language):
    with pytest.raises(FijiError, match="ijm or groovy") as raised:
        minimal.run_script(language, "return 1")  # type: ignore[arg-type]
    assert raised.value.code == "unsupported_language"
    assert raised.value.retryable is False
    assert raised.value.outcome is Outcome.FAILED
    assert "ijm" in raised.value.recovery


def test_run_script_requires_nonempty_code_before_java(monkeypatch):
    monkeypatch.setattr(
        minimal,
        "run_mutation",
        lambda *_args: (_ for _ in ()).throw(AssertionError("called")),
    )
    with pytest.raises(FijiError) as raised:
        minimal.run_script("ijm", "  ")
    assert raised.value.code == "invalid_parameter"
    assert raised.value.retryable is False
    assert raised.value.outcome is Outcome.FAILED


def test_gui_required_script_failure_keeps_bridge_outcome(monkeypatch):
    headless_error = type(
        "HeadlessException",
        (Exception,),
        {"__module__": "java.awt"},
    )

    def raise_headless(_ij: object, _code: str) -> tuple[object, str]:
        raise headless_error()

    fake_ij = FakeIJ(FakeCommandService([]))
    bridge._reset_runtime_for_tests(ready_ij=fake_ij)
    monkeypatch.setattr(bridge, "_jvm_is_healthy", lambda _ij: True)
    monkeypatch.setattr(minimal, "_run_ijm_macro", raise_headless)
    try:
        with pytest.raises(FijiError) as raised:
            minimal.run_script("ijm", "run('Measure');")
    finally:
        bridge._reset_runtime_for_tests()

    assert raised.value.code == "gui_required"
    assert raised.value.retryable is False
    assert raised.value.outcome is Outcome.UNKNOWN
    assert "FIJI_MODE=gui" in raised.value.recovery
