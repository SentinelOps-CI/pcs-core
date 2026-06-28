#!/usr/bin/env bash
# PF-Core release-grade local verification (no git). Run from repository root.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${ROOT}/python"
TRACE="${ROOT}/examples/pf-core-valid/tool_use_trace_compiled/pfcore_trace.json"
FAILED=()

to_wsl_path() {
  local path="$1"
  if command -v wslpath >/dev/null 2>&1; then
    wslpath -u "${path}"
    return
  fi
  if [[ "${path}" =~ ^[A-Za-z]: ]]; then
    local drive letter rest
    drive="$(echo "${path}" | cut -c1 | tr 'A-Z' 'a-z')"
    rest="$(echo "${path}" | cut -c3- | tr '\\' '/')"
    printf '/mnt/%s%s' "${drive}" "${rest}"
    return
  fi
  printf '%s' "${path}"
}

WSL_ROOT="$(to_wsl_path "${ROOT}")"

step() {
  local name="$1"
  shift
  echo ""
  echo "=== ${name} ==="
  if (cd "${PY}" && "$@"); then
    echo "OK ${name}"
  else
    echo "FAIL ${name}"
    FAILED+=("${name}")
  fi
}

lake_available() {
  command -v lake >/dev/null 2>&1
}

wsl_lake_available() {
  command -v wsl >/dev/null 2>&1
}

cd "${PY}"
pip install -e ".[dev]" -q

step "pf-core all pytest" pytest -q tests/test_pf_core_*.py
step "pf-core certificate-mode codegen pytest" pytest -q tests/test_pf_core_certificate_mode_codegen.py
step "pf-core catalog tool_map pytest" pytest -q tests/test_pf_core_catalog_tool_map.py
step "pf-core conformance release-grade" pcs conformance run --suite pf-core --release-grade
step "pf-core cross-language conformance" pcs conformance run --suite pf-core-cross-language

step "PF-Core catalog drift check" bash -lc "
  cd '${PY}' &&
  python scripts/gen_pf_core_catalog.py &&
  git diff --exit-code \
    '${ROOT}/python/pcs_core/pf_core_catalog.py' \
    '${ROOT}/lean/PFCore/Catalog.lean' \
    '${ROOT}/rust/crates/pcs-core/src/pf_core_catalog.rs' \
    '${ROOT}/typescript/packages/core/src/pfCoreCatalog.ts'
"

step "pf-core audit-lean-no-sorry" pcs pf-core audit-lean-no-sorry

PF_CORE_RELEASE_CERT="$(mktemp /tmp/pfcore-release-grade-cert.XXXXXX.json 2>/dev/null || echo /tmp/pfcore-release-grade-cert.json)"
BUNDLE_DIR="$(mktemp -d /tmp/pfcore-release-grade-bundle.XXXXXX 2>/dev/null || echo /tmp/pfcore-release-grade-bundle)"

echo ""
echo "=== PF-Core LeanKernelChecked path (when lake/WSL available) ==="
if lake_available; then
  step "lake build PFCore" bash -lc "cd '${ROOT}/lean' && lake build PFCore"
  step "lake build PCS" bash -lc "cd '${ROOT}/lean' && lake build PCS"
  step "pf-core lean-check full (TraceSafeRCertificate default)" \
    pcs pf-core lean-check --trace "${TRACE}" --out "${PF_CORE_RELEASE_CERT}"
  if [[ -f "${PF_CORE_RELEASE_CERT}" ]]; then
    step "verify TraceSafeRCertificate + substantive proof" python3 - "${PF_CORE_RELEASE_CERT}" "${ROOT}" <<'PY'
import json
import re
import sys
from pathlib import Path

cert_path = Path(sys.argv[1])
root = Path(sys.argv[2])
cert = json.loads(cert_path.read_text(encoding="utf-8"))
if cert.get("certificate_mode") != "TraceSafeRCertificate":
    raise SystemExit(f"expected TraceSafeRCertificate, got {cert.get('certificate_mode')!r}")
proof_ref = cert.get("proof_term_ref")
if not proof_ref:
    raise SystemExit("certificate missing proof_term_ref")
proof_path = root / str(proof_ref).replace("\\", "/")
text = proof_path.read_text(encoding="utf-8")
if re.search(r":\s*True\s*:=\s*trivial", text):
    raise SystemExit(f"trivial aggregate in generated proof: {proof_path}")
obligations = cert.get("obligations") or []
if not any(item.get("theorem") == "concrete_trace_safe_r" for item in obligations if isinstance(item, dict)):
    raise SystemExit("certificate missing concrete_trace_safe_r obligation")
print("OK TraceSafeRCertificate substantive proof")
PY
    step "pf-core verify-proof-binding" pcs pf-core verify-proof-binding \
      --certificate "${PF_CORE_RELEASE_CERT}" --trace "${TRACE}"
    step "pf-core bundle-release" pcs pf-core bundle-release \
      --trace "${TRACE}" --cert "${PF_CORE_RELEASE_CERT}" --out "${BUNDLE_DIR}"
    step "pf-core validate-bundle (kernel manifest + hashes)" bash -lc "
      pcs pf-core validate-bundle '${BUNDLE_DIR}' &&
      python3 - <<'PY'
import json
from pathlib import Path
manifest = json.loads(Path('${BUNDLE_DIR}/manifest.json').read_text(encoding='utf-8'))
if manifest.get('certificate_mode') != 'TraceSafeRCertificate':
    raise SystemExit('bundle manifest certificate_mode not TraceSafeRCertificate')
if not Path('${BUNDLE_DIR}/kernel_manifest.json').is_file():
    raise SystemExit('bundle missing kernel_manifest.json')
print('OK bundle kernel manifest')
PY
    "
  else
    echo "FAIL pf-core verify-proof-binding (certificate missing)"
    FAILED+=("pf-core verify-proof-binding")
  fi
elif wsl_lake_available; then
  echo "NOTE: native lake unavailable; attempting WSL (may timeout on some Windows hosts)"
  step "lake build PFCore (WSL)" wsl bash -lc "export PATH=\"\$HOME/.elan/bin:\$PATH\"; cd '${WSL_ROOT}/lean' && lake build PFCore"
  step "lake build PCS (WSL)" wsl bash -lc "export PATH=\"\$HOME/.elan/bin:\$PATH\"; cd '${WSL_ROOT}/lean' && lake build PCS"
  step "pf-core lean-check full (WSL)" wsl bash -lc "cd '${WSL_ROOT}/python' && pcs pf-core lean-check --trace '${WSL_ROOT}/examples/pf-core-valid/tool_use_trace_compiled/pfcore_trace.json' --out /tmp/pfcore-release-grade-cert.json"
  step "pf-core verify-proof-binding (WSL)" wsl bash -lc "cd '${WSL_ROOT}/python' && test -f /tmp/pfcore-release-grade-cert.json && pcs pf-core verify-proof-binding --certificate /tmp/pfcore-release-grade-cert.json --trace '${WSL_ROOT}/examples/pf-core-valid/tool_use_trace_compiled/pfcore_trace.json'"
else
  echo "SKIP Lean path: neither lake nor wsl available (conformance --release-grade may have already failed closed)"
  FAILED+=("PF-Core Lean path (lake/WSL unavailable)")
fi

cd "${ROOT}/rust"
step "rust pf_core tests" cargo test pf_core -q

echo ""
echo "=== CertifyEdge release-gate matrix (mock + stub) ==="
if bash "${ROOT}/scripts/pf-core-certifyedge-dry-run.sh"; then
  echo "OK CertifyEdge mock dry-run"
else
  echo "FAIL CertifyEdge mock dry-run"
  FAILED+=("CertifyEdge mock dry-run")
fi

if bash "${ROOT}/scripts/pf-core-certifyedge-stub-dry-run.sh"; then
  echo "OK CertifyEdge stub dry-run"
else
  echo "FAIL CertifyEdge stub dry-run"
  FAILED+=("CertifyEdge stub dry-run")
fi

echo ""
echo "=== Summary ==="
if [[ ${#FAILED[@]} -eq 0 ]]; then
  echo "All PF-Core release-grade local steps passed."
  exit 0
fi
echo "Failed: ${FAILED[*]}"
exit 1
