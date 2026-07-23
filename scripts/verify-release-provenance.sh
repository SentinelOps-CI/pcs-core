#!/usr/bin/env bash
# Consumer-side verification of release provenance without the producer working tree.
# Expects a provenance package directory (artifact download) containing:
#   ReleaseProvenanceBinding.v0.json, subjects.sha256, wheels/, sbom/, lockfiles/, …
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PKG_DIR="${1:-}"
if [ -z "${PKG_DIR}" ]; then
  echo "usage: $0 <provenance-package-dir>" >&2
  exit 2
fi
PKG_DIR="$(cd "${PKG_DIR}" && pwd)"

BINDING="${PKG_DIR}/ReleaseProvenanceBinding.v0.json"
SUBJECTS="${PKG_DIR}/subjects.sha256"
STATUS_FILE="${PKG_DIR}/attestation-status.json"
test -f "${BINDING}"
test -f "${SUBJECTS}"

export PKG_DIR BINDING SUBJECTS STATUS_FILE ROOT

python3 - <<'PY'
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

pkg = Path(os.environ["PKG_DIR"])
binding_path = Path(os.environ["BINDING"])
subjects_path = Path(os.environ["SUBJECTS"])
root = Path(os.environ["ROOT"])

binding = json.loads(binding_path.read_text(encoding="utf-8"))
if binding.get("artifact_type") != "ReleaseProvenanceBinding.v0":
    raise SystemExit(f"unexpected artifact_type: {binding.get('artifact_type')!r}")

# Schema validate when pcs_core is importable (producer CI / checkout). Soft if absent.
try:
    sys.path.insert(0, str(root / "python"))
    from pcs_core.validate import validate_artifact

    validate_artifact(binding, "ReleaseProvenanceBinding.v0", release_grade=True)
    print("OK schema ReleaseProvenanceBinding.v0")
except Exception as exc:  # noqa: BLE001 - consumer may lack package
    # Fail closed when schema validation is available and rejects.
    if "ValidationError" in type(exc).__name__ or "schema" in str(exc).lower():
        raise
    print(f"WARN schema validation skipped ({exc})")

def sha256_hex(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()

def sha256_bare(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

# Recompute binding digest (exclude signature_or_digest).
sealed = {k: v for k, v in binding.items() if k != "signature_or_digest"}
canonical = json.dumps(sealed, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
expected = "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
recorded = binding.get("signature_or_digest")
if recorded != expected:
    raise SystemExit(f"binding digest mismatch: {recorded!r} != {expected!r}")
print("OK binding signature_or_digest")

# Verify every subjects.sha256 line against on-disk files.
missing = []
mismatched = []
for line in subjects_path.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    parts = line.split(None, 1)
    if len(parts) != 2:
        raise SystemExit(f"bad subjects line: {line!r}")
    digest, rel = parts
    rel = rel.lstrip("./")
    path = pkg / rel
    if not path.is_file():
        missing.append(rel)
        continue
    actual = sha256_bare(path)
    if actual != digest:
        mismatched.append(f"{rel}: {actual} != {digest}")

if missing:
    raise SystemExit("missing subject files:\n  - " + "\n  - ".join(missing))
if mismatched:
    raise SystemExit("subject digest mismatches:\n  - " + "\n  - ".join(mismatched))
print(f"OK subjects.sha256 ({sum(1 for _ in subjects_path.read_text().splitlines() if _.strip())} entries)")

# Cross-check structured binding fields against files.
for wheel in binding["wheels"]:
    path = pkg / wheel["path"]
    if sha256_hex(path) != wheel["sha256"]:
        raise SystemExit(f"wheel digest drift: {wheel['path']}")
print(f"OK {len(binding['wheels'])} wheel digest(s)")

sbom = pkg / binding["sbom"]["path"]
if sha256_hex(sbom) != binding["sbom"]["sha256"]:
    raise SystemExit("SBOM digest drift")
print("OK SBOM digest")

for key, meta in binding["lockfiles"].items():
    path = pkg / "lockfiles" / key
    if sha256_hex(path) != meta["sha256"]:
        raise SystemExit(f"lockfile digest drift: {key}")
print("OK lockfile digests")

pin = pkg / "lockfiles" / "pins" / "python-base-image.json"
pin_data = json.loads(pin.read_text(encoding="utf-8"))
if pin_data["index_digest"] != binding["verifier_image"]["index_digest"]:
    raise SystemExit("verifier image index_digest drift vs pin file")
if binding["verifier_image"].get("pin_file_sha256") and sha256_hex(pin) != binding[
    "verifier_image"
]["pin_file_sha256"]:
    raise SystemExit("verifier pin file digest drift")
print(f"OK verifier image digest {binding['verifier_image']['index_digest']}")

bundle = binding["bundle"]
if bundle["status"] == "present":
    archive = pkg / bundle["archive_path"]
    if not archive.is_file():
        raise SystemExit(f"missing bundle archive {bundle['archive_path']}")
    if sha256_hex(archive) != bundle["archive_sha256"]:
        raise SystemExit("bundle archive digest drift")
    if not str(bundle.get("manifest_digest", "")).startswith("sha256:"):
        raise SystemExit("bundle manifest_digest missing")
    print(f"OK bundle root archive {bundle['archive_sha256']}")
    print(f"OK bundle manifest_digest {bundle['manifest_digest']}")
else:
    print(f"OK bundle absent ({bundle.get('absence_reason', 'n/a')})")

att = binding.get("attestation") or {}
status = att.get("status", "pending")
status_file = Path(os.environ["STATUS_FILE"])
file_status = None
require_signed = os.environ.get("PCS_PROVENANCE_REQUIRE_SIGNED", "0") == "1"
if status_file.is_file():
    st = json.loads(status_file.read_text(encoding="utf-8"))
    file_status = st.get("status")
    require_signed = require_signed or bool(st.get("require_signed"))

if status == "pending":
    raise SystemExit(
        "FAIL: attestation.status is still pending — producer did not finalize signed/gated"
    )

if status == "signed":
    if file_status and file_status != "signed":
        raise SystemExit(
            f"FAIL: binding claims signed but attestation-status.json is {file_status!r}"
        )
    print("OK attestation.status=signed (Sigstore / GitHub artifact attestation)")
elif status == "gated":
    reason = att.get("gate_reason") or "unspecified"
    print(f"WARN attestation gated: {reason}")
    if require_signed:
        raise SystemExit(
            "FAIL: signed provenance required but attestation.status=gated "
            "(org may lack artifact attestation permissions / GHEC for private repos)"
        )
    gated_notice = pkg / "PROVENANCE_ATTESTATION_GATED.json"
    if not gated_notice.is_file():
        raise SystemExit("FAIL: gated status without PROVENANCE_ATTESTATION_GATED.json")
    print("OK gated notice present (fail-closed honesty)")
else:
    raise SystemExit(f"unknown attestation.status: {status!r}")

# Identity bindings required by PR15.
for field in ("source_commit",):
    if not binding.get(field):
        raise SystemExit(f"missing {field}")
wf = binding["workflow"]
for field in ("repository", "workflow_ref", "workflow_sha", "run_id"):
    if not wf.get(field):
        raise SystemExit(f"missing workflow.{field}")
builder = binding["builder"]
for field in ("id", "runner_name", "runner_os"):
    if not builder.get(field):
        raise SystemExit(f"missing builder.{field}")
print(
    f"OK identity bindings commit={binding['source_commit'][:12]}… "
    f"workflow={wf['workflow_ref']} builder={builder['id']}"
)

result = {
    "ok": True,
    "attestation_status": status,
    "source_commit": binding["source_commit"],
    "binding_digest": binding["signature_or_digest"],
    "sbom_digest": binding["sbom"]["sha256"],
    "wheel_digests": [w["sha256"] for w in binding["wheels"]],
    "bundle_status": bundle["status"],
    "verifier_image_digest": binding["verifier_image"]["index_digest"],
}
(pkg / "consumer-verification-result.json").write_text(
    json.dumps(result, indent=2) + "\n", encoding="utf-8"
)
print("OK consumer digest verification")
print(json.dumps(result, indent=2))
PY

ATT_STATUS="$(python3 -c "import json; print(json.load(open(r'${BINDING}', encoding='utf-8'))['attestation']['status'])")"
REPO="$(python3 -c "import json; print(json.load(open(r'${BINDING}', encoding='utf-8'))['workflow']['repository'])")"

if [ "${ATT_STATUS}" = "signed" ]; then
  if ! command -v gh >/dev/null 2>&1; then
    echo "FAIL: gh CLI required to verify signed GitHub artifact attestations" >&2
    exit 1
  fi
  echo "== gh attestation verify (clean consumer) =="
  # Verify primary subjects against the GitHub attestations API.
  gh attestation verify "${BINDING}" --repo "${REPO}"
  # Wheels
  shopt -s nullglob
  for wheel in "${PKG_DIR}"/wheels/pcs_core-*.whl; do
    gh attestation verify "${wheel}" --repo "${REPO}"
  done
  # SBOM
  if [ -f "${PKG_DIR}/sbom/pcs-core.cdx.json" ]; then
    gh attestation verify "${PKG_DIR}/sbom/pcs-core.cdx.json" --repo "${REPO}"
  fi
  # Bundle archive when present
  ARCHIVE="$(python3 -c "import json; b=json.load(open(r'${BINDING}', encoding='utf-8')); print(b['bundle'].get('archive_path') or '')")"
  if [ -n "${ARCHIVE}" ] && [ -f "${PKG_DIR}/${ARCHIVE}" ]; then
    gh attestation verify "${PKG_DIR}/${ARCHIVE}" --repo "${REPO}"
  fi
  echo "OK gh attestation verify"
else
  echo "SKIP gh attestation verify (status=${ATT_STATUS})"
fi

echo "OK release provenance consumer verification"
