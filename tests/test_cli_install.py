"""Tests for fiji-mcp-install merge behavior."""

import json
from pathlib import Path

from fiji_mcp.cli import install as install_mod


def test_merge_fiji_mcp_server_creates_mcp_servers(tmp_path: Path) -> None:
    path = tmp_path / "mcp.json"
    install_mod._merge_fiji_mcp_server(path, "/opt/Fiji", "headless", None)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "mcpServers" in data
    assert "fiji" in data["mcpServers"]
    assert data["mcpServers"]["fiji"]["env"]["FIJI_PATH"] == "/opt/Fiji"
    assert data["mcpServers"]["fiji"]["env"]["FIJI_MODE"] == "headless"


def test_merge_fiji_mcp_server_preserves_other_servers(tmp_path: Path) -> None:
    path = tmp_path / "mcp.json"
    path.write_text(
        json.dumps({"mcpServers": {"other": {"command": "true"}}}),
        encoding="utf-8",
    )
    install_mod._merge_fiji_mcp_server(path, "/opt/Fiji", "headless", None)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "other" in data["mcpServers"]
    assert "fiji" in data["mcpServers"]


def test_claude_code_project_path(tmp_path: Path) -> None:
    out = install_mod.install_for_claude_code(
        "/opt/Fiji",
        "headless",
        None,
        project_root=tmp_path,
    )
    assert out == tmp_path / ".mcp.json"
    assert out.exists()
