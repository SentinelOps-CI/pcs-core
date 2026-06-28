#!/usr/bin/env bash
# CertifyEdge release-gate dry-run (mock mode). Run from repository root. No git operations.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${ROOT}/python"
MOCK_DIR="${ROOT}/examples/pf-core-valid/certifyedge_mock"
OUT_CERT="${TMPDIR:-/tmp}/pfcore-certifyedge-dry-run.json"

export PF_CORE_CERTIFYEDGE_MODE=mock

cd "${PY}"
pip install -e ".[dev]" -q

echo ""
echo "=== CertifyEdge mock certifyedge-check ==="
pcs pf-core certifyedge-check \
  --trace "${MOCK_DIR}/trace.json" \
  --property qc_release.temporal.safety \
  --out "${OUT_CERT}"

echo ""
echo "=== Validate mock fixture ==="
pcs pf-core validate-trace "${MOCK_DIR}/trace.json"
pcs validate "${MOCK_DIR}/certificate.json"

echo "OK CertifyEdge dry-run (mock; not live release-gate attestation)"
