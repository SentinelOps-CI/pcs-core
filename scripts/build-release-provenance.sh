#!/usr/bin/env bash
# Build release provenance subjects + ReleaseProvenanceBinding.v0.
# Binds: source commit, workflow/builder identity, lockfiles, verifier image
# digest, wheel digests, SBOM digest, and (when present) PF-Core bundle root.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${1:-${ROOT}/dist/provenance}"
WHEEL_DIR="${PCS_PROVENANCE_WHEEL_DIR:-${ROOT}/dist/wheels}"
SBOM_DIR="${PCS_PROVENANCE_SBOM_DIR:-${ROOT}/dist/sbom}"
BUNDLE_DIR="${PCS_PROVENANCE_BUNDLE_DIR:-}"
BUILD_WHEELS="${PCS_PROVENANCE_BUILD_WHEELS:-1}"
BUILD_SBOM="${PCS_PROVENANCE_BUILD_SBOM:-1}"

mkdir -p "${OUT_DIR}" "${WHEEL_DIR}"

sha256_file() {
  local path="$1"
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "${path}" | awk '{print $1}'
  else
    python3 -c "import hashlib, pathlib, sys; print(hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest())" "${path}"
  fi
}

VERSION="$(tr -d '\r\n' < "${ROOT}/VERSION")"
SOURCE_COMMIT="${GITHUB_SHA:-}"
if [ -z "${SOURCE_COMMIT}" ]; then
  SOURCE_COMMIT="$(git -C "${ROOT}" rev-parse HEAD)"
fi
SOURCE_REF="${GITHUB_REF:-$(git -C "${ROOT}" rev-parse --abbrev-ref HEAD 2>/dev/null || echo local)}"

if [ "${BUILD_WHEELS}" = "1" ]; then
  if ! python3 -c "import build" >/dev/null 2>&1; then
    python3 -m pip install --upgrade build >/dev/null 2>&1 \
      || python3 -m pip install --upgrade --user build >/dev/null 2>&1 \
      || python3 -m pip install --upgrade --break-system-packages build >/dev/null
  fi
  rm -rf "${ROOT}/python/dist"
  (cd "${ROOT}/python" && python3 -m build --wheel)
  shopt -s nullglob
  wheels=("${ROOT}/python/dist"/pcs_core-*.whl)
  shopt -u nullglob
  if [ "${#wheels[@]}" -eq 0 ]; then
    echo "FAIL: no pcs_core wheel produced under python/dist" >&2
    exit 1
  fi
  cp -f "${wheels[@]}" "${WHEEL_DIR}/"
fi

shopt -s nullglob
WHEEL_FILES=("${WHEEL_DIR}"/pcs_core-*.whl)
shopt -u nullglob
if [ "${#WHEEL_FILES[@]}" -eq 0 ]; then
  echo "FAIL: no wheels in ${WHEEL_DIR}" >&2
  exit 1
fi

if [ "${BUILD_SBOM}" = "1" ]; then
  bash "${ROOT}/scripts/generate-sbom.sh" "${SBOM_DIR}"
fi
SBOM_PATH="${SBOM_DIR}/pcs-core.cdx.json"
test -f "${SBOM_PATH}"

# Optional PF-Core release bundle (directory). Archive for subject attestation.
BUNDLE_STATUS="absent"
BUNDLE_PATH=""
BUNDLE_ARCHIVE=""
BUNDLE_ARCHIVE_SHA=""
BUNDLE_MANIFEST_DIGEST=""
BUNDLE_ABSENCE="Bundle directory not provided (set PCS_PROVENANCE_BUNDLE_DIR)."

if [ -n "${BUNDLE_DIR}" ] && [ -d "${BUNDLE_DIR}" ]; then
  BUNDLE_STATUS="present"
  BUNDLE_PATH="${BUNDLE_DIR}"
  BUNDLE_ABSENCE=""
  BUNDLE_ARCHIVE="${OUT_DIR}/pf-core-release-bundle.tar.gz"
  # Deterministic-ish archive: sorted paths, stable ownership metadata.
  (
    cd "${BUNDLE_DIR}"
    if tar --version 2>/dev/null | grep -qi gnu; then
      tar --sort=name --owner=0 --group=0 --numeric-owner --mtime='UTC 1970-01-01' \
        -czf "${BUNDLE_ARCHIVE}" .
    else
      tar -czf "${BUNDLE_ARCHIVE}" .
    fi
  )
  BUNDLE_ARCHIVE_SHA="$(sha256_file "${BUNDLE_ARCHIVE}")"
  if [ -f "${BUNDLE_DIR}/manifest.json" ]; then
    BUNDLE_MANIFEST_DIGEST="$(python3 - <<PY
import json
from pathlib import Path
m = json.loads(Path(r"${BUNDLE_DIR}/manifest.json").read_text(encoding="utf-8"))
digest = m.get("signature_or_digest") or ""
if not str(digest).startswith("sha256:"):
    raise SystemExit("manifest.json missing signature_or_digest")
print(digest)
PY
)"
  else
    echo "FAIL: bundle at ${BUNDLE_DIR} missing manifest.json" >&2
    exit 1
  fi
fi

# Copy lockfiles into provenance package for consumer verification without repo checkout.
LOCK_OUT="${OUT_DIR}/lockfiles"
mkdir -p "${LOCK_OUT}/python" "${LOCK_OUT}/rust" "${LOCK_OUT}/typescript" "${LOCK_OUT}/pins"
cp -f "${ROOT}/python/requirements.lock" "${LOCK_OUT}/python/requirements.lock"
cp -f "${ROOT}/rust/Cargo.lock" "${LOCK_OUT}/rust/Cargo.lock"
cp -f "${ROOT}/typescript/package-lock.json" "${LOCK_OUT}/typescript/package-lock.json"
cp -f "${ROOT}/pins/python-base-image.json" "${LOCK_OUT}/pins/python-base-image.json"

# Stage wheels + SBOM beside binding for the consumer job.
STAGE_WHEELS="${OUT_DIR}/wheels"
STAGE_SBOM="${OUT_DIR}/sbom"
mkdir -p "${STAGE_WHEELS}" "${STAGE_SBOM}"
cp -f "${WHEEL_FILES[@]}" "${STAGE_WHEELS}/"
cp -f "${SBOM_PATH}" "${STAGE_SBOM}/pcs-core.cdx.json"
if [ -f "${SBOM_DIR}/pcs-core.spdx.json" ]; then
  cp -f "${SBOM_DIR}/pcs-core.spdx.json" "${STAGE_SBOM}/pcs-core.spdx.json"
fi

export ROOT OUT_DIR VERSION SOURCE_COMMIT SOURCE_REF
export BUNDLE_STATUS BUNDLE_PATH BUNDLE_ARCHIVE BUNDLE_ARCHIVE_SHA
export BUNDLE_MANIFEST_DIGEST BUNDLE_ABSENCE STAGE_WHEELS STAGE_SBOM LOCK_OUT

python3 - <<'PY'
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

root = Path(os.environ["ROOT"])
out = Path(os.environ["OUT_DIR"])
version = os.environ["VERSION"]
source_commit = os.environ["SOURCE_COMMIT"].lower()
if len(source_commit) != 40 or any(c not in "0123456789abcdef" for c in source_commit):
    raise SystemExit(f"invalid source_commit: {source_commit!r}")

def sha256_hex(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()

def sha256_bare(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

lock_specs = {
    "python/requirements.lock": root / "python" / "requirements.lock",
    "rust/Cargo.lock": root / "rust" / "Cargo.lock",
    "typescript/package-lock.json": root / "typescript" / "package-lock.json",
}
lockfiles = {
    key: {"path": key, "sha256": sha256_hex(path)}
    for key, path in lock_specs.items()
}

pin_path = root / "pins" / "python-base-image.json"
pin = json.loads(pin_path.read_text(encoding="utf-8"))
index_digest = pin["index_digest"]
if not str(index_digest).startswith("sha256:"):
    raise SystemExit("pins/python-base-image.json index_digest must be sha256:...")

wheels_dir = Path(os.environ["STAGE_WHEELS"])
wheels = []
for wheel in sorted(wheels_dir.glob("pcs_core-*.whl")):
    wheels.append(
        {
            "path": f"wheels/{wheel.name}",
            "filename": wheel.name,
            "sha256": sha256_hex(wheel),
        }
    )
if not wheels:
    raise SystemExit("no staged wheels")

sbom_path = Path(os.environ["STAGE_SBOM"]) / "pcs-core.cdx.json"
sbom_text = sbom_path.read_text(encoding="utf-8")
sbom_format = "CycloneDX-JSON"
if '"scaffold"' in sbom_text or "Scaffold SBOM" in sbom_text:
    sbom_format = "scaffold-CycloneDX-JSON"

repo = os.environ.get("GITHUB_REPOSITORY", "local/pcs-core")
server = os.environ.get("GITHUB_SERVER_URL", "https://github.com").rstrip("/")
run_id = os.environ.get("GITHUB_RUN_ID", "local")
run_attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "1")
workflow_ref = os.environ.get(
    "GITHUB_WORKFLOW_REF",
    f"{repo}/.github/workflows/release-provenance.yml@{os.environ.get('SOURCE_REF', 'local')}",
)
workflow_sha = os.environ.get("GITHUB_WORKFLOW_SHA", source_commit)
if len(workflow_sha) != 40:
    workflow_sha = source_commit
event_name = os.environ.get("GITHUB_EVENT_NAME", "local")
runner_name = os.environ.get("RUNNER_NAME", "local")
runner_os = os.environ.get("RUNNER_OS", os.name)
runner_arch = os.environ.get("RUNNER_ARCH", "unknown")
builder_id = f"{server}/{repo}/actions/runs/{run_id}"

bundle: dict = {"status": os.environ["BUNDLE_STATUS"]}
if bundle["status"] == "present":
    archive = Path(os.environ["BUNDLE_ARCHIVE"])
    bundle.update(
        {
            "path": "pf-core-release-bundle/",
            "archive_path": archive.name,
            "archive_sha256": "sha256:" + os.environ["BUNDLE_ARCHIVE_SHA"],
            "manifest_digest": os.environ["BUNDLE_MANIFEST_DIGEST"],
        }
    )
else:
    bundle["absence_reason"] = os.environ.get("BUNDLE_ABSENCE") or "absent"

binding = {
    "schema_version": "v0",
    "artifact_type": "ReleaseProvenanceBinding.v0",
    "canonicalization_version": "v1",
    "version": version,
    "source_commit": source_commit,
    "source_ref": os.environ.get("SOURCE_REF", "local"),
    "workflow": {
        "repository": repo,
        "workflow_ref": workflow_ref,
        "workflow_sha": workflow_sha.lower(),
        "run_id": str(run_id),
        "run_attempt": str(run_attempt),
        "event_name": event_name,
        "server_url": server,
    },
    "builder": {
        "id": builder_id,
        "runner_name": runner_name,
        "runner_os": runner_os,
        "runner_arch": runner_arch,
    },
    "lockfiles": lockfiles,
    "verifier_image": {
        "pin_path": "pins/python-base-image.json",
        "index_digest": index_digest,
        "dockerfile_from": pin["dockerfile_from"],
        "pin_file_sha256": sha256_hex(pin_path),
        **(
            {"amd64_digest": pin["amd64_digest"]}
            if pin.get("amd64_digest")
            else {}
        ),
    },
    "wheels": wheels,
    "sbom": {
        "path": "sbom/pcs-core.cdx.json",
        "sha256": sha256_hex(sbom_path),
        "format": sbom_format,
    },
    "bundle": bundle,
    "attestation": {
        "status": "pending",
        "predicate_type": "https://slsa.dev/provenance/v1",
        "method": "none",
        "attestation_ids": [],
        "attestation_urls": [],
    },
    "subjects_checksums_path": "subjects.sha256",
}

# Seal without signature_or_digest, then attach digest of sealed body.
sealed = {k: v for k, v in binding.items() if k != "signature_or_digest"}
canonical = json.dumps(sealed, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
binding["signature_or_digest"] = "sha256:" + hashlib.sha256(
    canonical.encode("utf-8")
).hexdigest()

binding_path = out / "ReleaseProvenanceBinding.v0.json"
binding_path.write_text(json.dumps(binding, indent=2) + "\n", encoding="utf-8")

# Immutable subjects attested BEFORE the binding is finalized (binding digest
# changes when attestation.status flips pending → signed|gated).
immutable: list[str] = []
for wheel in sorted(wheels_dir.glob("pcs_core-*.whl")):
    immutable.append(f"{sha256_bare(wheel)}  wheels/{wheel.name}")
immutable.append(f"{sha256_bare(sbom_path)}  sbom/pcs-core.cdx.json")
if bundle["status"] == "present":
    archive = Path(os.environ["BUNDLE_ARCHIVE"])
    immutable.append(f"{sha256_bare(archive)}  {archive.name}")
for rel, path in lock_specs.items():
    staged = out / "lockfiles" / Path(rel)
    immutable.append(f"{sha256_bare(staged)}  lockfiles/{rel}")
immutable.append(
    f"{sha256_bare(out / 'lockfiles' / 'pins' / 'python-base-image.json')}  "
    "lockfiles/pins/python-base-image.json"
)

attest_subjects = out / "subjects-attest.sha256"
attest_subjects.write_text("\n".join(immutable) + "\n", encoding="utf-8")

# Full consumer subject list includes the (still-pending) binding; finalize
# script refreshes the binding line after status is sealed.
subjects_path = out / "subjects.sha256"
subjects_path.write_text(
    f"{sha256_bare(binding_path)}  ReleaseProvenanceBinding.v0.json\n"
    + "\n".join(immutable)
    + "\n",
    encoding="utf-8",
)

status_path = out / "attestation-status.json"
status_path.write_text(
    json.dumps(
        {
            "status": "pending",
            "require_signed": os.environ.get("PCS_PROVENANCE_REQUIRE_SIGNED", "0") == "1",
            "binding_path": "ReleaseProvenanceBinding.v0.json",
            "subjects_path": "subjects.sha256",
            "attest_subjects_path": "subjects-attest.sha256",
        },
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)

print(f"OK wrote {binding_path}")
print(f"OK wrote {attest_subjects} ({len(immutable)} immutable subjects)")
print(f"OK wrote {subjects_path}")
print(f"bundle.status={bundle['status']}")
PY

echo "OK release provenance subjects under ${OUT_DIR}"
