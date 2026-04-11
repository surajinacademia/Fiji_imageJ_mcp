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
required=(
  "extras/cursor-fiji-mcp-plugin/.cursor-plugin/plugin.json"
  "docs/releases/RELEASE_NOTES_v0.1.3.md"
)
for archive in "${tars[@]}"; do
  echo "Verifying sdist: ${archive}"
  listing=$(tar -tzf "${archive}")
  for path in "${required[@]}"; do
    if ! grep -qF -- "${path}" <<<"${listing}"; then
      echo "::error::sdist missing required path '${path}' in '${archive}'"
      grep -E 'extras/|docs/releases/RELEASE_NOTES' <<<"${listing}" || true
      exit 1
    fi
  done
done
echo "sdist layout OK (${#tars[@]} archive(s))"
