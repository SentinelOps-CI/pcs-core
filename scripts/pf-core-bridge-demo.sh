#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "== PCS TraceCertificate validation =="
cd python
pip install -e . >/dev/null
pcs validate ../examples/labtrust/trace_certificate.valid.json

echo "== LabTrust adapter: TraceCertificate -> PFCoreTrace =="
python - <<'PY'
import json
from pathlib import Path
from pcs_core.pf_core_labtrust_adapter import normalize_labtrust_release

root = Path("..")
tc = json.loads((root / "examples/labtrust/trace_certificate.valid.json").read_text(encoding="utf-8"))
scb = json.loads((root / "examples/labtrust/science_claim_bundle.certified.valid.json").read_text(encoding="utf-8"))
receipt = scb["runtime_receipts"][0]
trace = normalize_labtrust_release(tc, receipt)
out = root / "examples/pf-core-valid/labtrust_replay/trace.generated.json"
out.write_text(json.dumps(trace, indent=2) + "\n", encoding="utf-8")
print(f"Wrote {out}")
PY

echo "== PF-Core replay =="
pcs pf-core replay-trace ../examples/pf-core-valid/labtrust_replay/trace.json

echo "== External checker attestation -> PFCoreCertificate =="
python - <<'PY'
import json
from pathlib import Path
from pcs_core.pf_core_certificate import attach_external_certificate_check

root = Path("..")
trace = json.loads((root / "examples/pf-core-valid/labtrust_replay/trace.json").read_text(encoding="utf-8"))
cert = attach_external_certificate_check(
    trace,
    checker="certifyedge",
    checker_version="0.1.0",
    attestation_ref="examples/labtrust/trace_certificate.valid.json",
    assumption_refs=["as-labtrust-qc-v0.1"],
)
out = root / "examples/pf-core-valid/labtrust_replay/PFCoreCertificate.v0.generated.json"
out.write_text(json.dumps(cert, indent=2) + "\n", encoding="utf-8")
print(f"Wrote {out} claim_class={cert['claim_class']}")
PY

pcs validate ../examples/pf-core-valid/labtrust_replay/PFCoreCertificate.v0.generated.json

echo "== CertifyEdge mock check -> PFCoreCertificate =="
PCS_CERTIFYEDGE_MOCK=1 pcs pf-core certifyedge-check \
  --trace ../examples/pf-core-valid/labtrust_replay/trace.json \
  --property qc_release.temporal.safety \
  --out ../examples/pf-core-valid/labtrust_replay/PFCoreCertificate.certifyedge.generated.json

pcs validate ../examples/pf-core-valid/labtrust_replay/PFCoreCertificate.certifyedge.generated.json

echo "OK pf-core bridge demo"
