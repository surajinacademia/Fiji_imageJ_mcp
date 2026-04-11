"""Lazy package exports (avoid importing JVM stack on ``import fiji_mcp``)."""


def test_mcp_is_fastmcp_after_attribute_access() -> None:
    import fiji_mcp

    mcp = fiji_mcp.mcp
    assert mcp.__class__.__name__ == "FastMCP"
