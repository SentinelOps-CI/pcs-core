#!/usr/bin/env bash
# Clean-environment acceptance for the default validator wheel.
# Schema + semantic validation succeed; Lean capabilities report unavailable.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/pcs-validator-wheel.XXXXXX")"
cleanup() { rm -rf "${WORK}"; }
trap cleanup EXIT

cd "${ROOT}/python"
pip install --upgrade build >/dev/null
rm -rf dist
python -m build --wheel
WHEEL="$(ls -1 dist/pcs_core-*.whl | head -n1)"
test -n "${WHEEL}"

python -m venv "${WORK}/venv"
# shellcheck disable=SC1091
source "${WORK}/venv/bin/activate"
pip install --upgrade pip >/dev/null
pip install -c "${ROOT}/python/requirements.lock" "${ROOT}/python/${WHEEL}"

# Ensure the checkout is not on PYTHONPATH.
unset PYTHONPATH
cd "${WORK}"

pcs capabilities --json > "${WORK}/caps.json"
python3 - <<'PY'
import json, pathlib, sys
caps = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
assert caps["product"] == "validator", caps
c = caps["capabilities"]
assert c["schema_validation"] is True
assert c["lean_toolchain"] is False
assert c["pf_core_kernel"] is False
assert c["pcs_envelope_kernel"] is False
print("OK validator capabilities report Lean unavailable")
PY
"${WORK}/caps.json"

# Copy fixtures into the clean env (wheel does not ship examples/).
mkdir -p "${WORK}/fixtures"
cp "${ROOT}/examples/science_claim_bundle.certified.valid.json" "${WORK}/fixtures/"
cp "${ROOT}/examples/tool_use_trace.valid.json" "${WORK}/fixtures/"
cp -R "${ROOT}/examples/labtrust-release" "${WORK}/fixtures/labtrust-release"

pcs validate "${WORK}/fixtures/science_claim_bundle.certified.valid.json"
pcs validate "${WORK}/fixtures/tool_use_trace.valid.json"
pcs validate-release-chain "${WORK}/fixtures/labtrust-release/"
echo "OK validator wheel clean-environment checks"
