#!/usr/bin/env bash
# PCS v0.1 release verification (Linux/macOS/Git Bash). Run from repo root.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${ROOT}/python"
FAILED=()

to_wsl_path() {
  local path="$1"
  if command -v wslpath >/dev/null 2>&1; then
    wslpath -u "${path}"
    return
  fi
  local drive letter rest
  drive="$(echo "${path}" | cut -c1 | tr 'A-Z' 'a-z')"
  rest="$(echo "${path}" | cut -c3- | tr '\\' '/')"
  printf '/mnt/%s%s' "${drive}" "${rest}"
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

cd "${PY}"
pip install -e ".[dev]" -q

step "schema check" pcs schema check
step "examples check" pcs examples check
step "hash vectors" python -m pcs_core.hash_vectors --verify
step "shared hash vectors" pcs shared-hash-vectors verify
step "labtrust release chain" pcs validate-release-chain ../examples/labtrust-release/
step "tool-use release chain" pcs validate-release-chain ../examples/tool-use-release/
step "computation release chain" pcs validate-release-chain ../examples/computation-release/
step "labtrust release manifest" pcs validate ../examples/labtrust-release/release_manifest.v0.json
step "registry validate" pcs registry validate ../examples/artifact_registry.valid.json
step "registry audit" pcs registry audit
step "benchmark validate" pcs benchmark validate
step "benchmark ingest release-grade" pcs benchmark validate-ingest --release-grade
step "validate benchmark ingest script" python ../scripts/validate_benchmark_ingest_examples.py --release-grade
step "conformance benchmark-ingest" pcs conformance run --suite benchmark-ingest
step "conformance benchmark-report" pcs conformance run --suite benchmark-report
step "conformance benchmark" pcs conformance run --suite benchmark
step "conformance computation" pcs conformance run --suite computation
step "conformance multidomain" pcs conformance run --suite multidomain
step "conformance all" pcs conformance run --suite all
step "labtrust conformance pytest" pytest -q tests/test_labtrust_conformance.py
step "multidomain pytest" pytest -q tests/test_multidomain_workflows.py
step "pytest" pytest -q
step "pytest protocol" pytest -q tests/test_protocol_conformance.py tests/test_benchmark_ingest_contract.py tests/test_release_chain.py
step "pf-core valid fixtures" pcs pf-core validate-trace ../examples/pf-core-valid/tool_use_trace_compiled/pfcore_trace.json
step "pf-core lean no-sorry audit" pcs pf-core audit-lean-no-sorry
step "pf-core pytest" pytest -q tests/test_pf_core_*.py

PF_CORE_TRACE="${ROOT}/examples/pf-core-valid/tool_use_trace_compiled/pfcore_trace.json"
PF_CORE_CERT="/tmp/pfcore-lean-check-cert.json"
step "pf-core lean-check canonical trace" pcs pf-core lean-check --trace "${PF_CORE_TRACE}" --out "${PF_CORE_CERT}" --skip-build
if [[ -f "${PF_CORE_CERT}" ]]; then
  step "pf-core lean-check certificate validate" pcs validate "${PF_CORE_CERT}"
else
  echo "SKIP pf-core lean-check certificate validate (certificate not emitted with --skip-build)"
fi

if command -v wsl >/dev/null 2>&1; then
  step "lake build PCS" wsl bash -lc "cd '${WSL_ROOT}/lean' && lake build PCS"
  step "lake build PFCore" wsl bash -lc "cd '${WSL_ROOT}/lean' && lake build PFCore"
  step "pf-core lean-check full" wsl bash -lc "cd '${WSL_ROOT}/python' && pcs pf-core lean-check --trace '${WSL_ROOT}/examples/pf-core-valid/tool_use_trace_compiled/pfcore_trace.json' --out /tmp/pfcore-full-cert.json"
  step "pf-core lean-check full certificate validate" wsl bash -lc "test -f /tmp/pfcore-full-cert.json && cd '${WSL_ROOT}/python' && pcs validate /tmp/pfcore-full-cert.json"
elif command -v lake >/dev/null 2>&1; then
  step "lake build PCS" bash -lc "cd ../lean && lake build PCS"
  step "lake build PFCore" bash -lc "cd ../lean && lake build PFCore"
  step "pf-core lean-check full" pcs pf-core lean-check --trace "${PF_CORE_TRACE}" --out /tmp/pfcore-full-cert.json
  if [[ -f /tmp/pfcore-full-cert.json ]]; then
    step "pf-core lean-check full certificate validate" pcs validate /tmp/pfcore-full-cert.json
  fi
else
  echo "SKIP lake build (lake and wsl unavailable)"
fi

step "pf-core conformance" pcs conformance run --suite pf-core
step "pf-core cross-language conformance" pcs conformance run --suite pf-core-cross-language

for suite in \
  labtrust-qc-release-v0 \
  tool-use-safety-v0 \
  computation-reproducibility-v0 \
  scientific-memory-rendering-v0 \
  formal-trust-kernel-v0 \
  cross-domain-release-chain-v0; do
  step "benchmark run ${suite}" pcs benchmark run --suite "${suite}"
done

step "materialize benchmark examples" python scripts/materialize_benchmark_examples.py
step "materialize benchmark ingest" python scripts/materialize_benchmark_producer_examples.py
step "ruff check" ruff check pcs_core tests
step "ruff format" ruff format --check pcs_core tests

cd "${ROOT}/rust"
step "rust test" cargo test -q
step "rust shared hash vectors" cargo test shared_hash_vectors -q
step "rust fmt" cargo fmt --check
step "rust clippy" cargo clippy --all-targets -- -D warnings

cd "${ROOT}/typescript"
npm install --silent
step "typescript test" npm test --silent
step "typescript hash vectors" npm run test:hash-vectors -w @pcs/core --silent

cd "${ROOT}"
if [[ -x "${ROOT}/scripts/pcs-schema-diff.sh" ]]; then
  step "pcs schema diff" bash scripts/pcs-schema-diff.sh schemas
else
  echo "SKIP pcs schema diff (script missing)"
fi

echo ""
echo "=== Summary ==="
if [[ ${#FAILED[@]} -eq 0 ]]; then
  echo "All steps passed."
  exit 0
fi
echo "Failed: ${FAILED[*]}"
exit 1
