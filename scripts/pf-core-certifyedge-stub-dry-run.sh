#!/usr/bin/env bash
# CertifyEdge stub CLI dry-run (format contract, not live attestation). Run from repository root.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${ROOT}/python"
STUB="${ROOT}/scripts/certifyedge-stub.py"
TRACE="${ROOT}/examples/pf-core-valid/labtrust_replay/trace.json"
OUT_CERT="${TMPDIR:-/tmp}/pfcore-certifyedge-stub-dry-run.json"

if [[ ! -f "${STUB}" ]]; then
  echo "missing certifyedge-stub.py" >&2
  exit 1
fi

export PF_CORE_CERTIFYEDGE_MODE=live
export PF_CORE_CERTIFYEDGE_CLI="${STUB}"

cd "${PY}"
pip install -e ".[dev]" -q

echo ""
echo "=== CertifyEdge stub certifyedge-check ==="
pcs pf-core certifyedge-check \
  --trace "${TRACE}" \
  --property qc_release.temporal.safety \
  --out "${OUT_CERT}"

python3 - "${OUT_CERT}" <<'PY'
import json
import sys

cert = json.load(open(sys.argv[1], encoding="utf-8"))
checker_version = str(cert.get("checker_version") or "")
if not checker_version:
    print("FAIL: stub certificate missing checker_version")
    sys.exit(1)
if checker_version != "0.1.0":
    print(f"FAIL: unexpected checker_version: {checker_version}")
    sys.exit(1)
attestation = next(
    (
        str(item.get("proof_ref") or "")
        for item in cert.get("obligations") or []
        if isinstance(item, dict)
    ),
    "",
)
if not attestation:
    print("FAIL: stub certificate missing proof_ref attestation")
    sys.exit(1)
if not attestation.startswith("stub://certifyedge/"):
    print(f"FAIL: expected stub:// attestation, got {attestation}")
    sys.exit(1)
refs = cert.get("assumption_refs") or []
if attestation not in refs:
    print(f"FAIL: attestation_ref not in assumption_refs: {attestation}")
    sys.exit(1)
print(f"OK CertifyEdge stub dry-run: {attestation} (checker_version={checker_version})")
PY

echo "OK CertifyEdge stub dry-run (format contract; not release-grade live attestation)"
