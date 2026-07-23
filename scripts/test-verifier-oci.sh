#!/usr/bin/env bash
# Clean-environment acceptance for the verifier OCI image.
# Builds docker/verifier/Dockerfile and runs capabilities + a fixture lean-check.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${PCS_VERIFIER_OCI_IMAGE:-pcs-core-verifier:ci-local}"
TAG_FILE="${PCS_VERIFIER_OCI_ID_FILE:-}"

if ! command -v docker >/dev/null 2>&1; then
  echo "FAIL: docker not on PATH (required for verifier OCI clean execution)" >&2
  exit 1
fi

cd "${ROOT}"
echo "Building verifier OCI image ${IMAGE} ..."
docker build -f docker/verifier/Dockerfile -t "${IMAGE}" .

if [ -n "${TAG_FILE}" ]; then
  docker image inspect --format '{{.Id}}' "${IMAGE}" > "${TAG_FILE}"
fi

echo "Running capabilities as non-root uid 10001 ..."
docker run --rm --user 10001:10001 "${IMAGE}" capabilities --json >/tmp/pcs-verifier-oci-caps.json
python3 - <<'PY'
import json
from pathlib import Path

caps = json.loads(Path("/tmp/pcs-verifier-oci-caps.json").read_text(encoding="utf-8"))
assert caps.get("product") == "verifier", caps
c = caps.get("capabilities") or {}
assert c.get("lean_toolchain") is True, caps
assert c.get("pf_core_kernel") is True, caps
assert c.get("pcs_envelope_kernel") is True, caps
print("OK verifier OCI capabilities")
PY

# Mount a fixture for lean-check (examples are not copied into the image).
FIXTURE_HOST="${ROOT}/examples/pf-core-valid/tool_use_trace_compiled"
test -f "${FIXTURE_HOST}/pfcore_trace.json"

echo "Running lean-check inside OCI image ..."
docker run --rm --user 10001:10001 \
  -v "${FIXTURE_HOST}:/work/fixture:ro" \
  -w /work \
  "${IMAGE}" \
  pf-core lean-check \
  --trace /work/fixture/pfcore_trace.json \
  --out /tmp/pfcore-oci-cert.json \
  --result-out /tmp/pfcore-oci-lean-check.json

echo "OK verifier OCI clean execution"
