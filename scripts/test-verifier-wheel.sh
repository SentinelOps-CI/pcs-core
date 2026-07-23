#!/usr/bin/env bash
# Clean-environment acceptance for the verifier wheel (Lean assets embedded).
# Requires lake on PATH (install via scripts/install-elan-verified.sh).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if ! command -v lake >/dev/null 2>&1; then
  echo "FAIL: lake not on PATH; install pinned elan first" >&2
  exit 1
fi

WORK="$(mktemp -d "${TMPDIR:-/tmp}/pcs-verifier-wheel.XXXXXX")"
cleanup() { rm -rf "${WORK}"; }
trap cleanup EXIT

bash "${ROOT}/scripts/build-verifier-wheel.sh"
WHEEL="$(ls -1 "${ROOT}/python/dist"/pcs_core-*.whl | head -n1)"
test -n "${WHEEL}"

python3 -m venv "${WORK}/venv"
# shellcheck disable=SC1091
source "${WORK}/venv/bin/activate"
pip install --upgrade pip >/dev/null
pip install -c "${ROOT}/python/requirements.lock" "${WHEEL}"

unset PYTHONPATH
cd "${WORK}"

# Copy fixtures needed for lean-check / bundle (examples are not in the wheel).
mkdir -p "${WORK}/fixtures"
cp -R "${ROOT}/examples/pf-core-valid/tool_use_trace_compiled" "${WORK}/fixtures/tool_use"

python3 - <<'PY'
from pcs_core.asset_resolver import lean_root, pins_dir, resolver_report
from pcs_core.pf_core_lean_codegen import (
    compute_lean_environment_hash,
    compute_pfcore_kernel_hash,
)

report = resolver_report()
assert report["lean_project_present"] is True, report
assert report["pf_core_kernel_present"] is True, report
assert report["pcs_kernel_present"] is True, report
assert lean_root() is not None
assert pins_dir() is not None

kernel = compute_pfcore_kernel_hash()
env = compute_lean_environment_hash()
assert kernel.startswith("sha256:") and len(kernel) > 16, kernel
assert env.startswith("sha256:") and len(env) > 16, env
assert kernel != "sha256:" + ("0" * 64)
print(f"OK bundled assets kernel={kernel[:18]}… env={env[:18]}…")
PY

pcs capabilities --json > "${WORK}/caps.json"
python3 - <<'PY'
import json, pathlib, sys
caps = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
assert caps["product"] == "verifier", caps
c = caps["capabilities"]
assert c["lean_toolchain"] is True
assert c["pf_core_kernel"] is True
assert c["pcs_envelope_kernel"] is True
print("OK verifier capabilities")
PY
"${WORK}/caps.json"

# Pre-build kernels once so lean-check does not rebuild from a missing lake-packages tree.
(
  cd "$(python3 -c 'from pcs_core.asset_resolver import require_lean_root; print(require_lean_root())')"
  lake build PCS
  lake build PFCore
)

pcs pf-core lean-check \
  --trace "${WORK}/fixtures/tool_use/pfcore_trace.json" \
  --out "${WORK}/cert.json" \
  --result-out "${WORK}/lean_check_result.json"

pcs pf-core bundle-release \
  --trace "${WORK}/fixtures/tool_use/pfcore_trace.json" \
  --cert "${WORK}/cert.json" \
  --lean-check-result "${WORK}/lean_check_result.json" \
  --out "${WORK}/bundle"

pcs pf-core verify-bundle "${WORK}/bundle"
echo "OK verifier wheel clean-environment checks"
