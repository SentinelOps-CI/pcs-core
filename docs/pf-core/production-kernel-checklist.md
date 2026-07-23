# PF-Core production kernel — external auditor sign-off

One-page verification checklist for Tier 1 PF-Core production kernel readiness in `pcs-core`. Run from repository root unless noted.

## Scope

This checklist covers the **production trusted kernel** only: contract semantics, cross-language validation parity, PCS release-envelope separation (choice B), compositional trust lemmas, and integration hooks. It does **not** claim full global non-interference or complete Lean RoleMap/runtime catalog parity (partial RoleMap in `RoleMap.lean`).

## Evidence commands

| Check | Command | Expected |
|-------|---------|----------|
| Tier 1 semantics + envelope | `cd python && pytest -q tests/test_pf_core_tier1.py` | All pass |
| Compositional + proof binding | `cd python && pytest -q tests/test_pf_core_compositional.py` | All pass |
| Cross-language parity | `cd python && pytest -q tests/test_pf_core_cross_language.py` | All pass (TS may skip if `node` absent) |
| Cross-language conformance | `pcs conformance run --suite pf-core-cross-language` | Python vectors + Rust/TS tests pass |
| Generated lean proof | `pcs conformance run --suite pf-core` | Includes `pf-core.generated-lean-proof` when `lake` available |
| Full PF-Core suite | `cd python && pytest -q tests/ -k test_pf_core` | All pass |
| Rust PF-Core vectors | `cd rust && cargo test pf_core` | All pass |
| TypeScript hash vectors | `cd typescript/packages/core && npx tsc && node --test dist/tests/examples.test.js` | All pass |
| PCS envelope path | `pcs pcs-envelope check --obligations examples/proof_obligation.valid.json --out /tmp/envelope.json --skip-lean-build` | No `LeanKernelChecked` in output |
| Lean kernel (optional) | `cd lean && lake build PFCore && pcs pf-core lean-check --trace examples/pf-core-valid/tool_use_trace_compiled/pfcore_trace.json` | `LeanKernelChecked` when full pipeline succeeds |
| Proof binding (optional) | `pcs pf-core verify-proof-binding --certificate <cert> --trace <trace>` | OK when hashes and generated file match |
| Adapter pin parity | `bash scripts/run-pf-core-adapter-ci.sh` | Vectors match `provability-fabric-core` pin |
| Release-grade local | `bash scripts/pf-core-release-grade-local.sh` | Conformance `--release-grade`, verify-proof-binding, lean-check when lake/WSL available |

## Artifact and policy checks

| Item | Location | Auditor confirms |
|------|----------|------------------|
| `semantics_layer` schema | `schemas/PFCoreContract.v0.schema.json` | Field map with `lean` / `runtime` / `out_of_scope` |
| Semantics validator | `python/pcs_core/pf_core_contract_semantics.py` | Wired into `validate-contracts` and lean codegen |
| Trusted boundary | `docs/pf-core/trusted-boundary.md` | PCS path is envelope-only; PF-Core kernel on `pf-core lean-check` |
| Claim boundaries | `docs/pf-core/claim-boundary.md` | No silent upgrade between claim classes |
| Deferred research | `docs/pf-core/non-interference.md`, `runtime-semantics.md`, `assumptions.md` | `TenantProjectionIsolation` proved; paired-execution NI scaffolding only; RoleMap permanent assumption documented |
| Frozen hash vectors | `python/tests/hash_vectors/pf_core/` | Python, Rust, TypeScript agree on canonical form |

## Claim class boundaries (must not overclaim)

| Path | May emit | Must not emit |
|------|----------|---------------|
| `pcs pcs-envelope check` | `ProofChecked` / `Rejected` on `LeanCheckResult.v0` | `LeanKernelChecked` |
| `pcs pf-core lean-check` (full) | `LeanKernelChecked` when concrete proof succeeds | Global non-interference, full role/policy Lean discharge |
| `pcs pf-core lean-check --skip-build` | `RuntimeChecked` | `LeanKernelChecked` |
| `pcs pf-core certifyedge-check` | `CertificateChecked` | `LeanKernelChecked` |

## Sign-off

| Role | Name | Date | Result |
|------|------|------|--------|
| Engineering | PCS maintainers | 2026-06-29 | Tier 1 complete; B1–B7 + B5 vectors + Phase 3 shipped; tag `v0.1.0-pf-core` at `ea16683`; six CI jobs green [28405144850](https://github.com/SentinelOps-CI/pcs-core/actions/runs/28405144850) |
| Security / assurance | PCS maintainers | 2026-06-29 | Claim boundaries accepted; TraceSafeR release-grade path; CertifyEdge live/stub/mock separation; release gate blocks without live CLI |

Reference: `docs/pf-core/current-gap-audit.md`, `docs/pf-core/release-checklist.md`, `CHANGELOG.md`.
