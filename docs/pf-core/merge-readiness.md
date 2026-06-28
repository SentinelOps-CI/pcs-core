# PF-Core merge readiness (PR #5)

Local preparation checklist for merging `phase7/shared-hash-vector-ci` into main. **No git operations** are performed by this document; it records verification steps only.

## PR #5 status

| Item | Status |
|------|--------|
| Branch | `main` (local HEAD `9c9d290`; uncommitted PF-Core catalog + cert-mode parity) |
| CI on PR #5 | Green (prior); re-verify after local changes |
| Shared hash vectors | Python / Rust / TypeScript parity |
| Lean kernel | `lake build PFCore` in CI lean job |
| Cross-language conformance | `pf-core-cross-language` suite |
| Single-source catalog wiring (Rust/TS) | Done (uncommitted): `pf_core_catalog.rs`, `pfCoreCatalog.ts` consumers |
| Certificate-mode parity (six modes) | Done (uncommitted): lean-check `--certificate-mode`, fixtures, cross-language tests |
| `contract_semantics_checked` Rust/TS parity | Done (uncommitted): validation helpers + cross-language tests; no LeanKernelChecked from Rust/TS alone |
| Resource scope certificate obligations | Done (uncommitted): `resource_pattern_scope` + `resource_within_capability_pattern` when `lean_proof_checked` |
| CertifyEdge dry-run scripts | Done (uncommitted): `scripts/pf-core-certifyedge-dry-run.{ps1,sh}` |

## Pre-merge local verification

Run from repository root:

```bash
pip install -e python
cd python && pytest -q tests/test_pf_core_*.py
cd ../rust && cargo test pf_core
# Windows native (lake on PATH):
powershell -File scripts/pf-core-release-grade-local.ps1
# Linux/macOS or Git Bash:
export PF_CORE_CERTIFYEDGE_MODE=mock
bash scripts/pf-core-release-grade-local.sh

# CertifyEdge release-gate dry-run only (mock):
powershell -File scripts/pf-core-certifyedge-dry-run.ps1
# bash scripts/pf-core-certifyedge-dry-run.sh
```

On Windows without native `lake`, use WSL for Lean steps (see `docs/pf-core/windows-lean.md`) or rely on CI lean job.

### Local verification log (2026-06-28, Windows native — session 2)

| Step | Result |
|------|--------|
| `cargo test pf_core` | OK (16 passed) |
| TypeScript `@pcs/core` tests | OK (26 passed; Windows `node --test dist/tests/`) |
| PF-Core pytest (`-k pf_core`) | OK (262 passed, 2 skipped) |
| `pcs conformance run --suite pf-core-cross-language` | OK |
| `pcs conformance run --suite pf-core --release-grade` | OK |
| `audit_lean_catalog()` | OK |
| `scripts/pf-core-certifyedge-dry-run.ps1` | OK (mock mode) |
| `contract_semantics_checked` Rust/TS/Python parity tests | OK |

Prior session (HEAD `9c9d290` baseline): lake build, lean-check, verify-proof-binding, bundle-release, release-grade PS1 — see rows below when re-run.

### Local verification log (2026-06-28, Windows native — prior)

| Step | Result |
|------|--------|
| `lake build PFCore` | OK (native `lake` 5.0.0 / Lean 4.14.0) |
| `pcs pf-core lean-check` on `examples/pf-core-valid/tool_use_trace_compiled/pfcore_trace.json` | OK (`LeanKernelChecked`) |
| `pcs pf-core verify-proof-binding` | OK |
| `pcs pf-core bundle-release` + `validate-bundle` | OK |
| `pcs conformance run --suite pf-core --release-grade` | OK |
| `pcs conformance run --suite pf-core-cross-language` | OK (after TS `npm test` glob fix) |
| PF-Core pytest suites (cross-language, tier1, compositional, research) | OK (106 passed, 1 skipped) |
| `cargo test pf_core` | OK (14 passed) |
| `scripts/pf-core-release-grade-local.sh` via WSL | BLOCKED (WSL `CreateInstance` connection timeout) |
| `scripts/pf-core-release-grade-local.ps1` (native) | Use when `lake` on PATH; avoids WSL |

**Windows npm test:** `node --test dist/tests/*.test.js` does not expand globs in npm on Windows; use `node --test dist/tests/` in `typescript/packages/core/package.json` (fixed locally).


## Post-merge verification

1. Pull main and confirm CI green on default branch.
2. Re-run `pcs conformance run --suite pf-core --release-grade` (fail closed without lake).
3. Re-run `pcs pf-core verify-proof-binding` on a fresh `lean-check` certificate from `examples/pf-core-valid/tool_use_trace_compiled/pfcore_trace.json`.
4. Confirm `pcs pf-core audit-lean-no-sorry` passes on `lean/PFCore/` including `Observational.lean` and `ResourcePattern.lean`.
5. Run `pcs examples check` for valid/invalid PF-Core fixtures.

## Claim boundaries for v0.1 release announcement

**May state:**

- PF-Core trace safety (`TraceSafe`, `EventSafe`) with concrete Lean proof terms on the `LeanKernelChecked` path.
- Conservative tenant isolation for **allowed events in safe traces** (`TenantIsolation`, `TraceCrossTenantSafe`).
- Observational tenant projection vocabulary (`Observational.lean`) without covert-channel claims.
- Runtime resource-pattern scope validation (`resource_pattern_scope` in certificates).
- Compositional trust lemmas (safe extension, handoff authority bounds, contract refinement).
- Proof binding via `trace_hash`, `proof_term_hash`, `lean_environment_hash`.

**Must not state:**

- Full global cross-tenant non-interference or absence of covert channels.
- Lean discharge of capability `resource_pattern` matching (runtime-only; see `claim-boundary.md`).
- PCS envelope checks (`ProofChecked`) as PF-Core `LeanKernelChecked` trace safety.
- Full JSON contract discharge for role, policy, and evidence fields (runtime `semantics_layer`).
- CertifyEdge live attestation unless the external CLI is installed and configured.

Reference: `docs/pf-core/claim-boundary.md`, `docs/pf-core/non-interference.md`, `docs/pf-core/current-gap-audit.md`.

## Open after merge (research, not blockers)

- Full global non-interference under adversarial schedulers.
- Lean kernel discharge of resource-pattern scope.
- PCS per-obligation Lean term generation (see `docs/pf-core/pcs-envelope-lean-roadmap.md`).
- Live provability-fabric-core adapter orchestration beyond hash parity CI.
- Reliable WSL on this host for duplicate Lean path (native lake suffices when installed).
