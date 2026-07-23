#!/usr/bin/env bash
# Finalize ReleaseProvenanceBinding attestation status after GitHub attest steps.
# Usage:
#   scripts/finalize-provenance-attestation.sh <pkg-dir> signed|gated [reason] [id1,id2] [url1,url2]
set -euo pipefail

PKG_DIR="${1:?provenance package dir}"
STATUS="${2:?signed|gated}"
REASON="${3:-}"
IDS_CSV="${4:-}"
URLS_CSV="${5:-}"

BINDING="${PKG_DIR}/ReleaseProvenanceBinding.v0.json"
test -f "${BINDING}"

export PKG_DIR BINDING STATUS REASON IDS_CSV URLS_CSV

python3 - <<'PY'
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

pkg = Path(os.environ["PKG_DIR"])
path = Path(os.environ["BINDING"])
status = os.environ["STATUS"]
if status not in {"signed", "gated"}:
    raise SystemExit(f"status must be signed|gated, got {status!r}")

binding = json.loads(path.read_text(encoding="utf-8"))
ids = [x for x in os.environ.get("IDS_CSV", "").split(",") if x]
urls = [x for x in os.environ.get("URLS_CSV", "").split(",") if x]
reason = os.environ.get("REASON") or None

att = {
    "status": status,
    "predicate_type": "https://slsa.dev/provenance/v1",
    "method": "actions/attest-build-provenance" if status == "signed" else "none",
    "attestation_ids": ids,
    "attestation_urls": urls,
}
if status == "gated":
    att["gate_reason"] = reason or (
        "GitHub artifact attestations unavailable "
        "(permissions, private-repo plan, or OIDC). Digests remain binding; "
        "do not claim signed SLSA provenance."
    )
binding["attestation"] = att

sealed = {k: v for k, v in binding.items() if k != "signature_or_digest"}
canonical = json.dumps(sealed, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
binding["signature_or_digest"] = "sha256:" + hashlib.sha256(
    canonical.encode("utf-8")
).hexdigest()
path.write_text(json.dumps(binding, indent=2) + "\n", encoding="utf-8")

# Refresh subjects.sha256 line for the binding file itself.
subjects = pkg / "subjects.sha256"
bare = hashlib.sha256(path.read_bytes()).hexdigest()
lines = []
replaced = False
for line in subjects.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    digest, rel = line.split(None, 1)
    if rel.strip() in {"ReleaseProvenanceBinding.v0.json", "./ReleaseProvenanceBinding.v0.json"}:
        lines.append(f"{bare}  ReleaseProvenanceBinding.v0.json")
        replaced = True
    else:
        lines.append(line)
if not replaced:
    lines.insert(0, f"{bare}  ReleaseProvenanceBinding.v0.json")
subjects.write_text("\n".join(lines) + "\n", encoding="utf-8")

status_path = pkg / "attestation-status.json"
require_signed = False
if status_path.is_file():
    prev = json.loads(status_path.read_text(encoding="utf-8"))
    require_signed = bool(prev.get("require_signed"))
status_path.write_text(
    json.dumps(
        {
            "status": status,
            "require_signed": require_signed,
            "gate_reason": att.get("gate_reason"),
            "attestation_ids": ids,
            "attestation_urls": urls,
        },
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)

if status == "gated":
    notice = {
        "artifact_type": "ProvenanceAttestationGated.v0",
        "status": "gated",
        "reason": att["gate_reason"],
        "binding_digest": binding["signature_or_digest"],
        "honesty": (
            "Digest-bound ReleaseProvenanceBinding.v0 is present. "
            "Signed in-toto/SLSA attestation was not produced. "
            "Do not advertise this release as SLSA-attested until status=signed."
        ),
    }
    (pkg / "PROVENANCE_ATTESTATION_GATED.json").write_text(
        json.dumps(notice, indent=2) + "\n", encoding="utf-8"
    )

print(f"OK finalized attestation.status={status}")
print(f"binding digest {binding['signature_or_digest']}")
PY
