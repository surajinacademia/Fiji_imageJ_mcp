#!/usr/bin/env sh
# Easiest install: creates .venv and pip-installs all Python dependencies.
# Requires: Python 3.10+, git clone of this repo, network.
cd "$(dirname "$0")" || exit 1
exec python3 scripts/install_fiji_mcp.py "$@"
