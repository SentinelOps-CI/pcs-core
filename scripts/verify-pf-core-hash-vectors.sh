#!/usr/bin/env bash
# Compare PCS hash vectors with provability-fabric-core adapter fixtures (Phase 7 PR-2).
set -euo pipefail

PF_CORE_TAG="${PF_CORE_TAG:-pf-core-v0.6.0}"
PF_CORE_REPO="${PF_CORE_REPO:-https://github.com/SentinelOps-CI/provability-fabric-core.git}"
WORK="${TMPDIR:-/tmp}/pf-core-hash-vectors-$$"
LOCAL="${1:-$(cd "$(dirname "$0")/.." && pwd)/python/tests/hash_vectors}"
UPSTREAM="${WORK}/provability-fabric-core/adapters/pcs/tests/fixtures/hash_vectors"

cleanup() { rm -rf "$WORK"; }
trap cleanup EXIT

git clone --depth 1 --branch "$PF_CORE_TAG" "$PF_CORE_REPO" "$WORK/provability-fabric-core"

if [ ! -d "$UPSTREAM" ]; then
  echo "missing upstream hash vectors at $UPSTREAM"
  exit 1
fi

fail=0
while IFS= read -r -d '' rel; do
  local_file="$LOCAL/$rel"
  upstream_file="$UPSTREAM/$rel"
  if [ ! -f "$local_file" ]; then
    echo "missing local vector: $rel"
    fail=1
    continue
  fi
  if ! diff -q "$local_file" "$upstream_file" >/dev/null 2>&1; then
    echo "hash vector drift: $rel (expected match with $PF_CORE_TAG)"
    diff -u "$local_file" "$upstream_file" || true
    fail=1
  fi
done < <(cd "$UPSTREAM" && find . -type f ! -name '.gitkeep' -print0)

if [ "$fail" -ne 0 ]; then
  exit 1
fi

echo "OK: PCS hash vectors match provability-fabric-core $PF_CORE_TAG"
