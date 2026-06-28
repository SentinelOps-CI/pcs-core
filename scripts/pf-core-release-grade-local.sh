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

step "pf-core cross-language pytest" pytest -q tests/test_pf_core_cross_language.py
step "pf-core tier1 pytest" pytest -q tests/test_pf_core_tier1.py
step "pf-core compositional pytest" pytest -q tests/test_pf_core_compositional.py
step "pf-core research pytest" pytest -q tests/test_pf_core_research.py tests/test_pf_core_research_grade.py
step "pf-core conformance release-grade" pcs conformance run --suite pf-core --release-grade
step "pf-core cross-language conformance" pcs conformance run --suite pf-core-cross-language

PF_CORE_RELEASE_CERT="$(mktemp /tmp/pfcore-release-grade-cert.XXXXXX.json 2>/dev/null || echo /tmp/pfcore-release-grade-cert.json)"

echo ""
echo "=== PF-Core LeanKernelChecked path (when lake/WSL available) ==="
if lake_available; then
  step "lake build PFCore" bash -lc "cd '${ROOT}/lean' && lake build PFCore"
  step "pf-core lean-check full" pcs pf-core lean-check --trace "${TRACE}" --out "${PF_CORE_RELEASE_CERT}"
  if [[ -f "${PF_CORE_RELEASE_CERT}" ]]; then
    step "pf-core verify-proof-binding" pcs pf-core verify-proof-binding \
      --certificate "${PF_CORE_RELEASE_CERT}" --trace "${TRACE}"
  else
    echo "FAIL pf-core verify-proof-binding (certificate missing)"
    FAILED+=("pf-core verify-proof-binding")
  fi
elif wsl_lake_available; then
  step "lake build PFCore (WSL)" wsl bash -lc "export PATH=\"\$HOME/.elan/bin:\$PATH\"; cd '${WSL_ROOT}/lean' && lake build PFCore"
  step "pf-core lean-check full (WSL)" wsl bash -lc "cd '${WSL_ROOT}/python' && pcs pf-core lean-check --trace '${WSL_ROOT}/examples/pf-core-valid/tool_use_trace_compiled/pfcore_trace.json' --out /tmp/pfcore-release-grade-cert.json"
  step "pf-core verify-proof-binding (WSL)" wsl bash -lc "cd '${WSL_ROOT}/python' && test -f /tmp/pfcore-release-grade-cert.json && pcs pf-core verify-proof-binding --certificate /tmp/pfcore-release-grade-cert.json --trace '${WSL_ROOT}/examples/pf-core-valid/tool_use_trace_compiled/pfcore_trace.json'"
else
  echo "SKIP Lean path: neither lake nor wsl available (conformance --release-grade may have already failed closed)"
  FAILED+=("PF-Core Lean path (lake/WSL unavailable)")
fi

cd "${ROOT}/rust"
step "rust pf_core tests" cargo test pf_core -q

echo ""
echo "=== Summary ==="
if [[ ${#FAILED[@]} -eq 0 ]]; then
  echo "All PF-Core release-grade local steps passed."
  exit 0
fi
echo "Failed: ${FAILED[*]}"
exit 1
