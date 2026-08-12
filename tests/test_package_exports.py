"""Lazy package exports (avoid importing the MCP server on ``import fiji_mcp``)."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 only
    import tomli as tomllib

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _release_workflow() -> dict[str, Any]:
    workflow = yaml.safe_load(Path(".github/workflows/publish-pypi.yml").read_text())
    assert isinstance(workflow, dict)
    return workflow


def _assert_release_workflow_security(workflow: dict[str, Any]) -> None:
    expected_jobs = {
        "build": {
            "runs-on": "ubuntu-latest",
            "permissions": {"contents": "read"},
            "steps": [
                {
                    "name": "Check out the release source",
                    "uses": "actions/checkout@11d5960a326750d5838078e36cf38b85af677262",
                },
                {
                    "name": "Set up Python",
                    "uses": "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065",
                    "with": {"python-version": "3.12", "cache": "pip"},
                },
                {
                    "name": "Install reviewed build and validation tools",
                    "run": (
                        'python -m pip install "pip==25.3" '
                        '"setuptools==84.0.0" "wheel==0.45.1" '
                        '"build==1.4.0" "twine==6.2.0" "fastmcp==2.14.3"'
                    ),
                },
                {
                    "name": "Build distribution",
                    "run": "python -m build --no-isolation",
                },
                {
                    "name": "Freeze distribution artifact",
                    "uses": (
                        "actions/upload-artifact@"
                        "ea165f8d65b6e75b540449e92b4886f43607fa02"
                    ),
                    "with": {
                        "name": "python-dist",
                        "path": "dist/",
                        "if-no-files-found": "error",
                    },
                },
                {
                    "name": "Validate distribution",
                    "run": "python -m twine check dist/*",
                },
                {
                    "name": "Smoke-test installed wheel",
                    "run": (
                        "python tests/wheel_smoke.py "
                        "dist/fiji_mcp_server-0.2.0-py3-none-any.whl"
                    ),
                },
            ],
        },
        "publish": {
            "needs": "build",
            "runs-on": "ubuntu-latest",
            "permissions": {"id-token": "write"},
            "steps": [
                {
                    "name": "Download frozen distribution",
                    "uses": (
                        "actions/download-artifact@"
                        "d3f86a106a0bac45b974a628896c90dbdf5c8093"
                    ),
                    "with": {"name": "python-dist", "path": "dist/"},
                },
                {
                    "name": "Publish to PyPI",
                    "uses": (
                        "pypa/gh-action-pypi-publish@"
                        "cef221092ed1bacb1cc03d23a2d87d1d172e277b"
                    ),
                },
            ],
        },
    }

    trigger_keys = [key for key in ("on", True) if key in workflow]
    assert len(trigger_keys) == 1
    assert workflow[trigger_keys[0]] == {
        "release": {"types": ["published"]},
        "workflow_dispatch": None,
    }
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["jobs"] == expected_jobs


def test_package_import_keeps_mcp_lazy() -> None:
    env = {**os.environ, "PYTHONPATH": str(_REPO_ROOT / "src")}
    result = subprocess.run(  # noqa: S603 -- fixed interpreter and test script
        [
            sys.executable,
            "-c",
            "import sys; import fiji_mcp; assert 'fiji_mcp.server' not in sys.modules",
        ],
        cwd=_REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_mcp_is_fastmcp_after_attribute_access() -> None:
    import fiji_mcp

    mcp = fiji_mcp.mcp
    assert mcp.__class__.__name__ == "FastMCP"


def test_runtime_dependencies_are_minimal():
    project = tomllib.loads(Path("pyproject.toml").read_text())
    assert project["project"]["version"] == "0.2.0"
    assert project["project"]["dependencies"] == [
        "fastmcp>=2.10.3,<3",
        "pyimagej>=1.5.0",
        "numpy>=1.26.0",
        "Pillow>=10.0.0",
    ]
    assert project["project"]["scripts"] == {
        "fiji-mcp-server": "fiji_mcp.__main__:main"
    }


def test_publish_workflow_matches_complete_security_contract() -> None:
    _assert_release_workflow_security(_release_workflow())


def test_test_and_dev_tooling_are_minimal() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text())
    assert project["project"]["optional-dependencies"]["test"] == [
        "pytest>=8.0.0",
        "pytest-asyncio>=0.23.0",
        "pytest-timeout>=2.2.0",
        "PyYAML>=6.0.0",
        "tomli>=2.0.1; python_version < '3.11'",
    ]
    assert project["project"]["optional-dependencies"]["dev"] == [
        "ruff>=0.12.10",
        "mypy>=1.17.0,<2.0",
        "pre-commit>=4.3.0",
    ]
    assert project["tool"]["pytest"]["ini_options"]["markers"] == [
        "integration: integration tests requiring local Fiji runtime",
        "mcp_stdio: subprocess MCP client over stdio (FastMCP Client)",
    ]
    assert "no_site_packages" not in project["tool"]["mypy"]
    assert project["tool"]["mypy"]["overrides"] == [
        {
            "module": ["numpy", "numpy.*"],
            "follow_imports": "skip",
            "follow_imports_for_stubs": True,
        }
    ]
    assert "black" not in project["tool"]
    assert not Path(".coveragerc").exists()


def test_source_distribution_manifest_is_minimal() -> None:
    assert Path("MANIFEST.in").read_text().splitlines() == [
        "include README.md",
        "include LICENSE",
        "include CHANGELOG.md",
        "include RELEASING.md",
        "include docs/tools.md",
        "prune tests",
        "prune docs/releases",
        "prune docs/superpowers",
        "exclude CLAUDE.md",
        "exclude .mcp.json",
        "exclude AGENTS.md",
        "exclude tests.md",
        "global-exclude __pycache__ *.py[cod] .DS_Store",
    ]


def test_repository_surface_is_lean_and_local_rules_are_ignored() -> None:
    for required in (
        "README.md",
        "docs/tools.md",
        "CHANGELOG.md",
        "RELEASING.md",
        "LICENSE",
    ):
        assert Path(required).is_file()

    git = shutil.which("git")
    assert git is not None
    tracked = set(
        subprocess.run(  # noqa: S603 - exact local Git query
            [git, "ls-files"],
            cwd=_REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
    )
    deleted = set(
        subprocess.run(  # noqa: S603 - exact local Git query
            [git, "diff", "HEAD", "--name-only", "--diff-filter=D"],
            cwd=_REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
    )
    tracked -= deleted
    for removed in (
        "AGENTS.md",
        ".agents",
        ".codex",
        "CLAUDE.md",
        ".mcp.json",
        "tests.md",
        "docs/releases",
        "docs/superpowers",
    ):
        assert not any(
            path == removed or path.startswith(f"{removed}/") for path in tracked
        )
    assert not any(
        path == ".coverage" or path.startswith(".coverage.") for path in tracked
    )

    ignored = set(Path(".gitignore").read_text().splitlines())
    assert {
        "/AGENTS.md",
        "/.agents/",
        "/.codex/",
        "/CLAUDE.md",
        "/.mcp.json",
        "/tests.md",
        "/.coverage",
        "/.coverage.*",
    } <= ignored

    readme = Path("README.md").read_text()
    releasing = Path("RELEASING.md").read_text()
    assert "docs/releases" not in readme
    assert "docs/releases" not in releasing


def test_readme_documents_v020_onboarding_and_exact_tool_surface() -> None:
    readme = Path("README.md").read_text()
    json_config = readme.split("```json\n", maxsplit=1)[1].split("\n```", maxsplit=1)[0]
    toml_config = readme.split("```toml\n", maxsplit=1)[1].split("\n```", maxsplit=1)[0]
    tool_section = readme.split("## The nine tools\n", maxsplit=1)[1].split(
        "\n## ", maxsplit=1
    )[0]
    documented_tools = re.findall(r"^\| `([^`]+)` \|", tool_section, re.MULTILINE)

    assert "This README documents v0.2.0" in readme
    assert 'python -m pip install "fiji-mcp-server==0.2.0"' in readme
    assert "codex mcp add fiji" in readme
    assert json.loads(json_config)["mcpServers"]["fiji"]["command"] == (
        "fiji-mcp-server"
    )
    assert tomllib.loads(toml_config)["mcp_servers"]["fiji"]["env"] == {
        "FIJI_PATH": "/Applications/Fiji",
        "FIJI_MODE": "headless",
    }
    assert documented_tools == [
        "get_state",
        "search_commands",
        "run_command",
        "run_script",
        "open_image",
        "save_image",
        "get_results",
        "screenshot",
        "compare_screenshots",
    ]
    assert readme.count("> **Prompt:**") >= 5
    assert "fiji-mcp-install" not in readme
    assert "trusted arbitrary local code" in readme
    assert "The MCP client owns the stdio process" in readme
    assert "python -m pip install ." in readme
    assert "`save_image` is strict" in readme
    assert "within this MCP server process" in readme
    assert re.search(r"not a\s+cross-process atomic publisher", readme)
    assert (
        "`screenshot` and `compare_screenshots` overwrite an existing `save_path`"
        in readme
    )
    assert (
        "https://github.com/surajinacademia/Fiji_imageJ_mcp/blob/main/docs/tools.md"
        in readme
    )
    assert (
        "https://github.com/surajinacademia/Fiji_imageJ_mcp/blob/main/LICENSE" in readme
    )
    assert (
        "https://github.com/surajinacademia/Fiji_imageJ_mcp/blob/main/CHANGELOG.md"
        in readme
    )
