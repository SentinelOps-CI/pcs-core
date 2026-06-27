#!/usr/bin/env bash
set -euo pipefail

# Thin wrapper retained for local/CI use. Delegates to run-pf-core-adapter-ci.sh.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec bash "${ROOT}/scripts/run-pf-core-adapter-ci.sh" "$@"
