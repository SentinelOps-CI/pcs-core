#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}/python"
python scripts/materialize_labtrust_protocol_artifacts.py
pcs shared-hash-vectors verify
