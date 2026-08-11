"""Public MCP tool registration contract."""

from fastmcp import Client

from fiji_mcp.server import mcp

EXPECTED = {
    "get_state",
    "search_commands",
    "run_command",
    "run_script",
    "open_image",
    "save_image",
    "get_results",
    "screenshot",
    "compare_screenshots",
}

EXPECTED_INPUTS = {
    "get_state": (set(), set()),
    "search_commands": ({"query", "limit"}, {"query"}),
    "run_command": ({"name", "parameters", "options"}, {"name"}),
    "run_script": ({"language", "code"}, {"language", "code"}),
    "open_image": ({"path"}, {"path"}),
    "save_image": ({"path"}, {"path"}),
    "get_results": ({"offset", "limit"}, set()),
    "screenshot": ({"target", "save_path"}, {"target"}),
    "compare_screenshots": (
        {"before_path", "after_path", "save_path"},
        {"before_path", "after_path"},
    ),
}


async def test_exact_public_tool_surface() -> None:
    async with Client(mcp) as client:
        tools = await client.list_tools()

    assert {tool.name for tool in tools} == EXPECTED


async def test_schema_defaults_and_limits_are_visible() -> None:
    async with Client(mcp) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}

    assert tools["search_commands"].inputSchema["properties"]["limit"]["default"] == 20
    assert tools["get_results"].inputSchema["properties"]["limit"]["default"] == 500
    assert set(tools["run_script"].inputSchema["properties"]["language"]["enum"]) == {
        "ijm",
        "groovy",
    }
    for name, (properties, required) in EXPECTED_INPUTS.items():
        schema = tools[name].inputSchema
        assert set(schema["properties"]) == properties
        assert set(schema.get("required", [])) == required
        assert tools[name].description
