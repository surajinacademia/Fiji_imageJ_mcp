#!/usr/bin/env bash
# After `python -m build`, assert the sdist tarball still carries paths we rely on
# (MANIFEST graft / re-includes). Run from repository root.
set -euo pipefail
shopt -s nullglob
tars=(dist/*.tar.gz)
if ((${#tars[@]} == 0)); then
  echo "::error::No dist/*.tar.gz found; run python -m build first."
  exit 1
fi
required_subpath="extras/cursor-fiji-mcp-plugin/.cursor-plugin/plugin.json"
for archive in "${tars[@]}"; do
  echo "Verifying sdist: ${archive}"
  listing=$(tar -tzf "${archive}")
  if ! grep -qF -- "${required_subpath}" <<<"${listing}"; then
    echo "::error::sdist missing Cursor plugin bundle path '${required_subpath}' in '${archive}'"
    grep -E 'extras/' <<<"${listing}" || true
    exit 1
  fi
  if ! grep -qE 'docs/releases/RELEASE_NOTES_v[0-9]+\.[0-9]+\.[0-9]+\.md$' <<<"${listing}"; then
    echo "::error::sdist missing any docs/releases/RELEASE_NOTES_vX.Y.Z.md in '${archive}'"
    grep 'docs/releases/' <<<"${listing}" || true
    exit 1
  fi
done
echo "sdist layout OK (${#tars[@]} archive(s))"
