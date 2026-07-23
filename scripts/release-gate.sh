#!/usr/bin/env bash
# Unified PCS / PF-Core release gate (preview vs release).
# Does not push tags or publish GitHub Releases.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

MODE="${PCS_RELEASE_MODE:-preview}"
PROPERTY_ID="${PCS_EXTERNAL_ATTESTATION_PROPERTY:-qc_release.temporal.safety}"
BUNDLE_OUT="${PCS_RELEASE_BUNDLE_DIR:-${ROOT}/dist/release-bundle}"
SKIP_LEAN="${PCS_RELEASE_SKIP_LEAN:-0}"
SKIP_RUST="${PCS_RELEASE_SKIP_RUST:-0}"
SKIP_TS="${PCS_RELEASE_SKIP_TS:-0}"

echo "== PCS release gate mode=${MODE} =="

python3 "${ROOT}/scripts/verify-certifyedge-pin.py" --mode "${MODE}"

# Provision CertifyEdge when pin is ready (no-op when unpinned in preview).
bash "${ROOT}/scripts/provision-certifyedge.sh" || {
  if [[ "${MODE}" == "release" ]]; then
    exit 1
  fi
  echo "WARN: CertifyEdge provision skipped/failed in ${MODE} mode"
}

# Prefer provisioned binary when present.
if [[ -x "${ROOT}/.tools/certifyedge/certifyedge" ]]; then
  export PF_CORE_CERTIFYEDGE_CLI="${ROOT}/.tools/certifyedge/certifyedge"
fi

cd "${ROOT}/python"
pip install -c requirements.lock -e ".[dev,quality]" >/dev/null
pcs capabilities

echo "== Gate: org/infra release gates =="
pcs release check-gates --mode "${MODE}"

echo "== Gate: quality (Python) =="
ruff check pcs_core tests
ruff format --check pcs_core tests
if command -v pyright >/dev/null 2>&1; then
  pyright pcs_core || true  # advisory until fully typed; CI job enforces separately
fi
pytest -q
pytest -q tests/test_property_based.py tests/test_external_attestation.py

echo "== Gate: schema / catalog / claims =="
pcs schema check
pcs pf-core audit-claims
pcs pf-core audit-boundary
pcs pf-core audit-lean-catalog
pcs pf-core audit-lean-no-sorry
python scripts/gen_pf_core_catalog.py
git -C "${ROOT}" diff --exit-code \
  python/pcs_core/pf_core_catalog.py \
  lean/PFCore/Catalog.lean \
  rust/crates/pcs-core/src/pf_core_catalog.rs \
  typescript/packages/core/src/pfCoreCatalog.ts

echo "== Gate: release chains + adversarial fixtures =="
pcs examples check
pcs validate-release-chain ../examples/labtrust-release/
pcs validate-release-chain ../examples/tool-use-release/
pcs validate-release-chain ../examples/computation-release/
pcs conformance run --suite all
python -m pcs_core.hash_vectors --verify
pcs shared-hash-vectors verify

if [[ "${SKIP_RUST}" != "1" ]]; then
  echo "== Gate: Rust =="
  (cd "${ROOT}/rust" && cargo fmt --check && cargo clippy --locked --all-targets -- -D warnings && cargo test --locked)
fi

if [[ "${SKIP_TS}" != "1" ]]; then
  echo "== Gate: TypeScript =="
  (cd "${ROOT}/typescript" && npm ci && npm run lint && npm test)
fi

if [[ "${SKIP_LEAN}" != "1" ]]; then
  echo "== Gate: Lean kernels + generated proofs =="
  export PATH="${HOME}/.elan/bin:${PATH}"
  if ! command -v lake >/dev/null 2>&1; then
    if [[ "${MODE}" == "release" ]]; then
      echo "FAIL: lake required for release mode" >&2
      exit 1
    fi
    echo "WARN: lake absent; skipping Lean gates in ${MODE} mode"
  else
    (cd "${ROOT}/lean" && lake build PCS && lake build PFCore)
    pcs pf-core lean-check \
      --trace ../examples/pf-core-valid/tool_use_trace_compiled/pfcore_trace.json \
      --out /tmp/pfcore-release-cert.json \
      --result-out /tmp/pfcore-release-lean-check.json
    pcs pf-core verify-proof-binding \
      --certificate /tmp/pfcore-release-cert.json \
      --trace ../examples/pf-core-valid/tool_use_trace_compiled/pfcore_trace.json
    pcs conformance run --suite pf-core --release-grade
  fi
fi

echo "== Gate: SBOM scaffold =="
bash "${ROOT}/scripts/generate-sbom.sh" "${ROOT}/dist/sbom"
test -f "${ROOT}/dist/sbom/pcs-core.cdx.json"

echo "== Gate: assemble release bundle + external attestation =="
rm -rf "${BUNDLE_OUT}"
mkdir -p "${BUNDLE_OUT}"
# Prefer a lean-checked certificate when available; otherwise mock certificate for preview assembly.
CERT_PATH="/tmp/pfcore-release-cert.json"
LEAN_CHECK_RESULT="/tmp/pfcore-release-lean-check.json"
if [[ ! -f "${CERT_PATH}" ]]; then
  PF_CORE_CERTIFYEDGE_MODE=mock pcs pf-core certifyedge-check \
    --trace ../examples/pf-core-valid/labtrust_replay/trace.json \
    --property "${PROPERTY_ID}" \
    --out /tmp/pfcore-preview-cert.json
  CERT_PATH="/tmp/pfcore-preview-cert.json"
  TRACE_PATH="../examples/pf-core-valid/labtrust_replay/trace.json"
  LEAN_CHECK_RESULT=""
else
  TRACE_PATH="../examples/pf-core-valid/tool_use_trace_compiled/pfcore_trace.json"
fi
BUNDLE_ARGS=(--trace "${TRACE_PATH}" --cert "${CERT_PATH}" --out "${BUNDLE_OUT}")
if [[ -n "${LEAN_CHECK_RESULT}" && -f "${LEAN_CHECK_RESULT}" ]]; then
  BUNDLE_ARGS+=(--lean-check-result "${LEAN_CHECK_RESULT}")
fi
pcs pf-core bundle-release "${BUNDLE_ARGS[@]}"
pcs pf-core validate-bundle "${BUNDLE_OUT}"

if [[ "${MODE}" == "release" ]]; then
  export PF_CORE_CERTIFYEDGE_REQUIRE_LIVE=1
  export PF_CORE_CERTIFYEDGE_MODE=live
  pcs pf-core attest-bundle --bundle "${BUNDLE_OUT}" --property "${PROPERTY_ID}" --require-live
  pcs pf-core validate-external-attestation --bundle "${BUNDLE_OUT}" --require-live
  pcs pf-core validate-bundle "${BUNDLE_OUT}"
  echo "OK release mode: live external attestation bound to bundle"
else
  # Preview: attempt attestation; on failure write explicit absence notice.
  pcs pf-core attest-bundle --bundle "${BUNDLE_OUT}" --property "${PROPERTY_ID}" --allow-absence || true
  pcs pf-core validate-external-attestation --bundle "${BUNDLE_OUT}" --allow-absence
  echo "OK preview mode: external attestation present or absence notice recorded"
fi

echo "== Gate: release provenance binding (local gated; CI signs) =="
PCS_PROVENANCE_BUILD_SBOM=0 \
PCS_PROVENANCE_SBOM_DIR="${ROOT}/dist/sbom" \
PCS_PROVENANCE_BUNDLE_DIR="${BUNDLE_OUT}" \
  bash "${ROOT}/scripts/build-release-provenance.sh" "${ROOT}/dist/provenance"
test -f "${ROOT}/dist/provenance/ReleaseProvenanceBinding.v0.json"
bash "${ROOT}/scripts/finalize-provenance-attestation.sh" "${ROOT}/dist/provenance" gated \
  "local release-gate.sh cannot mint GitHub Sigstore attestations; CI release-provenance.yml does"
PCS_PROVENANCE_REQUIRE_SIGNED=0 \
  bash "${ROOT}/scripts/verify-release-provenance.sh" "${ROOT}/dist/provenance"

echo "== Gate: signed tag policy (document only; do not push) =="
echo "Documented: create an annotated GPG/SSH-signed tag matching VERSION after gates pass."
echo "This script does not create or push tags."

cat > "${ROOT}/dist/release-gate-report.json" <<EOF
{
  "schema_version": "v0",
  "artifact_type": "ReleaseGateReport.v0",
  "release_mode": "${MODE}",
  "bundle_dir": "${BUNDLE_OUT}",
  "external_attestation_required": $([ "${MODE}" = "release" ] && echo true || echo false),
  "status": "passed"
}
EOF

echo "OK unified release gate passed (mode=${MODE})"
