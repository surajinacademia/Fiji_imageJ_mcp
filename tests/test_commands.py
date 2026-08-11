"""Focused command discovery, invocation, and script-boundary tests."""

from __future__ import annotations

import pytest
import scyjava as sj

from fiji_mcp import _minimal_tools as minimal
from fiji_mcp import bridge
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
    ) -> None:
        self._name = name
        self._type = FakeJavaClass(type_name)
        self._required = required
        self._description = description

    def getDescription(self) -> str:
        return self._description

    def getName(self) -> str:
        return self._name

    def getType(self) -> FakeJavaClass:
        return self._type

    def isRequired(self) -> bool:
        return self._required


class FakeCommandInfo:
    def __init__(
        self,
        title: str,
        class_name: str,
        menu_path: str,
        inputs: list[FakeInput],
    ) -> None:
        self._title = title
        self._class_name = class_name
        self._menu_path = menu_path
        self._inputs = inputs

    def getDelegateClassName(self) -> str:
        return self._class_name

    def getMenuPath(self) -> str:
        return self._menu_path

    def getTitle(self) -> str:
        return self._title

    def inputs(self) -> list[FakeInput]:
        return self._inputs


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

    def getLog(self) -> str:
        return self._log

    def run(self, name: str, options: str) -> None:
        self.run_calls.append((name, options))


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


def test_search_allows_empty_query_and_caps_limit(monkeypatch):
    monkeypatch.setattr(minimal, "_collect_commands", lambda _ij: COMMANDS)
    monkeypatch.setattr(minimal, "run_read", lambda _name, fn: fn(object()))
    assert len(minimal.search_commands("", limit=2)["commands"]) == 2
    with pytest.raises(FijiError, match="between 1 and 100"):
        minimal.search_commands("", limit=101)


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


def test_scijava_record_wins_duplicate_delegate():
    merged = minimal._deduplicate_commands(
        [
            {
                "name": "Blur",
                "class_name": "pkg.Blur",
                "family": "imagej1",
                "inputs": [],
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


def test_run_script_dispatches_only_ijm_and_groovy(monkeypatch):
    service = FakeCommandService([])
    fake_ij = FakeIJ(
        service,
        log="log",
        active_image=FakeImage(),
    )
    monkeypatch.setattr(minimal, "run_mutation", _direct_mutation(fake_ij))

    ijm = minimal.run_script("ijm", "return 11;")
    groovy = minimal.run_script("groovy", "return 12")

    assert fake_ij.py.run_macro_calls == ["return 11;"]
    assert fake_ij.py.run_script_calls == [("groovy", "return 12")]
    assert ijm["result"] == 11
    assert groovy["result"] == 12
    assert ijm["log_tail"] == "log"
    assert groovy["active_image"]["title"] == "after-command"


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
    class HeadlessIJ(FakeIJ):
        pass

    class HeadlessPy(FakePy):
        def run_macro(self, code: str) -> FakeJavaInteger:
            raise type(
                "HeadlessException",
                (Exception,),
                {"__module__": "java.awt"},
            )()

    fake_ij = HeadlessIJ(FakeCommandService([]))
    fake_ij.py = HeadlessPy(FakeJavaMap())
    bridge._reset_runtime_for_tests(ready_ij=fake_ij)
    monkeypatch.setattr(bridge, "_jvm_is_healthy", lambda _ij: True)
    try:
        with pytest.raises(FijiError) as raised:
            minimal.run_script("ijm", "run('Measure');")
    finally:
        bridge._reset_runtime_for_tests()

    assert raised.value.code == "gui_required"
    assert raised.value.retryable is False
    assert raised.value.outcome is Outcome.UNKNOWN
    assert "FIJI_MODE=gui" in raised.value.recovery
