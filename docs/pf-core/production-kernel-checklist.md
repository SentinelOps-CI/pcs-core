# PF-Core production kernel — external auditor sign-off

One-page verification checklist for Tier 1 PF-Core production kernel readiness in `pcs-core`. Run from repository root unless noted.

## Scope

This checklist covers the **production trusted kernel** only: contract semantics, cross-language validation parity, PCS release-envelope separation (choice B), and integration hooks. It does **not** claim full global non-interference or Lean RoleMap discharge (Tier 2 deferrals).

## Evidence commands

| Check | Command | Expected |
|-------|---------|----------|
| Tier 1 semantics + envelope | `cd python && pytest -q tests/test_pf_core_tier1.py` | All pass |
| Cross-language parity | `cd python && pytest -q tests/test_pf_core_cross_language.py` | All pass (TS may skip if `node` absent) |
| Full PF-Core suite | `cd python && pytest -q tests/ -k test_pf_core` | All pass |
| Rust PF-Core vectors | `cd rust && cargo test pf_core` | All pass |
| TypeScript hash vectors | `cd typescript/packages/core && npx tsc && node --test dist/tests/examples.test.js` | All pass |
| PCS envelope path | `pcs pcs-envelope check --obligations examples/proof_obligation.valid.json --out /tmp/envelope.json --skip-lean-build` | No `LeanKernelChecked` in output |
| Lean kernel (optional) | `cd lean && lake build PFCore && pcs pf-core lean-check --trace examples/pf-core-valid/tool_use_trace_compiled/pfcore_trace.json` | `LeanKernelChecked` when full pipeline succeeds |
| Adapter pin parity | `bash scripts/run-pf-core-adapter-ci.sh` | Vectors match `provability-fabric-core` pin |

## Artifact and policy checks

| Item | Location | Auditor confirms |
|------|----------|------------------|
| `semantics_layer` schema | `schemas/PFCoreContract.v0.schema.json` | Field map with `lean` / `runtime` / `out_of_scope` |
| Semantics validator | `python/pcs_core/pf_core_contract_semantics.py` | Wired into `validate-contracts` and lean codegen |
| Trusted boundary | `docs/pf-core/trusted-boundary.md` | PCS path is envelope-only; PF-Core kernel on `pf-core lean-check` |
| Claim boundaries | `docs/pf-core/claim-boundary.md` | No silent upgrade between claim classes |
| Deferred research | `docs/pf-core/non-interference.md`, `assumptions.md` | RoleMap permanent assumption documented |
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
| Engineering | | | Tier 1 complete / gaps noted |
| Security / assurance | | | Boundaries accepted / exceptions listed |

Reference: `docs/pf-core/current-gap-audit.md`, `docs/pf-core/release-checklist.md`, `CHANGELOG.md`.
