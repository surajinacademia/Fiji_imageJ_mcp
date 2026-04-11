# fiji-mcp-server v0.1.3

## PyPI project page

- **README demo images** now use **Markdown `![]()` inside tables** so [pypi.org](https://pypi.org/project/fiji-mcp-server/) renders the gallery consistently (raw HTML blocks are easier for Warehouse to mishandle).

**Ship checklist:** confirm the release exists on production PyPI (`curl -s https://pypi.org/pypi/fiji-mcp-server/json | jq .releases | jq keys`) after the GitHub **Release published** workflow finishes—only published versions get a working `/project/.../X.Y.Z/` description page.

## Other changes since v0.1.1

See [CHANGELOG.md](CHANGELOG.md) for v0.1.2 / v0.1.3 (bundled agent skill, expanded macro templates, absolute image URLs).
