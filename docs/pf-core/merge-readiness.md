# PF-Core merge readiness (PR #5)

Local preparation checklist for merging `phase7/shared-hash-vector-ci` into main. **No git operations** are performed by this document; it records verification steps only.

## PR #5 status

| Item | Status |
|------|--------|
| Branch | `phase7/shared-hash-vector-ci` (HEAD ~ `12fb29b`) |
| CI on PR #5 | Green |
| Shared hash vectors | Python / Rust / TypeScript parity |
| Lean kernel | `lake build PFCore` in CI lean job |
| Cross-language conformance | `pf-core-cross-language` suite |

## Pre-merge local verification

Run from repository root:

```bash
pip install -e python
cd python && pytest -q tests/test_pf_core_*.py
cd ../rust && cargo test pf_core
bash scripts/pf-core-release-grade-local.sh   # full release-grade path when lake/WSL available
```

On Windows without native `lake`, use WSL for Lean steps (see `docs/pf-core/windows-lean.md`).

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
