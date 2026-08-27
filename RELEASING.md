# Releasing `fiji-mcp-server`

## Prepare a release

1. Set the PEP 440 version in [`pyproject.toml`](pyproject.toml).
2. Move the relevant entry from [the changelog](CHANGELOG.md) into a dated
   release section.
3. Run the local distribution validation:

   ```bash
   pip install ".[publish]"
   python -m build
   python -m twine check dist/*
   python tests/wheel_smoke.py dist/fiji_mcp_server-0.2.0-py3-none-any.whl
   ```

The wheel smoke probe creates a fresh environment, installs the wheel, starts
the generated console entry point without `FIJI_PATH`, and checks its nine-tool
stdio surface.

## Publish through GitHub Actions

1. Commit and push the version and changelog changes on `main`.
2. Publish a GitHub Release whose tag matches the package version, such as
   `v0.2.0`.
3. The `publish-pypi.yml` workflow builds the distribution, runs Twine and the
   wheel smoke probe, then publishes with PyPI trusted publishing.

Configure the PyPI Trusted Publisher for repository
`surajinacademia/Fiji_imageJ_mcp` and workflow filename `publish-pypi.yml`.
The workflow can also be started manually after the publisher is configured.

## Manual user installation and configuration

Users install the released package with:

```bash
pip install fiji-mcp-server
```

They must install Fiji locally and manually add a generic stdio server entry to
their MCP client configuration, replacing the Fiji root with a directory that
contains `jars/` and `plugins/`:

```json
{
  "mcpServers": {
    "fiji": {
      "command": "fiji-mcp-server",
      "env": {
        "FIJI_PATH": "/Applications/Fiji",
        "FIJI_MODE": "headless"
      }
    }
  }
}
```

`FIJI_MODE` is optional and defaults to `headless`. See the
[tool reference](docs/tools.md) for the current API.
