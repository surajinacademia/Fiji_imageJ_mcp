# Releasing `fiji-mcp-server`

## Version bump

1. Update **`version`** in [`pyproject.toml`](pyproject.toml) (PEP 440, e.g. `0.1.2`).
2. Update **[`CHANGELOG.md`](CHANGELOG.md)** — move items from *Unreleased* into a dated section for that version.
3. Optional: add or refresh **`RELEASE_NOTES_vX.Y.Z.md`** for GitHub Release notes text.

`fiji_mcp.__version__` is read from installed package metadata (`importlib.metadata`), so it matches `pyproject.toml` after `pip install` / PyPI.

## PyPI (first time)

1. Create the project on [PyPI](https://pypi.org/manage/projects/) named **`fiji-mcp-server`** (if the name is taken, rename in `pyproject.toml` and imports accordingly).
2. **Trusted Publisher (recommended):** [PyPI → Publishing → Add a pending publisher](https://docs.pypi.org/trusted-publishers/)  
   - Owner: `surajinacademia`  
   - Repository: `Fiji_imageJ_mcp`  
   - Workflow: `Publish to PyPI`  
   - Environment: leave blank unless you add a GitHub Environment and match it here.
3. Alternatively, create an **API token** and add repo secret **`PYPI_API_TOKEN`**, then uncomment the `with: password:` block in [`.github/workflows/publish-pypi.yml`](.github/workflows/publish-pypi.yml).

## GitHub Release → PyPI

1. Commit the version + changelog on `main` and push.
2. On GitHub: **Releases → Draft a new release** — create a new tag **`v0.1.1`** (must match the version you intend to ship), title e.g. `v0.1.1`, publish the release.
3. The **Publish to PyPI** workflow runs on `release: published`, builds with `python -m build`, and uploads the sdist + wheel.

You can re-run a failed publish from the **Actions** tab via **workflow_dispatch** on **Publish to PyPI**.

## Local dry run

```bash
pip install build twine
python -m build
twine check dist/*
```

## Install from PyPI (users)

```bash
pip install fiji-mcp-server
fiji-mcp-install install cursor --fiji-path /path/to/Fiji
```

See [`docs/quickstart.md`](docs/quickstart.md) for full setup.
